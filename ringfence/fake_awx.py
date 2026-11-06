"""In-process fake Airwallex (httpx.MockTransport) mirroring BUILD_SPEC section 3, with fault injection.

Used by every offline test and by --backend fake. Where a live probe disagreed with the spec, the live
result wins (docs/PROBES.md) and the fake follows it; knobs below default to what the probes showed.
"""
from __future__ import annotations

import hashlib
import hmac
import itertools
import json
import re
import threading
import time
import uuid
from copy import deepcopy
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

import httpx

from .money import dumps_money, loads_money, q

PREFUNDED = ("CNY", "EUR", "GBP", "HKD", "USD")
GB_OK_SORT_CODES = {"040004", "200000", "041907"}
# mid rates, units of buy currency per 1 unit of sell currency (display-quality only)
_USD = {"USD": Decimal(1), "GBP": Decimal("0.79"), "EUR": Decimal("0.92"), "AUD": Decimal("1.52"),
        "CNY": Decimal("7.2"), "HKD": Decimal("7.8")}
FAILURE_TYPES = {"BENEFICIARY_BANK_RETURNED": ("INCORRECT_ROUTING", "90802: Beneficiary bank returned")}


def _as_stored(b: dict) -> dict:
    """Live Airwallex drops swift_code for a LOCAL IBAN payee (verified 6 Nov)."""
    ben = deepcopy(b.get("beneficiary") or {})
    bd = ben.get("bank_details") or {}
    if bd.get("iban") and b.get("transfer_methods") == ["LOCAL"]:
        bd.pop("swift_code", None)
    return ben


@dataclass
class Account:
    id: str
    balances: dict[str, Decimal] = field(default_factory=dict)
    beneficiaries: dict[str, dict] = field(default_factory=dict)
    gas: dict[str, dict] = field(default_factory=dict)
    transfers: dict[str, dict] = field(default_factory=dict)
    req_index: dict[str, str] = field(default_factory=dict)
    deposits: dict[str, dict] = field(default_factory=dict)
    conversions: dict[str, dict] = field(default_factory=dict)  # by request_id
    reserved: dict[str, Decimal] = field(default_factory=dict)  # debit-at-PAID mode


def _err(status: int, code: str, message: str, **extra: Any) -> httpx.Response:
    if "error_code" in extra:  # Airwallex beneficiary validation codes (001, 010, 011, 016)
        message += f" (code {extra['error_code']})"
    return _json(status, {"code": code, "message": message, **extra})


def _json(status: int, body: Any) -> httpx.Response:
    return httpx.Response(status, content=dumps_money(body), headers={"content-type": "application/json"})


def _ga_ccy(ga: dict) -> str:
    return ga["required_features"][0]["currency"]


