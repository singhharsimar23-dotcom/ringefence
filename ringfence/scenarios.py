"""[SIMULATED] sandbox actions the real world would perform: a bank pays the wire, the employer tops up.
Backend-agnostic: uses only /simulation/* endpoints that both the fake and the live sandbox have."""
from __future__ import annotations

from . import store
from .awx import Awx
from .executor import INFLIGHT
from .ledger import Ledger


def pay_out(awx: Awx, L: Ledger, run_id: str, tenant: str) -> int:
    """[SIMULATED] move this run's in-flight transfers SCHEDULED -> SENT -> PAID. Returns how many."""
    c, n = awx.for_tenant(tenant), 0
    for ln in store.get_lines(L, run_id, tenant, states=INFLIGHT):
        tid = ln.get("transfer_id")
        if not tid:
            continue
        for nxt in (("PAID",) if ln["state"] == "SENT" else ("SENT", "PAID")):
            c.post(f"/simulation/transfers/{tid}/transition", {"next_status": nxt})
        n += 1
    if n:
        L.append("SIMULATED", {"what": "[SIMULATED] transfers marked SENT then PAID", "count": n}, run_id, tenant)
    return n


def top_up(awx: Awx, L: Ledger, run_id: str, tenant: str, request: dict) -> None:
    """[SIMULATED] the employer's bank wires exactly what the funding request asked for, with its reference."""
    awx.for_tenant(tenant).post("/simulation/deposit/create", {
        "global_account_id": request["ga_id"], "amount": request["amount"], "reference": request["reference"],
        "payer_name": f"{tenant} (simulated payer)"})
    L.append("SIMULATED", {"what": "[SIMULATED] employer top-up deposit", "amount": request["amount"],
                           "currency": request["currency"], "reference": request["reference"]}, run_id, tenant)
