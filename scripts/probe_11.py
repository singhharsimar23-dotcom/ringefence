"""P11: platform fee beneficiary on all employers + USD GA on Kestrel. P5b: employer-token conversion (Northwind GBP->AUD)."""
import json
import time
from decimal import Decimal as D

from ringfence.awx import Awx, AwxError

a = Awx()
J = lambda x, n=400: json.dumps(x, default=str)[:n]
fee = {"nickname": "Ringfence fee", "transfer_methods": ["LOCAL"], "beneficiary": {
    "entity_type": "COMPANY", "company_name": "Ringfence Platform",
    "address": {"country_code": "GB", "city": "London", "street_address": "1 Fee St", "postcode": "EC1A 1BB"},
    "bank_details": {"bank_country_code": "GB", "account_currency": "GBP", "account_name": "Ringfence Platform",
                     "bank_name": "Barclays", "account_routing_type1": "sort_code", "account_routing_value1": "041907",
                     "account_number": "07371376"}}}
for t in ("kestrel", "harbour"):
    c = a.for_tenant(t)
    try:
        c.post("/beneficiaries/validate", fee)
        r = c.post("/beneficiaries/create", fee)
        print(t, "fee beneficiary", r["id"])
    except AwxError as e:
        print(t, "fee ERR", e.status, e.code, e.message[:200], J(e.details))
k = a.for_tenant("kestrel")
for feats in ([{"currency": "USD", "transfer_method": "ACH"}], [{"currency": "USD"}]):
    try:
        ga = k.post("/global_accounts/create", {"request_id": "rf-probe-ga-us-" + str(int(time.time())),
                                                "country_code": "US", "nick_name": "Kestrel USD", "required_features": feats})
        print("GA", J(ga, 600))
        break
    except AwxError as e:
        print("GA ERR", feats, e.status, e.code, e.message[:200], J(e.details))
n = a.for_tenant("northwind")
q = n.post("/fx/quotes/create", {"buy_currency": "AUD", "sell_currency": "GBP", "buy_amount": D("10.00"), "validity": "MIN_1"})
print("quote keys", sorted(q), "rate", q.get("client_rate"), "validity", q.get("validity"))
c = n.post("/fx/conversions/create", {"request_id": "rf-probe-fx-" + str(int(time.time())), "buy_currency": "AUD",
                                      "sell_currency": "GBP", "buy_amount": D("10.00"), "quote_id": q["quote_id"]})
print("conversion", J(c, 500))
print("Northwind AUD", n.balances().get("AUD"))
