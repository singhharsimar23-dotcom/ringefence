"""Funding a short employer: act-by deadline, a payment instruction with a unique reference, deposit matching.

A deposit matches only if it is in THIS tenant's account (fetched with its token), lands on the requested
global account, has the requested currency and reference, and is SETTLED (or PENDING, see ACCEPT_PENDING).
A deposit in another tenant can never change this tenant's state: we never look at it.
"""
from __future__ import annotations

import json
import secrets
import string
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from . import beneficiaries as ben
from .awx import Awx
from .config import tenants
from .ledger import Ledger

# configured assumption, not an Airwallex fact: local bank cut-off per currency on the pay date
CUTOFFS = {"AUD": ("Australia/Sydney", "11:00"), "GBP": ("Europe/London", "12:00"),
           "EUR": ("Europe/Berlin", "12:00"), "USD": ("America/New_York", "15:00")}
BUFFER = timedelta(hours=2)
ACCEPT_PENDING = True  # sandbox showed a PENDING simulated deposit as available at once (CLAUDE.md); re-check live (P3)
OK_STATUS = ("SETTLED", "PENDING") if ACCEPT_PENDING else ("SETTLED",)


def act_by(ccy: str, pay_date: date, display_tz: str) -> datetime:
    """Cut-off on the pay date minus the buffer, shown in the tenant's own timezone."""
    zone, hhmm = CUTOFFS[ccy]
    h, m = map(int, hhmm.split(":"))
    return (datetime.combine(pay_date, time(h, m), ZoneInfo(zone)) - BUFFER).astimezone(ZoneInfo(display_tz))


def new_reference(tenant: str, run_id: str) -> str:
    """RF-<TEN3>-<run4>-<rand4>: A-Z0-9 and dashes, <= 18 chars, unique per request."""
    rand = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    return f"RF-{tenant[:3].upper()}-{run_id[-4:].upper()}-{rand}"


def request_funding(awx: Awx, L: Ledger, run_id: str, tenant: str, ccy: str, amount: Decimal,
                    pay_date: date) -> dict:
    """The payment instruction for this tenant's own account. Idempotent per (run, tenant, currency) while OPEN."""
    for r in _requests(L, run_id, tenant, "OPEN"):
        if r["currency"] == ccy:
            return r
    c = awx.for_tenant(tenant)
    ga = next((g for g in map(ben.ga_record, ben.paged(c, "/global_accounts")) if g["currency"] == ccy), None)
    if ga is None:
        raise LookupError(f"{tenant} has no {ccy} global account to be funded into")
    req = {"reference": new_reference(tenant, run_id), "currency": ccy, "amount": str(amount), "ga_id": ga["id"],
           "account_number": ga["account_number"], "iban": ga["iban"], "routing_type": ga["routing_type"],
           "routing_value": ga["routing_value"],
           "act_by": act_by(ccy, pay_date, tenants(fake=True)[tenant].display_tz).isoformat()}
    with L.tx() as tx:
        tx.execute("INSERT INTO funding_requests(run_id, tenant, reference, status, data) VALUES(?,?,?,?,?)",
                   (run_id, tenant, req["reference"], "OPEN", json.dumps(req)))
        tx.append("FUNDING_REQUESTED", req, run_id, tenant)
    return req


def _requests(L: Ledger, run_id: str, tenant: str, status: str) -> list[dict]:
    return [json.loads(r["data"]) for r in L.query(
        "SELECT data FROM funding_requests WHERE run_id=? AND tenant=? AND status=? ORDER BY id",
        (run_id, tenant, status))]


def match_deposits(awx: Awx, L: Ledger, run_id: str, tenant: str) -> list[dict]:
    """Poll this tenant's own deposits; mark matching OPEN requests MATCHED. Returns the matched deposits."""
    open_ = _requests(L, run_id, tenant, "OPEN")
    if not open_:
        return []
    deposits = awx.for_tenant(tenant).get("/deposits", {"page_num": 0, "page_size": 100}).get("items", [])
    out = []
    for req in open_:
        d = next((d for d in deposits if d.get("reference") == req["reference"]
                  and d.get("global_account_id") == req["ga_id"] and d.get("currency") == req["currency"]
                  and d.get("status") in OK_STATUS), None)
        if d is None:
            continue
        with L.tx() as tx:
            tx.execute("UPDATE funding_requests SET status='MATCHED' WHERE reference=?", (req["reference"],))
            tx.append("FUNDING_MATCHED", {"reference": req["reference"], "deposit_id": d["id"],
                                          "amount": str(d["amount"]), "currency": d["currency"],
                                          "status": d["status"]}, run_id, tenant)
        out.append(d)
    return out
