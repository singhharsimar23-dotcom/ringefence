"""P1: AU beneficiary on Harbour; insufficient-funds behaviour and whether a rejected create burns the request_id."""
import json
from decimal import Decimal as D

from ringfence.awx import Awx, AwxError

h = Awx().for_tenant("harbour")
body = {"nickname": "probe-AU", "transfer_methods": ["LOCAL"], "beneficiary": {
    "entity_type": "PERSONAL", "first_name": "Test", "last_name": "Payee",
    "address": {"country_code": "AU", "city": "Sydney", "street_address": "1 Main St", "postcode": "2000", "state": "AU-NSW"},
    "bank_details": {"bank_country_code": "AU", "account_currency": "AUD", "account_name": "Test Payee",
                     "bank_name": "Commonwealth Bank", "account_routing_type1": "bsb",
                     "account_routing_value1": "062000", "account_number": "12345678"}}}
try:
    print("validate", h.post("/beneficiaries/validate", body))
    resp = h.post("/beneficiaries/create", body); print("create resp", json.dumps(resp, default=str)[:400]); bid = resp.get("beneficiary_id") or resp["id"]
    print("beneficiary", bid)
except AwxError as e:
    raise SystemExit(f"ben ERR {e.status} {e.code} {json.dumps(e.details)[:400]}")
print("AUD balance", h.balances().get("AUD"))
rid = "rf-probe-p1-0000000001"
tr = {"request_id": rid, "beneficiary_id": bid, "transfer_amount": D("10.00"), "transfer_currency": "AUD",
      "source_currency": "AUD", "transfer_method": "LOCAL", "reason": "professional_business_services", "reference": "RF PROBE"}
try:
    print("create#1", json.dumps(h.post_money("/transfers/create", tr), default=str)[:300])
except AwxError as e:
    print("create#1 ERR", e.status, e.code, e.message[:200], json.dumps(e.details)[:200])
print("lookup by request_id", json.dumps(h.get("/transfers", {"request_id": rid}), default=str)[:300])
# fund AUD with a tiny conversion? no: just retry the same request_id after (not) funding to see if burned
try:
    print("create#2", json.dumps(h.post_money("/transfers/create", tr), default=str)[:300])
except AwxError as e:
    print("create#2 ERR", e.status, e.code, e.message[:200], json.dumps(e.details)[:200])
