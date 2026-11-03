"""Environment, tenant registry, clock and signing keys.

env() reuses the env-then-HKCU-registry fallback from scripts/awx.py (setx values are invisible to
shells that were started before setx ran).
"""
from __future__ import annotations

import json
import os
import secrets as _secrets
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def var_dir() -> Path:
    p = Path(os.environ.get("RF_VAR") or ROOT / "var")
    p.mkdir(parents=True, exist_ok=True)
    return p


def env(name: str, default: str | None = None) -> str:
    if os.environ.get(name):
        return os.environ[name]
    if sys.platform == "win32":
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
                return winreg.QueryValueEx(k, name)[0]
        except OSError:
            pass
    if default is not None:
        return default
    raise KeyError(name)


@dataclass(frozen=True)
class Tenant:
    key: str
    name: str
    account_id: str
    display_tz: str


# key, display name, env var holding the account id, display tz
_DEFS = [
    ("platform", "Platform", "AWX_PLATFORM_ACCOUNT", "UTC"),
    ("northwind", "Northwind Studio", "AWX_EMPLOYER_A", "Europe/London"),
    ("kestrel", "Kestrel Labs", "AWX_EMPLOYER_B", "America/New_York"),
    ("harbour", "Harbour Foods", "AWX_EMPLOYER_C", "Australia/Sydney"),
]
EMPLOYERS = ("northwind", "kestrel", "harbour")


def tenants(fake: bool = False) -> dict[str, Tenant]:
    """Fake backend uses fixed ids so the demo runs with no keys at all."""
    return {k: Tenant(k, n, f"acct_FAKE_{k}" if fake else env(v), tz) for k, n, v, tz in _DEFS}


class Clock:
    """RF_NOW shifts business time only (act-by, countdowns). Ledger ts, token expiry, approval
    expiry and backoff use real UTC / monotonic."""

    def __init__(self) -> None:
        raw = os.environ.get("RF_NOW")
        self.set_business(datetime.fromisoformat(raw) if raw else None)

    def set_business(self, dt: datetime | None) -> None:
        self._start, self._mono0 = dt, time.monotonic()

    def utc_now(self) -> datetime:
        return datetime.now(UTC)

    def business_now(self) -> datetime:
        if self._start is None:
            return self.utc_now()
        return self._start + timedelta(seconds=time.monotonic() - self._mono0)

    now = business_now


clock = Clock()


def get_key(name: str) -> bytes:
    """RF_MANDATE_KEY / RF_APPROVAL_KEY: env first, else generated once into var/keys.json."""
    if os.environ.get(name):
        return os.environ[name].encode()
    f = var_dir() / "keys.json"
    keys = json.loads(f.read_text()) if f.exists() else {}
    if name not in keys:
        keys[name] = _secrets.token_hex(32)
        f.write_text(json.dumps(keys))
    return keys[name].encode()
