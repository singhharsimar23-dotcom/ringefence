"""Signed Airwallex webhooks. A webhook is a hint, never the truth: after it verifies we re-GET the transfer and
apply what Airwallex says, through the same code the poller uses. A forged or replayed event can at worst cause one
extra GET. HMAC_SHA256(secret, x-timestamp + raw_body) is checked, in constant time, before the body is parsed."""
from __future__ import annotations

import hashlib
import hmac
import json
import time

from .config import EMPLOYERS, tenants
from .executor import Executor
from .ledger import Ledger

WINDOW_S = 300


def _age(ts: str, now: float) -> float:
    t = float(ts)
    return abs(now - (t / 1000 if t > 1e11 else t))  # sandbox timestamps are ms (P6 to confirm live); accept s too


def _tenant_of(account_id: object) -> str | None:
    for fake in (True, False):
        try:
            return next(t for t in EMPLOYERS if tenants(fake)[t].account_id == account_id)
        except (StopIteration, KeyError, OSError):
            continue
    return None


def handle(L: Ledger, ex: Executor, secret: str, headers: dict, raw: bytes, now: float | None = None) -> tuple[int, str]:
    """Returns (http status, short reason). Never raises on bad input."""
    ts, sig = headers.get("x-timestamp", ""), headers.get("x-signature", "")
    if not secret or not ts or not sig:
        return 401, "missing signature"
    want = hmac.new(secret.encode(), ts.encode() + raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(want, sig):
        return 401, "bad signature"
    try:
        if _age(ts, time.time() if now is None else now) > WINDOW_S:
            return 401, "stale timestamp"
        ev = json.loads(raw)
        name, eid = str(ev.get("name", "")), str(ev.get("id") or hashlib.sha256(raw).hexdigest())
    except (ValueError, AttributeError):
        return 400, "unreadable"
    # shortcut: dedupe scans WEBHOOK rows, fine at demo volume; index event_id if this ever sees real traffic
    if any(e["payload"].get("event_id") == eid for e in L.entries(kind="WEBHOOK")):
        return 200, "duplicate"
    data = ev.get("data") if isinstance(ev.get("data"), dict) else {}
    tid = str(data.get("id", ""))
    tenant = next((t for t in EMPLOYERS if tenants(fake=True)[t].account_id == ev.get("account_id")), None) \
        or next((t for t in EMPLOYERS if tenants()[t].account_id == ev.get("account_id")), None)
    result = "ignored"
    if name.startswith("payout.transfer.") and tenant and tid:
        result = "applied" if ex.poll_one(tenant, tid) else "unknown transfer"
    L.append("WEBHOOK", {"event_id": eid, "name": name, "transfer_id": tid, "result": result}, None, tenant)
    return 200, result