class FakeAirwallex:
    def __init__(self, account_ids: dict[str, str] | None = None):
        """account_ids: tenant key -> account id (platform, northwind, kestrel, harbour)."""
        self.lock = threading.RLock()
        self.accounts: dict[str, Account] = {}
        self.tokens: dict[str, str | None] = {}
        self.quotes: dict[str, dict] = {}
        self.webhook_secret = "whsec_fake"
        self.holders: dict[str, str] = {}  # account number / IBAN -> the holder's name at the bank (verify_account)
        self.log: list[tuple[str, str, str | None]] = []  # (method, path, account) for assertions
        # behaviour knobs (see PROBES.md)
        self.insufficient_funds_mode = "error"  # error | overdue
        self.rejected_create_burns_request_id = False
        self.balance_debit_at = "create"  # create | paid
        self.pending_deposit_available = True
        self.auto_cancel_failed = False
        self.fx_shift_bps = 0
        # fault injection
        self._faults: list[dict] = []
        self._expire_once = 0
        self._ids = itertools.count(1)
        ids = account_ids or {}
        for key in ("platform", "northwind", "kestrel", "harbour"):
            self.add_account(ids.get(key, f"acct_FAKE_{key}"))
        self.platform = ids.get("platform", "acct_FAKE_platform")
        self._seed_platform_ga()
        if "harbour" in ids or not ids:
            h = self.accounts[ids.get("harbour", "acct_FAKE_harbour")]
            h.gas["8ec497a4-67a9-4ba2-8b3d-48f1a53d1f4d"] = self._make_ga("AU", "AUD", "Harbour AUD")
            h.gas["8ec497a4-67a9-4ba2-8b3d-48f1a53d1f4d"]["id"] = "8ec497a4-67a9-4ba2-8b3d-48f1a53d1f4d"
            h.balances["AUD"] = Decimal("3000.00")
        self.transport = httpx.MockTransport(self._handle)

    # -- setup helpers -----------------------------------------------------------------------
    def add_account(self, acct_id: str) -> Account:
        a = Account(acct_id, {c: Decimal("10000000.00") for c in PREFUNDED})
        for i in range(9):  # each new account gets 9 seeded beneficiaries
            bid = f"seed-{uuid.uuid4().hex[:8]}"
            a.beneficiaries[bid] = {"id": bid, "nickname": f"Seeded {i + 1}",
                                    "beneficiary": {"bank_details": {"account_number": f"9000{i:04d}"}}}
        ga = self._make_ga("GB", "GBP", "Sandbox Business")  # every live account starts with its own GBP GA
        a.gas[ga["id"]] = ga
        self.accounts[acct_id] = a
        return a

    def _nid(self, prefix: str) -> str:
        return f"{prefix}-{next(self._ids):06d}-{uuid.uuid4().hex[:8]}"

    def _make_ga(self, country: str, ccy: str, nick: str, number: str | None = None) -> dict:
        """Live shape: account_number/iban on top, routing codes only under supported_features (P11)."""
        n = next(self._ids)
        base = {"id": str(uuid.uuid4()), "status": "ACTIVE", "country_code": country, "nick_name": nick,
                "account_name": "Sandbox Business", "request_id": str(uuid.uuid4()),
                "required_features": [{"currency": ccy, "transfer_method": "LOCAL"}],
                "account_number": f"{40000000 + n * 37:08d}"}
        routing: list[dict] = []
        if country == "AU":
            base["account_number"] = f"{200000000 + n * 91:09d}"
            routing = [{"type": "bsb", "value": f"06{n % 10000:04d}"}]
        elif country == "GB":
            routing = [{"type": "sort_code", "value": "041907"}]
        elif country == "US":
            routing = [{"type": "ach", "value": "026073150"}]
        else:
            base["iban"] = f"{country}89370400440532{n:06d}"
        if number:
            base["account_number"] = number
        base["supported_features"] = [{"currency": ccy, "transfer_method": "LOCAL", "type": "DEPOSIT",
                                       "routing_codes": routing}]
        return base

    def _seed_platform_ga(self) -> None:
        ga = self._make_ga("GB", "GBP", "Platform GBP", number="07371376")
        self.accounts[self.platform].gas[ga["id"]] = ga

    def inject(self, kind: str, **kw: Any) -> None:
        """timeout_after_commit(n) | error_before_commit(status, n) | slow(ms) | token_expired_once().
        Faults hit POST /transfers/create unless path=/method= is given."""
        with self.lock:
            if kind == "token_expired_once":
                self._expire_once += 1
            else:
                self._faults.append({"kind": kind, "n": kw.pop("n", 1), "path": kw.pop("path", "transfers/create"),
                                     "method": kw.pop("method", "POST"), **kw})

    # -- http plumbing -----------------------------------------------------------------------
    def _handle(self, req: httpx.Request) -> httpx.Response:
        with self.lock:
            return self._route(req)

    def _route(self, req: httpx.Request) -> httpx.Response:
        path = req.url.path
        if not path.startswith("/api/v1/"):
            return _err(404, "not_found", "Route Not Found")
        path = path[len("/api/v1/"):].strip("/")
        method = req.method
        if path == "authentication/login":
            return self._login(req)
        auth = req.headers.get("authorization", "")
        tok = auth.removeprefix("Bearer ").strip()
        if not auth:
            return httpx.Response(403, text="<html>403 Forbidden</html>", headers={"content-type": "text/html"})
        if tok not in self.tokens:
            return _err(401, "unauthorized", "Unauthorized")
        if self._expire_once > 0:
            self._expire_once -= 1
            del self.tokens[tok]
            return _err(401, "credentials_expired", "Access token expired")
        acct = self.tokens[tok]
        obo = req.headers.get("x-on-behalf-of")
        if obo and obo != acct:
            return _err(401, "credentials_invalid", "Access Denied")
        if acct is None:
            return _err(401, "unauthorized", "Insufficient permissions")
        self.log.append((method, path, acct))
        for f in list(self._faults):
            if f["path"] in path and method == f["method"] and f["kind"] in ("error_before_commit", "slow"):
                f["n"] -= 1
                if f["n"] <= 0:
                    self._faults.remove(f)
                if f["kind"] == "slow":
                    time.sleep(f["ms"] / 1000)
                    continue
                return _err(f["status"], "injected", "injected fault")
        a = self.accounts[acct]
        body = loads_money(req.content) if req.content else {}
        qs = dict(req.url.params)
        resp = self._dispatch(method, path, body, qs, a)
        for f in list(self._faults):  # timeout AFTER the side effect: the classic double-pay trap
            if f["kind"] == "timeout_after_commit" and f["path"] in path and method == f["method"]:
                f["n"] -= 1
                if f["n"] <= 0:
                    self._faults.remove(f)
                raise httpx.ReadTimeout("injected timeout after commit", request=req)
        return resp

    def _login(self, req: httpx.Request) -> httpx.Response:
        if not req.headers.get("x-client-id") or not req.headers.get("x-api-key"):
            return _err(401, "credentials_invalid", "Access Denied")
        if req.content:
            return _err(400, "validation_error", "body must be empty")
        login_as = req.headers.get("x-login-as")
        if login_as is not None:
            if not login_as.startswith("acct_"):
                return _err(400, "validation_error", "invalid account ID format")
            if login_as not in self.accounts:
                return _err(401, "credentials_invalid", "Access Denied")
        tok = "tok_" + uuid.uuid4().hex
        self.tokens[tok] = login_as
        exp = (datetime.now(UTC) + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%S+0000")
        return _json(201, {"token": tok, "expires_at": exp})

    def _dispatch(self, method: str, path: str, body: dict, qs: dict, a: Account) -> httpx.Response:
        if method == "GET":
            if path == "account":
                return _json(200, {"id": a.id})
            if path == "balances/current":
                return _json(200, [self._balance_row(a, c) for c in sorted(a.balances)])
            if path == "transfers":
                return self._list_transfers(a, qs)
            if m := re.fullmatch(r"transfers/([^/]+)", path):
                t = a.transfers.get(m[1])
                return _json(200, self._view(a, t)) if t else _err(404, "not_found", "transfer not found")
            if path == "beneficiaries":
                return _json(200, {"items": list(a.beneficiaries.values()), "has_more": False,
                                   "total_count": len(a.beneficiaries)})
            if m := re.fullmatch(r"beneficiaries/([^/]+)", path):
                b = a.beneficiaries.get(m[1])
                return _json(200, b) if b else httpx.Response(200, content=b"")  # live 6 Nov: a foreign or deleted id is an empty 200
            if path == "global_accounts":
                return _json(200, {"items": list(a.gas.values()), "has_more": False})
            if path == "deposits":
                if int(qs.get("page_size", 0)) < 10 or "page_num" not in qs:
                    return _err(400, "validation_error", "page_num and page_size >= 10 required")
                return _json(200, {"items": list(a.deposits.values()), "has_more": False})
            if path == "webhooks":
                return _json(200, {"items": [], "has_more": False})
        if method == "POST":
            if path == "transfers/create":
                return self._create_transfer(a, body)
            if (m := re.fullmatch(r"transfers/([^/]+)/cancel", path)) and m[1] in a.transfers:
                t = a.transfers[m[1]]
                if t["status"] not in ("SCHEDULED", "PROCESSING"):  # live: cancellable until it is SENT
                    return _err(400, "update_unsupported", "The transfer in the current status cannot be updated.")
                t["status"] = "CANCELLED"
                self._refund(a, t)
                return _json(200, dict(t))
            if path in ("beneficiaries/create", "beneficiaries/validate"):
                return self._beneficiary(a, body, create=path.endswith("create"))
            if (m := re.fullmatch(r"beneficiaries/([^/]+)/update", path)) and m[1] in a.beneficiaries:
                a.beneficiaries[m[1]].update(beneficiary=_as_stored(body))  # in place: the id stays (as live)
                return _json(200, a.beneficiaries[m[1]])
            if path == "beneficiaries/verify_account":
                bd = body.get("bank_details") or {}
                held = self.holders.get(bd.get("iban") or bd.get("account_number") or "")
                res = "FULL_MATCH" if held in (None, bd.get("account_name")) else "NOT_MATCHED"
                return _json(200, {"code": "VERIFIED", "details": {"account_name_match_result": res}})
            if path == "global_accounts/create":
                return self._create_ga(a, body)
            if path == "simulation/deposit/create":
                return self._sim_deposit(a, body)
            if m := re.fullmatch(r"simulation/transfers/([^/]+)/transition", path):
                return self._sim_transition(a, m[1], body)
            if m := re.fullmatch(r"simulation/deposits/([^/]+)/(settle|reverse)", path):
                return _err(404, "not_found", "Route Not Found")  # 404 for global-account deposits
            if path == "fx/quotes/create":
                return self._quote(body)
            if path == "fx/conversions/create":
                return self._convert(a, body)
        return _err(404, "not_found", "Route Not Found")

    # -- balances ----------------------------------------------------------------------------
    def _balance_row(self, a: Account, c: str) -> dict:
        total = a.balances[c]
        res = a.reserved.get(c, Decimal(0))
        return {"currency": c, "available_amount": total - res, "pending_amount": Decimal("0.00"),
                "reserved_amount": res, "total_amount": total}

    def balance(self, acct: str, ccy: str) -> Decimal:
        return self.accounts[acct].balances.get(ccy, Decimal("0.00"))

    # -- transfers ---------------------------------------------------------------------------
    def _view(self, a: Account, t: dict) -> dict:
        if t["status"] == "FAILED" and self.auto_cancel_failed:
            t["status"] = "CANCELLED"
        return dict(t)

    def _list_transfers(self, a: Account, qs: dict) -> httpx.Response:
        items = [self._view(a, t) for t in a.transfers.values()]
        for k in ("request_id", "status", "beneficiary_id", "transfer_currency"):
            if k in qs:
                items = [t for t in items if t[k] == qs[k]]
        if "from_created_at" in qs:
            lo = datetime.fromisoformat(qs["from_created_at"].replace("Z", "+00:00").replace("+0000", "+00:00"))
            items = [t for t in items if datetime.fromisoformat(t["created_at"]) >= lo]
        size = int(qs.get("page_size", 100))
        start = int(str(qs.get("page", "0")).removeprefix("cur-") or 0)  # like live: page_num is ignored, page is a cursor
        body = {"items": items[start:start + size]}
        if start + size < len(items):
            body["page_after"] = f"cur-{start + size}"
        return _json(200, body)

    def _create_transfer(self, a: Account, b: dict) -> httpx.Response:
        rid = b.get("request_id")
        if not isinstance(rid, str) or not 10 <= len(rid) <= 50:
            return _err(400, "validation_error", "request_id must be 10-50 chars")
        if rid in a.req_index:
            return _err(400, "duplicate_request_id", "duplicate request_id", details={"id": a.req_index[rid]})
        ben = a.beneficiaries.get(b.get("beneficiary_id", ""))
        if ben is None:
            return _err(400, "validation_error", "beneficiary not found", source="beneficiary_id")
        if b.get("transfer_method") not in ("LOCAL", "SWIFT"):
            return _err(400, "validation_error", "transfer_method must be LOCAL or SWIFT")
        amt, ccy, src = b.get("transfer_amount"), b.get("transfer_currency"), b.get("source_currency")
        if not isinstance(amt, (Decimal, int)) or Decimal(amt) <= 0 or ccy != src:
            return _err(400, "validation_error", "bad amount or currency (fake supports same-currency only)")
        amt = Decimal(amt)
        fee = Decimal("12.85") if b["transfer_method"] == "SWIFT" else Decimal(0)
        status = "SCHEDULED"
        if a.balances.get(src, Decimal(0)) < amt + (fee if src == "EUR" else 0):
            if self.insufficient_funds_mode == "error":
                if self.rejected_create_burns_request_id:
                    a.req_index[rid] = "rejected"
                return _err(400, "balance_insufficient", "There is insufficient Wallet balance to fund this transfer.")
            status = "OVERDUE"
        tid = self._nid("tr")
        t = {"id": tid, "request_id": rid, "status": status, "beneficiary_id": b["beneficiary_id"],
             "transfer_amount": amt, "transfer_currency": ccy, "source_currency": src,
             "transfer_method": b["transfer_method"], "reason": b.get("reason"), "reference": b.get("reference"),
             "created_at": datetime.now(UTC).isoformat(), "fee_amount": fee, "debited": False,
             "beneficiary": {"bank_details": dict(ben.get("beneficiary", {}).get("bank_details", {}))}}  # snapshot, as live
        a.transfers[tid] = t
        a.req_index[rid] = tid
        if status != "OVERDUE" and self.balance_debit_at == "create":
            self._debit(a, t)
        return _json(201, self._view(a, t))

    def _debit(self, a: Account, t: dict) -> None:
        if not t["debited"]:
            a.balances[t["source_currency"]] -= t["transfer_amount"] + (t["fee_amount"] if t["source_currency"] == "EUR" else 0)
            t["debited"] = True

    def _refund(self, a: Account, t: dict) -> None:
        if t["debited"]:
            a.balances[t["source_currency"]] += t["transfer_amount"] + (t["fee_amount"] if t["source_currency"] == "EUR" else 0)
            t["debited"] = False

    def _sim_transition(self, a: Account, tid: str, b: dict) -> httpx.Response:
        t = a.transfers.get(tid)
        if t is None:
            return _err(404, "not_found", "transfer not found")
        nxt, cur = b.get("next_status"), t["status"]
        ok = {"SENT": ("SCHEDULED", "PROCESSING"), "PAID": ("SENT",), "FAILED": ("SENT", "PAID"),
              "CANCELLED": ("SCHEDULED", "OVERDUE", "PROCESSING")}
        if nxt == "OVERDUE":
            return _err(500, "internal_error", "internal error")  # sandbox 500s on forced OVERDUE
        if nxt not in ok or cur not in ok[nxt]:
            return _err(400, "validation_error", f"cannot go from {cur} to {nxt}")
        if nxt == "SENT" and cur == "OVERDUE":
            return _err(400, "validation_error", "overdue")
        if nxt in ("SENT", "PAID") and not t["debited"] and self.balance_debit_at == "create":
            self._debit(a, t)
        if nxt == "PAID" and self.balance_debit_at == "paid":
            self._debit(a, t)
        t["status"] = nxt
        if nxt == "FAILED":
            ft = b.get("failure_type", "BENEFICIARY_BANK_RETURNED")
            t["failure_type"], t["failure_reason"] = FAILURE_TYPES.get(ft, (ft, "simulation"))
            self._refund(a, t)
        if nxt == "CANCELLED":
            t["failure_reason"] = "simulation"
            self._refund(a, t)
        return _json(200, self._view(a, t))

    # -- beneficiaries / global accounts / deposits -------------------------------------------
    def _beneficiary(self, a: Account, b: dict, create: bool) -> httpx.Response:
        if "payment_methods" in b or "transfer_methods" not in b:
            return _err(400, "validation_error", "transfer_methods required", error_code="001")
        ben = b.get("beneficiary") or {}
        bank = ben.get("bank_details") or {}
        country = bank.get("bank_country_code")
        if country == "GB":
            if bank.get("account_routing_type1") != "sort_code":
                return _err(400, "validation_error", "routing type must be sort_code", error_code="011")
            if not bank.get("bank_name"):
                return _err(400, "validation_error", "bank_name required", error_code="002")
            if bank.get("account_routing_value1") not in GB_OK_SORT_CODES:
                return _err(400, "validation_error", "invalid sort code", error_code="010")
        if country == "US" and bank.get("bank_account_category") not in ("Checking", "Savings"):
            return _err(400, "validation_error", "bank_account_category invalid", error_code="016")
        if not create:
            return _json(200, {"valid": True})
        bid = self._nid("ben")
        rec = {"id": bid, "nickname": b.get("nickname"), **{k: v for k, v in b.items() if k != "nickname"}, "beneficiary": _as_stored(b)}
        a.beneficiaries[bid] = rec
        return _json(201, rec)

    def _create_ga(self, a: Account, b: dict) -> httpx.Response:
        feats = b.get("required_features") or [{}]
        if not feats[0].get("transfer_method"):
            return _err(400, "field_required", "ensure transfer_method is not null")
        if feats[0]["transfer_method"] not in ("LOCAL", "SWIFT"):
            return _err(400, "invalid_argument", "ensure transfer_method is one of [LOCAL, SWIFT]")
        ccy = feats[0].get("currency", "USD")
        country = b.get("country_code", "")
        if country == "BE":
            return _err(400, "validation_error", "country not supported for EUR")
        ga = self._make_ga(country, ccy, b.get("nick_name", ""))
        a.gas[ga["id"]] = ga
        return _json(201, ga)

    def _sim_deposit(self, a: Account, b: dict) -> httpx.Response:
        ga = a.gas.get(b.get("global_account_id", ""))
        if ga is None:
            return _err(404, "not_found", "global account not found")
        return _json(201, self.deposit(a.id, ga["id"], Decimal(b["amount"]), b.get("reference"),
                                       b.get("status", "SETTLED"), b.get("payer_name", "Payer")))

    # -- fx ----------------------------------------------------------------------------------
    def _rate(self, sell: str, buy: str) -> Decimal:
        r = _USD[buy] / _USD[sell] * (1 + Decimal(self.fx_shift_bps) / 10000)
        return r.quantize(Decimal("0.0001"))

    def _quote(self, b: dict) -> httpx.Response:
        sell, buy = b.get("sell_currency"), b.get("buy_currency")
        if sell not in _USD or buy not in _USD or sell == buy:
            return _err(400, "validation_error", "bad currency pair")
        rate = self._rate(sell, buy)
        if "buy_amount" in b:
            buy_amt = Decimal(b["buy_amount"])
            sell_amt = q(buy_amt / rate, sell)
        elif "sell_amount" in b:
            sell_amt = Decimal(b["sell_amount"])
            buy_amt = q(sell_amt * rate, buy)
        else:
            return _err(400, "validation_error", "buy_amount or sell_amount required")
        qid = "q-" + uuid.uuid4().hex
        quote = {"quote_id": qid, "client_rate": rate, "buy_currency": buy, "sell_currency": sell,
                 "buy_amount": buy_amt, "sell_amount": sell_amt, "usage": "MULTI_USE", "validity": "MIN_1"}
        self.quotes[qid] = quote
        return _json(201, quote)

    def _convert(self, a: Account, b: dict) -> httpx.Response:
        rid = b.get("request_id", "")
        if rid in a.conversions:
            return _err(400, "duplicate_request_id", "duplicate request_id", details={"id": a.conversions[rid]["conversion_id"]})
        qt = self.quotes.get(b.get("quote_id", ""))
        if qt is None:
            return _err(400, "validation_error", "quote missing")
        if (qt["buy_currency"], qt["sell_currency"]) != (b.get("buy_currency"), b.get("sell_currency")):
            return _err(400, "validation_error", "quote mismatch")
        if a.balances.get(qt["sell_currency"], Decimal(0)) < qt["sell_amount"]:
            return _err(400, "insufficient_funds", "insufficient balance to convert")
        a.balances[qt["sell_currency"]] -= qt["sell_amount"]
        a.balances[qt["buy_currency"]] = a.balances.get(qt["buy_currency"], Decimal(0)) + qt["buy_amount"]
        conv = {"conversion_id": "conv-" + uuid.uuid4().hex[:12], "request_id": rid, "status": "SETTLED",
                "buy_currency": qt["buy_currency"], "sell_currency": qt["sell_currency"],
                "buy_amount": qt["buy_amount"], "sell_amount": qt["sell_amount"], "client_rate": qt["client_rate"]}
        a.conversions[rid] = conv
        return _json(201, conv)

    # -- harness-side scenario controls (also reachable via scenarios.FakeSim) ------------------
    def deposit(self, acct: str, ga_id: str, amount: Decimal, reference: str | None,
                status: str = "SETTLED", payer: str = "Payer") -> dict:
        with self.lock:
            a = self.accounts[acct]
            ga = a.gas[ga_id]
            d = {"id": self._nid("dep"), "global_account_id": ga_id, "status": status, "amount": amount,
                 "currency": _ga_ccy(ga), "reference": reference, "payer_name": payer,
                 "created_at": datetime.now(UTC).isoformat()}
            a.deposits[d["id"]] = d
            if status == "SETTLED" or (status == "PENDING" and self.pending_deposit_available):
                a.balances[_ga_ccy(ga)] = a.balances.get(_ga_ccy(ga), Decimal(0)) + amount
            return dict(d)

    def reverse_deposit(self, acct: str, dep_id: str) -> None:
        with self.lock:
            a = self.accounts[acct]
            d = a.deposits[dep_id]
            a.balances[d["currency"]] -= d["amount"]
            d["status"] = "REVERSED"

    def transfer_by_request(self, acct: str, rid: str) -> dict | None:
        a = self.accounts[acct]
        tid = a.req_index.get(rid)
        return a.transfers.get(tid) if tid else None

    def all_transfers(self, acct: str) -> list[dict]:
        return list(self.accounts[acct].transfers.values())

    def set_status(self, acct: str, tid: str, status: str, **fields: Any) -> None:
        """cancel / overdue / any harness-forced status (OVERDUE cannot be forced via the sandbox API)."""
        with self.lock:
            a = self.accounts[acct]
            t = a.transfers[tid]
            t["status"] = status
            t.update(fields)
            if status in ("CANCELLED", "FAILED"):
                self._refund(a, t)

    def late_failure(self, acct: str, tid: str, failure_type: str = "BENEFICIARY_BANK_RETURNED") -> None:
        a = self.accounts[acct]
        t = a.transfers[tid]
        t["status"] = "FAILED"
        t["failure_type"], t["failure_reason"] = FAILURE_TYPES.get(failure_type, (failure_type, "simulation"))
        self._refund(a, t)

    # -- webhooks ----------------------------------------------------------------------------
    def sign_webhook(self, ts: str, raw: bytes) -> str:
        return hmac.new(self.webhook_secret.encode(), ts.encode() + raw, hashlib.sha256).hexdigest()

    def webhook(self, event: dict, sink: Callable[[dict, bytes], Any], *, bad_signature: bool = False,
                duplicate: bool = False) -> list:
        raw = json.dumps(event).encode()
        ts = str(int(time.time() * 1000))
        sig = self.sign_webhook(ts, raw)
        headers = {"x-timestamp": ts, "x-signature": "0" * 64 if bad_signature else sig}
        out = [sink(headers, raw)]
        if duplicate:
            out.append(sink(headers, raw))
        return out
