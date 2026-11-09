"""Can you create money from nothing on this sandbox -- i.e. can AIRWALLEX (not an employer) lose money?
Three value-creation classes, live on Kestrel's own account, GBP/EUR, amounts <= 5, everything cancelled:
  T1 negative transfer_amount   -> a debit that credits you?            expect: rejected
  T2 negative conversion amount -> same on the FX rail                  expect: rejected
  T3 cancel-refund accounting   -> create (debit), cancel (refund):     does the balance come back to EXACTLY
                                   the start, or more (double refund = money from nothing)?
Settlement risk (funds available before settled, then the deposit reverses) is noted but not run: CLAUDE.md
records /simulation/deposits/{id}/reverse returns 404 for global-account deposits, so the loss can't be
completed live -- only the precondition (a PENDING deposit is immediately spendable) is observable.
  export MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8; uv run python bench/probes/value_creation.py
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
from ringfence.fx import get_quote  # noqa: E402

TAG = f"PRB-val-{int(time.time()) % 100000}"
ks = Awx().for_tenant("kestrel")
made: list[str] = []


def say(*a):
    print(*a, flush=True)


def call(f, *a, **k):
    try:
        return f(*a, **k)
    except AwxError as e:
        return {"_error": e.status, "code": e.code, "msg": str(e)[:200]}


def ben():
    p = {"nickname": f"{TAG}-x", "transfer_methods": ["LOCAL"], "beneficiary": {
        "entity_type": "PERSONAL", "first_name": "Val", "last_name": "Probe",
        "address": {"country_code": "GB", "city": "London", "street_address": "1 Test St", "postcode": "EC1A 1BB"},
        "bank_details": {"bank_country_code": "GB", "account_currency": "GBP", "account_name": "Val Probe",
                         "bank_name": "HSBC", "account_routing_type1": "sort_code",
                         "account_routing_value1": "040004", "account_number": "11112222"}}}
    return ks.post("/beneficiaries/create", p)["id"]


def main():
    say(f"tag {TAG}")
    bid = ben()

    # T1 negative transfer amount
    r1 = call(ks.post_money, "/transfers/create", {
        "request_id": f"{TAG}-neg", "beneficiary_id": bid, "transfer_amount": Decimal("-1.00"),
        "transfer_currency": "GBP", "source_currency": "GBP", "transfer_method": "LOCAL",
        "reason": "professional_business_services", "reference": TAG})
    if isinstance(r1, dict) and r1.get("id"):
        made.append(r1["id"])
    say("T1 negative transfer:", "ACCEPTED (!!) " + r1["id"] if isinstance(r1, dict) and r1.get("id")
        else f"rejected ({r1.get('code')})")

    # T2 negative conversion amount
    try:
        qt = get_quote(ks, "EUR", "GBP", buy_amount=Decimal("1"))
        r2 = call(ks.post, "/fx/conversions/create", {
            "request_id": f"{TAG}-negfx", "quote_id": qt.quote_id, "sell_currency": "EUR",
            "buy_currency": "GBP", "buy_amount": Decimal("-1.00")})
    except AwxError as e:
        r2 = {"_error": e.status, "code": e.code}
    say("T2 negative conversion:", "ACCEPTED (!!)" if isinstance(r2, dict) and r2.get("conversion_id")
        else f"rejected ({r2.get('code')})")

    # T3 cancel-refund accounting: does a cancelled transfer refund EXACTLY what it debited?
    start = ks.balances().get("GBP")
    t = call(ks.post_money, "/transfers/create", {
        "request_id": f"{TAG}-ref", "beneficiary_id": bid, "transfer_amount": Decimal("2.00"),
        "transfer_currency": "GBP", "source_currency": "GBP", "transfer_method": "LOCAL",
        "reason": "professional_business_services", "reference": TAG})
    if not (isinstance(t, dict) and t.get("id")):
        say("T3 create failed:", t)
    else:
        made.append(t["id"])
        after_create = ks.balances().get("GBP")
        st = "?"
        for i in range(6):
            call(ks.post, f"/transfers/{t['id']}/cancel", {})
            st = ks.get(f"/transfers/{t['id']}").get("status")
            if st in ("CANCELLED", "FAILED"):
                break
            time.sleep(3 * (i + 1))
        time.sleep(3)
        after_cancel = ks.balances().get("GBP")
        say(f"T3 GBP start={start} after_create={after_create} after_cancel={after_cancel} (cancel status {st})")
        debited = (start - after_create) if (start is not None and after_create is not None) else None
        refunded = (after_cancel - after_create) if (after_cancel is not None and after_create is not None) else None
        say(f"T3 debited={debited} refunded={refunded}")
        if start is not None and after_cancel is not None:
            say("T3 VERDICT:", "BALANCE RESTORED EXACTLY (accounting correct)" if after_cancel == start
                else f"BALANCE OFF BY {after_cancel - start} (!! investigate)")

    say("\nsettlement-risk note: a PENDING global-account deposit is spendable immediately (CLAUDE.md), which"
        " is the precondition for a front-the-float loss, but /simulation/deposits/{id}/reverse 404s on GA"
        " deposits, so the loss cannot be completed live.")
    # self-check: the negative-amount rails must reject, or the sandbox is wide open and we'd want to know loudly.
    assert not (isinstance(r1, dict) and r1.get("id")), "negative transfer was ACCEPTED -- value creation!"
    say("self-check ok: negative transfer rejected")


def cleanup():
    say("\n== cleanup")
    for tid in made:
        st = "?"
        for i in range(5):
            call(ks.post, f"/transfers/{tid}/cancel", {})
            st = ks.get(f"/transfers/{tid}").get("status")
            if st in ("CANCELLED", "FAILED"):
                break
            time.sleep(3 * (i + 1))
        say("transfer", tid, st)
    for b in ks.get("/beneficiaries", {"page_num": 0, "page_size": 100}).get("items", []):
        if str(b.get("nickname", "")).startswith(TAG):
            call(ks.post, f"/beneficiaries/{b['id']}/delete", {})
            say("payee deleted", b["id"])


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        say("SELF-CHECK FAILED:", e)
    except Exception as e:  # noqa: BLE001
        say(f"harness error {type(e).__name__}: {e}")
    finally:
        cleanup()
