"""Airwallex client. The harness binds a tenant; the model never does.

- for_tenant(key) is the ONLY way to get a client; it is bound to one account and has no obo parameter.
- Login always sends x-login-as with an EMPTY body (a body-less POST needs content=b"").
- GETs retry on 429/5xx/transport errors (<=3). post_money never retries a send: a timeout raises
  AwxTimeout and the executor reconciles by request_id. post() retries only if the body has a request_id.
- Tokens, API keys and Authorization headers are never logged or put in exceptions.
"""
from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import httpx

from .config import Tenant, env, tenants
from .money import dumps_money, loads_money

log = logging.getLogger("ringfence.awx")
TOKEN_REFRESH_S = 25 * 60  # tokens last 30 minutes
GET_RETRIES = 3
RELOGIN_CODES = ("credentials_expired", "unauthorized")  # live garbage/expired bearer -> unauthorized (P9)


class AwxError(Exception):
    def __init__(self, status: int, code: str | None, message: str, details: Any = None):
        super().__init__(f"HTTP {status} {code}: {message}")
        self.status, self.code, self.message, self.details = status, code, message, details


class AwxTimeout(Exception):
    """A money-moving POST may or may not have been processed. Reconcile by request_id; never re-mint."""


def _raise_for(r: httpx.Response) -> Any:
    try:
        data = loads_money(r.content) if r.content else None
    except ValueError:
        data = None
    if r.status_code >= 400:
        d = data if isinstance(data, dict) else {}
        raise AwxError(r.status_code, d.get("code"), str(d.get("message") or r.text[:200]), d.get("details"))
    return data


class TenantClient:
    __slots__ = ("_awx", "_lock", "_tenant", "_token", "_token_at")

    def __init__(self, awx: Awx, tenant: Tenant):
        self._awx, self._tenant = awx, tenant
        self._token: str | None = None
        self._token_at = 0.0
        self._lock = threading.Lock()

    @property
    def tenant_key(self) -> str:
        return self._tenant.key

    @property
    def account_id(self) -> str:
        return self._tenant.account_id

    def __repr__(self) -> str:
        return f"<TenantClient {self._tenant.key}>"

    # -- token -------------------------------------------------------------------------------
    def _login(self) -> str:
        r = self._awx._http.post(
            f"{self._awx.base}/authentication/login",
            headers={"x-client-id": self._awx._client_id, "x-api-key": self._awx._api_key,
                     "x-login-as": self.account_id},
            content=b"")
        tok = _raise_for(r)["token"]
        self._token, self._token_at = tok, time.monotonic()
        return tok

    def _tok(self, force: bool = False) -> str:
        with self._lock:
            if force or self._token is None or time.monotonic() - self._token_at > TOKEN_REFRESH_S:
                return self._login()
            return self._token

    # -- transport ---------------------------------------------------------------------------
    def _send(self, method: str, path: str, params: dict | None, content: bytes | None,
              extra: dict | None = None) -> Any:
        """One request, with exactly one re-login on 401 expired/unauthorized (safe: rejected pre-processing)."""
        for attempt in (0, 1):
            h = {"Authorization": f"Bearer {self._tok(force=attempt == 1)}", **(extra or {})}
            if content is not None:
                h["Content-Type"] = "application/json"
            r = self._awx._http.request(method, f"{self._awx.base}/{path.lstrip('/')}", params=params,
                                        headers=h, content=content)
            log.debug("%s %s -> %s [%s]", method, path, r.status_code, self._tenant.key)
            if r.status_code == 401 and attempt == 0 and self._code(r) in RELOGIN_CODES:
                continue
            return r
        raise AssertionError("unreachable")

    @staticmethod
    def _code(r: httpx.Response) -> str | None:
        try:
            return loads_money(r.content).get("code")
        except (ValueError, AttributeError):
            return None

    def get(self, path: str, params: dict | None = None) -> Any:
        for i in range(GET_RETRIES + 1):
            try:
                r = self._send("GET", path, params, None)
            except httpx.TransportError:
                if i == GET_RETRIES:
                    raise AwxTimeout(f"GET {path} failed after retries") from None
            else:
                if r.status_code not in (429, 500, 502, 503, 504) or i == GET_RETRIES:
                    return _raise_for(r)
            self._awx._sleep(0.5 * 2 ** i)
        raise AssertionError("unreachable")

    def post_money(self, path: str, body: dict) -> Any:
        """No auto-retry. Raises AwxTimeout (outcome unknown) or AwxError(status, code, ...)."""
        try:
            r = self._send("POST", path, None, dumps_money(body))
        except httpx.TransportError as e:
            raise AwxTimeout(f"POST {path}: {type(e).__name__}") from None
        return _raise_for(r)

    def post(self, path: str, body: dict) -> Any:
        """Non-money writes; retried on 5xx/transport errors only when the body carries a request_id."""
        retry = isinstance(body, dict) and "request_id" in body
        for i in range(GET_RETRIES + 1 if retry else 1):
            try:
                r = self._send("POST", path, None, dumps_money(body))
            except httpx.TransportError:
                if not retry or i == GET_RETRIES:
                    raise AwxTimeout(f"POST {path} failed") from None
            else:
                if not retry or r.status_code < 500 or i == GET_RETRIES:
                    return _raise_for(r)
            self._awx._sleep(0.5 * 2 ** i)
        raise AssertionError("unreachable")

    def balances(self) -> dict[str, Decimal]:
        """This tenant's own available balances. Never sum these across tenants."""
        return {b["currency"]: Decimal(b["available_amount"]) for b in self.get("/balances/current")}


