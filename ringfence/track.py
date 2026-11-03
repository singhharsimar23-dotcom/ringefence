"""Contractor 'track my pay' page. The link carries an opaque token: HMAC(approval key, tenant|run|contractor).
It shows that contractor's own payment and nothing else: no other contractor, no other employer, no balances."""
from __future__ import annotations

import hashlib
import hmac

from . import copy, seed, store
from .config import EMPLOYERS, get_key
from .ledger import Ledger


def token(tenant: str, run_id: str, contractor_id: str) -> str:
    msg = f"track|{tenant}|{run_id}|{contractor_id}".encode()
    return hmac.new(get_key("RF_APPROVAL_KEY"), msg, hashlib.sha256).hexdigest()[:24]


def lookup(L: Ledger, tok: str) -> dict | None:
    """Finds the line behind a token by recomputing tokens for known lines; unknown or malformed tokens give None."""
    if len(tok) != 24:
        return None
    for t in EMPLOYERS:
        for r in L.query("SELECT run_id FROM runs WHERE tenant=?", (t,)):
            run = store.get_run(L, r["run_id"], t)
            for ln in store.get_lines(L, r["run_id"], t, round=run["round"]):
                if hmac.compare_digest(token(t, r["run_id"], ln["contractor_id"]), tok):
                    c = seed.contractors(t)[ln["contractor_id"]]
                    return {"employer": t.title(), "name": c.name, "amount": ln["amount"], "currency": ln["currency"],
                            "pay_date": run.get("pay_date", ""), "status": copy.pill(ln["state"], run["state"]),
                            "state": ln["state"]}
    return None
