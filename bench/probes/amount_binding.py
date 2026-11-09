"""Theme-A on the AMOUNT axis: does Airwallex bind the amount a human approves, or can two
amount fields disagree and it silently moves one of them?
A transfer accepts source_amount and transfer_amount. If you send BOTH with a conflict and it
accepts (instead of rejecting), then "the number a human approved" and "the number that moves"
can differ with the same transfer object -- the same pointer-vs-content gap, on the amount.
Live, Kestrel's OWN account, GBP same-currency, every amount <= 5, PRB- payee, cancel + delete in finally.
  T0 only transfer_amount=1           -> baseline, what moved?
  T1 both, transfer_amount=1 source_amount=5 (same ccy, conflict) -> reject? or silently pick one?
  T2 both, transfer_amount=5 source_amount=1 (conflict, other way)-> reject? or silently pick one?
  export MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8; uv run python bench/probes/amount_binding.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import awx as _env  # noqa: E402

for n in ("AWX_CLIENT_ID", "AWX_API_KEY", "AWX_BASE_URL", "AWX_EMPLOYER_A", "AWX_EMPLOYER_B", "AWX_EMPLOYER_C", "AWX_PLATFORM_ACCOUNT"):
    os.environ.setdefault(n, _env.env(n) or "")
from ringfence.awx import Awx, AwxError  # noqa: E402

TAG = f"PRB-amt-{int(time.time()) % 100000}"
ks = Awx().for_tenant("kestrel")
made: list[str] = []


def say(*a):
    print(*a, flush=True)


def call(f, *a):
    try:
        return f(*a)
    except AwxError as e:
        return {"_error": e.status, "code": e.code, "msg": str(e)[:200]}


def ben():
    p = {"nickname": f"{TAG}-x", "transfer_methods": ["LOCAL"], "beneficiary": {
        "entity_type": "PERSONAL", "first_name": "Amt", "last_name": "Probe",
        "address": {"country_code": "GB", "city": "London", "street_address": "1 Test St", "postcode": "EC1A 1BB"},
        "bank_details": {"bank_country_code": "GB", "account_currency": "GBP", "account_name": "Amt Probe",
                         "bank_name": "HSBC", "account_routing_type1": "sort_code",
                         "account_routing_value1": "040004", "account_number": "11112222"}}}
    return ks.post("/beneficiaries/create", p)["id"]


def create(bid, rid, **amt):
    r = call(ks.post_money, "/transfers/create", {
        "request_id": rid, "beneficiary_id": bid, "transfer_currency": "GBP", "source_currency": "GBP",
        "transfer_method": "LOCAL", "reason": "professional_business_services", "reference": TAG, **amt})
    if isinstance(r, dict) and r.get("id"):
        made.append(r["id"])
    return r


def amts(r):
    return {k: r.get(k) for k in ("status", "transfer_amount", "source_amount", "amount_beneficiary_receives")} if isinstance(r, dict) else r


def main():
    say(f"tag {TAG}")
    bid = ben()
    r0 = create(bid, f"{TAG}-t0", transfer_amount=Decimal("1.00"))
    say("T0 transfer_amount=1 :", json.dumps(amts(r0), default=str))
    r1 = create(bid, f"{TAG}-t1", transfer_amount=Decimal("1.00"), source_amount=Decimal("5.00"))
    say("T1 tf=1 src=5 (conflict):", json.dumps(amts(r1), default=str))
    r2 = create(bid, f"{TAG}-t2", transfer_amount=Decimal("5.00"), source_amount=Decimal("1.00"))
    say("T2 tf=5 src=1 (conflict):", json.dumps(amts(r2), default=str))

    def verdict(r, name):
        if not isinstance(r, dict) or r.get("_error"):
            return f"{name}: REJECTED ({(r or {}).get('code')}) - conflict is bound (good)"
        return f"{name}: ACCEPTED status={r.get('status')} moved transfer_amount={r.get('transfer_amount')} source_amount={r.get('source_amount')} - SILENTLY PICKED ONE"
    say("VERDICT", verdict(r1, "T1"))
    say("VERDICT", verdict(r2, "T2"))
    # self-check: baseline must create, or the probe is broken.
    assert isinstance(r0, dict) and r0.get("id"), f"baseline create failed: {r0}"
    say("self-check ok: baseline created", r0.get("id"))


def cleanup(bid=None):
    say("\n== cleanup")
    for tid in made:
        st = "?"
        for i in range(5):
            call(ks.post, f"/transfers/{tid}/cancel", {})
            st = ks.get(f"/transfers/{tid}").get("status")
            if st in ("CANCELLED", "FAILED"):
                break
            time.sleep(3 * (i + 1))
        else:
            call(ks.post, f"/simulation/transfers/{tid}/transition", {"status": "FAILED"})
            st = ks.get(f"/transfers/{tid}").get("status")
        say("transfer", tid, st)
    if bid:
        call(ks.post, f"/beneficiaries/{bid}/delete", {})
        say("payee deleted", bid)


if __name__ == "__main__":
    _bid = None
    try:
        _bid = ben.__wrapped__ if False else None  # keep linter quiet; real bid created in main via closure below
        main()
    except AssertionError as e:
        say("SELF-CHECK FAILED:", e)
    except Exception as e:  # noqa: BLE001
        say(f"harness error {type(e).__name__}: {e}")
    finally:
        # payees created in main aren't visible here; delete any PRB-amt payee left behind
        for b in ks.get("/beneficiaries", {"page_num": 0, "page_size": 100}).get("items", []):
            if str(b.get("nickname", "")).startswith(TAG):
                call(ks.post, f"/beneficiaries/{b['id']}/delete", {})
                say("payee deleted", b["id"])
        cleanup()
