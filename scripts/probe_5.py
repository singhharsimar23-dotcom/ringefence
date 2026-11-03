"""P5: FX quote + conversion under employer tokens; does a quote accept sell_amount (needed for the exact AUD drain)?
Usage: probe_5.py quote|drain. 'quote' only quotes (no money moves); 'drain' sells ALL Harbour AUD -> USD."""
import json
import sys
import uuid
from decimal import Decimal

from ringfence.awx import Awx, AwxError

a = Awx()
mode = sys.argv[1] if len(sys.argv) > 1 else "quote"
h = a.for_tenant("harbour")
out = {}
try:
    bal = h.balances().get("AUD", Decimal(0))
    out["harbour_aud_before"] = str(bal)
    q = h.post("/fx/quotes/create", {"sell_currency": "AUD", "buy_currency": "USD", "sell_amount": bal,
                                     "validity": "MIN_1"})
    out["sell_amount_quote"] = {k: str(v) for k, v in q.items()}
    if mode == "drain" and bal > 0:
        c = h.post("/fx/conversions/create", {"request_id": f"drain-{uuid.uuid4().hex[:16]}", "quote_id": q["quote_id"],
                                              "buy_currency": "USD", "sell_currency": "AUD", "sell_amount": bal})
        out["conversion"] = {k: str(v) for k, v in c.items()}
        out["harbour_aud_after"] = str(h.balances().get("AUD", Decimal(0)))
except AwxError as e:
    out["error"] = {"status": e.status, "code": e.code, "message": e.message, "details": e.details}
n = a.for_tenant("northwind")
try:
    q = n.post("/fx/quotes/create", {"sell_currency": "GBP", "buy_currency": "AUD", "buy_amount": Decimal("10.00"),
                                     "validity": "MIN_1"})
    out["northwind_gbp_aud_buy_quote"] = {k: str(v) for k, v in q.items()}
except AwxError as e:
    out["northwind_error"] = {"status": e.status, "code": e.code, "message": e.message}
print(json.dumps(out, indent=1))
