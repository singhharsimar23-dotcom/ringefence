"""Does an approved FX quote_id bind the amount and currency the conversion settles?
A candidate 4th pointer for the thesis: approve a quote_id, money follows the amount/currency in the body.
Live, Kestrel's OWN account (EUR/GBP/HKD, all pre-funded), same-account conversions, every amount <= 5.
Quotes are MULTI_USE (PROBES.md P5). convert() sends BOTH a quote_id and an amount (ringfence/fx.py:32-37).

  T0 baseline     quote EUR->GBP buy 1, convert buy 1                  -> SETTLED, record locked rate
  T1 amount       reuse that quote_id, convert buy 5                   -> settles 5 at the locked 1-unit rate?
  T2 currency     reuse that quote_id, convert buy_currency=HKD        -> honors quote GBP, or follows body HKD?
  T3 expired      fresh quote (validity MIN_1), wait 65s, convert      -> still settles on an expired quote?

A conversion can't be cancelled; these are tiny same-account moves inside our own test account B.
  export MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8; uv run python bench/probes/fx_quote_binding.py
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

TAG = f"PRB-fx-{int(time.time()) % 100000}"
ks = Awx().for_tenant("kestrel")
made: list[str] = []  # conversion_ids, for the receipt


def say(*a):
    print(*a, flush=True)


def call(f, *a):
    try:
        return f(*a)
    except AwxError as e:
        return {"_error": e.status, "code": e.code, "msg": str(e)[:200], "details": e.details}


def convert_raw(rid, quote_id, sell, buy, **amt):
    """Conversion with an explicit amount/currency, so we can mismatch it against the quote on purpose."""
    r = call(ks.post, "/fx/conversions/create",
             {"request_id": rid, "quote_id": quote_id, "sell_currency": sell, "buy_currency": buy, **amt})
    if isinstance(r, dict) and r.get("conversion_id"):
        made.append(r["conversion_id"])
    return r


def settled(r):
    return isinstance(r, dict) and r.get("status") == "SETTLED"


def rate_of(r):
    try:
        return (Decimal(str(r["sell_amount"])) / Decimal(str(r["buy_amount"]))).quantize(Decimal("0.000001"))
    except Exception:  # noqa: BLE001
        return None


def main():
    say(f"tag {TAG}")
    # T0 baseline: quote EUR->GBP for buy 1, convert the matching amount.
    qt = get_quote(ks, "EUR", "GBP", buy_amount=Decimal("1"))
    say("T0 quote", qt.quote_id, f"sell EUR {qt.sell_amount} -> buy GBP {qt.buy_amount} @ {qt.rate}")
    r0 = convert_raw(f"{TAG}-t0", qt.quote_id, "EUR", "GBP", buy_amount=Decimal("1"))
    say("T0 convert buy 1 :", r0.get("status", r0), "settled_rate", rate_of(r0))
    base_ok = settled(r0)

    # T1 amount unbinding: SAME quote_id, ask for 5 instead of 1.
    r1 = convert_raw(f"{TAG}-t1", qt.quote_id, "EUR", "GBP", buy_amount=Decimal("5"))
    locked = settled(r1) and rate_of(r1) == qt.rate
    say(f"T1 amount buy 5 : {r1.get('status', r1)} settled_rate {rate_of(r1)} quoted_rate {qt.rate}")
    say("T1 VERDICT:", "UNBOUND - settled 5 at the 1-unit locked rate" if locked
        else ("settled at a DIFFERENT rate (re-priced)" if settled(r1) else f"rejected ({r1.get('code')}) - amount is bound"))

    # T2 currency unbinding: SAME EUR->GBP quote_id, but ask to buy HKD.
    r2 = convert_raw(f"{TAG}-t2", qt.quote_id, "EUR", "HKD", buy_amount=Decimal("1"))
    say(f"T2 currency ->HKD: {r2.get('status', r2)} buy_ccy {r2.get('buy_currency')} settled_rate {rate_of(r2)}")
    say("T2 VERDICT:", "UNBOUND - quote currency ignored, followed body HKD" if settled(r2) and r2.get("buy_currency") == "HKD"
        else ("settled as quoted GBP (body ignored)" if settled(r2) else f"rejected ({r2.get('code')}) - currency is bound"))

    # T3 expired validity: fresh MIN_1 quote, let it expire, then convert.
    qt3 = get_quote(ks, "EUR", "GBP", buy_amount=Decimal("1"))
    say("T3 quote", qt3.quote_id, "validity MIN_1; sleeping 65s")
    time.sleep(65)
    r3 = convert_raw(f"{TAG}-t3", qt3.quote_id, "EUR", "GBP", buy_amount=Decimal("1"))
    say(f"T3 expired : {r3.get('status', r3)}")
    say("T3 VERDICT:", "accepts an EXPIRED quote" if settled(r3) else f"rejected ({r3.get('code')}) - validity enforced")

    say("\nconversion receipts:", made)
    # self-check: the baseline must settle, or the probe is broken and the other verdicts are meaningless.
    assert base_ok, f"baseline conversion did not settle: {r0}"
    say("self-check ok: baseline settled")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        say("SELF-CHECK FAILED:", e)
    except Exception as e:  # noqa: BLE001
        say(f"harness error {type(e).__name__}: {e}")
