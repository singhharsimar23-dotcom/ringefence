"""Platform fee: GBP 1.50 per PAID line, paid from the tenant's OWN GBP wallet to its own platform-fee beneficiary.

fee due = 1.50 x (lines PAID in the run, all rounds) - fee already charged for the run. One round, one transfer,
request_id fee-<run>-<tenant>-r<round>. A returned payout shrinks the PAID count, so a later round nets the
credit automatically; FEE_CREDIT is the ledger note. No money moves back. The platform side is a [SIMULATED]
deposit because the sandbox debits the employer but never credits the platform.
"""
from __future__ import annotations

from decimal import Decimal

from . import beneficiaries as ben
from . import seed, store
from .awx import Awx, AwxError, AwxTimeout
from .gate import Deny, FeeFacts, check_fee
from .ledger import Ledger
from .money import FEE_PER_PAYOUT, q

REASON = "professional_business_services"


def fee_due(paid_lines: int, charged: Decimal) -> Decimal:
    return q(FEE_PER_PAYOUT * paid_lines, "GBP") - charged


def platform_ga(awx: Awx) -> dict | None:
    """The platform's own GBP global account that the fee beneficiary points at."""
    want = seed.load()["fee_beneficiary"]["bank"]["account_number"]
    return next((g for g in ben.paged(awx.for_tenant("platform"), "/global_accounts")
                 if ben.ga_record(g)["account_number"] == want), None)


def note_return(L: Ledger, run_id: str, tenant: str) -> None:
    """A PAID line came back. If its fee was already collected, record the credit (netted next round)."""
    with L.tx() as tx:
        run = store.get_run(tx, run_id, tenant)
        if run and Decimal(run.get("fee_charged", "0")) > 0:
            tx.append("FEE_CREDIT", {"amount": str(FEE_PER_PAYOUT), "currency": "GBP",
                                     "note": "returned payout; netted against the next fee for this run"}, run_id, tenant)


def charge(awx: Awx, L: Ledger, run_id: str, tenant: str) -> str:
    """Returns NONE | CHARGED | DENIED | PENDING. Safe to call again: a duplicate request_id adopts the original."""
    run = store.get_run(L, run_id, tenant)
    paid = len(store.get_lines(L, run_id, tenant, states=("PAID",)))
    charged = Decimal(run.get("fee_charged", "0"))
    due = fee_due(paid, charged)
    if due <= 0:
        return "NONE"
    c = awx.for_tenant(tenant)
    rid = f"fee-{run_id}-{tenant}-r{run['round']}"
    reg = ben.load_registry().get("tenants", {}).get(tenant, {})
    fbid = reg.get("fee_beneficiary")
    bank = c.get(f"/beneficiaries/{fbid}")["beneficiary"]["bank_details"] if fbid else {}
    if fbid and ben.fingerprint(bank) != reg.get("pins", {}).get(fbid):  # same account number at another bank passes check_fee
        L.append("GATE_DENY", {"what": "fee", "code": "fee_beneficiary_changed",
                               "detail": "the fee payee's bank details changed outside Ringfence"}, run_id, tenant)
        return "DENIED"
    ok = check_fee(FeeFacts(tenant, c.tenant_key, L.kill_switch_on(), fbid or "", fbid, ben.bank_key(bank),
                            frozenset({seed.load()["fee_beneficiary"]["bank"]["account_number"]}), due, due))
    if isinstance(ok, Deny):
        L.append("GATE_DENY", {"what": "fee", "code": ok.code, "detail": ok.detail}, run_id, tenant)
        return "DENIED"
    L.append("INTENT", {"what": "fee", "request_id": rid, "amount": str(due), "currency": "GBP"}, run_id, tenant)
    body = {"request_id": rid, "beneficiary_id": fbid, "transfer_amount": due, "transfer_currency": "GBP",
            "source_currency": "GBP", "transfer_method": "LOCAL", "reason": REASON, "reference": "Ringfence fee"}
    try:
        t = c.post_money("/transfers/create", body)
    except AwxError as e:
        if e.code != "duplicate_request_id":
            L.append("ALERT", {"what": "fee", "code": e.code, "detail": e.message}, run_id, tenant)
            return "DENIED"
        t = c.get(f"/transfers/{e.details['id']}")
    except AwxTimeout:
        t = c.transfer_by_request(rid)
        if t is None:
            return "PENDING"  # not found: nothing was charged; the next call retries with the same id
    with L.tx() as tx:
        store.set_run(tx, run_id, tenant, fee_charged=str(charged + due), fee_transfer_id=t["id"])
        tx.append("FEE_CHARGED", {"amount": str(due), "currency": "GBP", "transfer_id": t["id"],
                                  "request_id": rid, "round": run["round"]}, run_id, tenant)
    _simulated_platform_credit(awx, L, run_id, tenant, t["id"], due)
    return "CHARGED"


def _simulated_platform_credit(awx: Awx, L: Ledger, run_id: str, tenant: str, transfer_id: str,
                               amount: Decimal) -> None:
    ga = platform_ga(awx)
    if ga is None:
        L.append("ALERT", {"what": "no platform GA for the simulated fee credit"}, run_id, tenant)
        return
    try:
        awx.for_tenant("platform").post("/simulation/deposit/create", {
            "global_account_id": ga["id"], "amount": amount, "reference": transfer_id,
            "payer_name": f"Ringfence fee from {tenant}"})
    except AwxError as e:
        L.append("ALERT", {"what": "simulated fee credit failed", "code": e.code}, run_id, tenant)
        return
    L.append("SIMULATED", {"what": "[SIMULATED] platform fee credit", "amount": str(amount), "currency": "GBP",
                           "reference": transfer_id}, run_id, tenant)
