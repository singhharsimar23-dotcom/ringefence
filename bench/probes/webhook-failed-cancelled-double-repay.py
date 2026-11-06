"""Live: does one bank return produce FAILED and then an automatic CANCELLED (two terminal states, so two webhook
events with different ids), and what does the transfer look like after the auto-cancel? Kestrel only.
  A  GBP->GBP 1.00 LOCAL: SENT, PAID, FAILED(BENEFICIARY_BANK_RETURNED); poll 0.5 s; balances before/after.
  B  USD->EUR 2.00 LOCAL (FX variant, H25): same lifecycle; which currency does the refund land in?
Everything this script creates is cancelled/deleted at the end; final statuses printed.
  uv run python bench/probes/webhook-failed-cancelled-double-repay.py"""
from __future__ import annotations

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

EPOCH = int(time.time())
TAG = "PRB-webhook-failed-cancelled-double-repay-"
ks = Awx().for_tenant("kestrel")
made_t: list[str] = []
made_b: list[str] = []
FIELDS = ("status", "failure_type", "failure_reason", "updated_at", "amount_beneficiary_receives", "source_amount")


def say(*a):
    print(*a, flush=True)


def call(f, *a):
    try:
        return f(*a)
    except AwxError as e:
        return {"_error": e.status, "code": e.code, "msg": str(e)[:200]}


def bal(ccys):
    b = ks.balances()
    return {c: b.get(c, Decimal(0)) for c in ccys}


def make_ben(nick, ccy, bank):
    p = {"nickname": TAG + nick, "transfer_methods": ["LOCAL"], "beneficiary": {
        "entity_type": "PERSONAL", "first_name": "Wh", "last_name": "Probe",
        "address": {"country_code": bank["bank_country_code"], "city": "City", "street_address": "1 Test St",
                    "postcode": "10117" if ccy == "EUR" else "EC1A 1BB"},
        "bank_details": {"account_currency": ccy, "account_name": "Wh Probe", **bank}}}
    v = call(ks.post, "/beneficiaries/validate", p)
    say("validate", nick, "ok" if "_error" not in (v or {}) else v)
    bid = ks.post("/beneficiaries/create", p)["id"]
    made_b.append(bid)
    return bid


def lifecycle(label, bid, src, dst, amt, watch):
    say(f"\n== {label}: {src}->{dst} {amt}")
    b0 = bal(watch)
    rid = f"prb-wh{label.lower()}-{EPOCH}"
    t = call(ks.post_money, "/transfers/create", {
        "request_id": rid, "beneficiary_id": bid, "source_currency": src, "transfer_currency": dst,
        "transfer_amount": Decimal(amt), "transfer_method": "LOCAL", "reason": "professional_business_services",
        "reference": f"PRB WH {label}"})
    if "_error" in t:
        return say("create", t)
    tid = t["id"]
    made_t.append(tid)
    say("created", tid, t["status"], "source_amount", t.get("source_amount"), "request_id", rid)
    b1 = bal(watch)
    paid_snapshot = None
    for st, kw in (("SENT", {}), ("PAID", {}), ("FAILED", {"failure_type": "BENEFICIARY_BANK_RETURNED"})):
        r = call(ks.post, f"/simulation/transfers/{tid}/transition", {"next_status": st, **kw})
        say(f"sim -> {st}:", r.get("_error") or r.get("status"), r.get("code", ""))
        if st == "PAID":
            paid_snapshot = ks.get(f"/transfers/{tid}")  # what a stale payout.transfer.paid would carry
    t0, seen, cancelled_at = time.monotonic(), [], None
    while time.monotonic() - t0 < 30:
        g = ks.get(f"/transfers/{tid}")
        row = tuple(str(g.get(f)) for f in FIELDS)
        if not seen or seen[-1][1] != row:
            seen.append((round(time.monotonic() - t0, 2), row))
            say(f"  t+{seen[-1][0]:>5}s", dict(zip(FIELDS, row)))
        if g.get("status") == "CANCELLED" and cancelled_at is None:
            cancelled_at = time.monotonic() - t0
        if cancelled_at is not None and time.monotonic() - t0 > cancelled_at + 3:
            break
        time.sleep(0.5)
    b2 = bal(watch)
    say("CANCELLED appeared after", f"{cancelled_at:.2f}s" if cancelled_at is not None else "never (30 s)")
    say("paid snapshot status", paid_snapshot.get("status") if paid_snapshot else None)
    for c in watch:
        say(f"balance {c}: before {b0[c]} after-create {b1[c]} after-terminal {b2[c]} "
            f"(create delta {b1[c] - b0[c]}, refund delta {b2[c] - b1[c]})")
    say("transfer row: source_amount", g.get("source_amount"), "transfer_amount", g.get("transfer_amount"),
        "fee", g.get("fee_amount"), g.get("fee_currency"))
    return tid


def cleanup():
    say("\n== cleanup")
    for tid in made_t:
        st = call(ks.get, f"/transfers/{tid}").get("status")
        if st not in ("CANCELLED", "FAILED"):
            for i in range(3):
                r = call(ks.post, f"/transfers/{tid}/cancel", f"cancel {tid}")
                st = call(ks.get, f"/transfers/{tid}").get("status")
                if st == "CANCELLED":
                    break
                time.sleep(2 ** i)
            if st != "CANCELLED":
                call(ks.post, f"/simulation/transfers/{tid}/transition", {"next_status": "FAILED"})
                st = call(ks.get, f"/transfers/{tid}").get("status")
        say("transfer", tid, "final", st)
    for bid in made_b:
        r = call(ks.post, f"/beneficiaries/{bid}/delete", {})
        say("beneficiary", bid, "delete", "ok" if not (isinstance(r, dict) and "_error" in r) else r)


if __name__ == "__main__":
    try:
        gb = make_ben("gb", "GBP", {"bank_country_code": "GB", "bank_name": "HSBC", "account_routing_type1": "sort_code",
                                    "account_routing_value1": "040004", "account_number": "31415926"})
        lifecycle("A", gb, "GBP", "GBP", "1.00", ("GBP",))
        de = make_ben("de", "EUR", {"bank_country_code": "DE", "bank_name": "Commerzbank",
                                    "iban": "DE89370400440532013000", "swift_code": "COBADEFFXXX"})
        lifecycle("B", de, "USD", "EUR", "2.00", ("USD", "EUR"))
    finally:
        cleanup()