class Awx:
    def __init__(self, transport: httpx.BaseTransport | None = None, base_url: str | None = None,
                 client_id: str | None = None, api_key: str | None = None,
                 tenant_map: dict[str, Tenant] | None = None, sleep: Callable[[float], None] = time.sleep):
        fake = transport is not None
        self.base = (base_url or ("https://fake.awx" if fake else env("AWX_BASE_URL"))).rstrip("/") + "/api/v1"
        self._client_id = client_id or ("fake" if fake else env("AWX_CLIENT_ID"))
        self._api_key = api_key or ("fake" if fake else env("AWX_API_KEY"))
        self._http = httpx.Client(transport=transport, timeout=30)
        self._tenants = tenant_map or tenants(fake=fake)
        self._clients: dict[str, TenantClient] = {}
        self._sleep = sleep
        self._lock = threading.Lock()

    def __repr__(self) -> str:
        return f"<Awx {self.base}>"

    def tenants(self) -> dict[str, Tenant]:
        return dict(self._tenants)

    def for_tenant(self, key: str) -> TenantClient:
        with self._lock:
            if key not in self._clients:
                self._clients[key] = TenantClient(self, self._tenants[key])
            return self._clients[key]

    def probe_cross_tenant(self, a: str, b: str) -> tuple[int, str | None]:
        """Read-only isolation proof: tenant a's token + x-on-behalf-of: b must be refused (401).
        The ONLY place that sends x-on-behalf-of. Returns (status, error code)."""
        ca, cb = self.for_tenant(a), self.for_tenant(b)
        r = ca._send("GET", "/balances/current", None, None, {"x-on-behalf-of": cb.account_id})
        return r.status_code, TenantClient._code(r)


def build_backend(backend: str | None = None):
    """Returns (awx, fake_or_None). RF_BACKEND=fake|live (default live)."""
    backend = backend or env("RF_BACKEND", "live")
    if backend == "fake":
        from .fake_awx import FakeAirwallex
        ts = tenants(fake=True)
        fake = FakeAirwallex({k: t.account_id for k, t in ts.items()})
        return Awx(transport=fake.transport, tenant_map=ts), fake
    return Awx(), None
