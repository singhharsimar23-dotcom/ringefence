"""P2 (balance debit timing across lifecycle), P7 (lookup by request_id), P10 (pagination, created-at filter)."""
import json
import time
from decimal import Decimal as D

from ringfence.awx import Awx, AwxError

k = Awx().for_tenant("kestrel")
J = lambda x, n=500: json.dumps(x, default=str)[:n]
body = {"nickname": "probe-US", "transfer_methods": ["LOCAL"], "beneficiary": {
    "entity_type": "PERSONAL", "first_name": "Test", "last_name": "Payee",
    "address": {"country_code": "US", "city": "New York", "street_address": "1 Broadway", "postcode": "10004", "state": "NY"},
    "bank_details": {"bank_country_code": "US", "account_currency": "USD", "account_name": "Test Payee",
                     "bank_name": "JPMorgan Chase", "account_routing_type1": "aba", "account_routing_value1": "021000021",
                     "account_number": "123456789", "bank_account_category": "Checking"}}}
resp = k.post("/beneficiaries/create", body)
bid = resp.get("beneficiary_id") or resp["id"]
print("create keys", sorted(resp))
bal = lambda: k.balances().get("USD")
print("USD before", bal())
rid = "rf-probe-p2-" + str(int(time.time()))
tr = {"request_id": rid, "beneficiary_id": bid, "transfer_amount": D("1.00"), "transfer_currency": "USD",
      "source_currency": "USD", "transfer_method": "LOCAL", "reason": "professional_business_services", "reference": "RF PROBE"}
t = k.post_money("/transfers/create", tr)
tid = t["id"]
print("created", t["status"], "keys", sorted(t))
print("USD after create", bal())
for nxt in ("SENT", "PAID"):
    r = k.post(f"/simulation/transfers/{tid}/transition", {"next_status": nxt})
    print(nxt, r.get("status"), "USD", bal())
print("P7 lookup by request_id:", J(k.get("/transfers", {"request_id": rid})))
print("P7 get by id:", J(k.get(f"/transfers/{tid}"), 300))
r = k.post(f"/simulation/transfers/{tid}/transition", {"next_status": "FAILED", "failure_type": "BENEFICIARY_BANK_RETURNED"})
print("FAILED", r.get("status"), r.get("failure_type"), "USD", bal())
print("after-fail transfer:", J(k.get(f"/transfers/{tid}"), 400))
# P10
page = k.get("/transfers", {"page_num": 0, "page_size": 10})
print("P10 transfers page keys", sorted(page), "n", len(page.get("items", [])), {x: page[x] for x in page if x != "items"})
bl = k.get("/beneficiaries")
print("P10 beneficiaries keys", sorted(bl), "first item keys", sorted(bl["items"][0]))
for fmt in ("2026-11-03T00:00:00+0000", "2026-11-03T00:00:00Z", "2026-11-03"):
    try:
        x = k.get("/transfers", {"from_created_at": fmt, "page_num": 0, "page_size": 10})
        print("from_created_at", fmt, "->", len(x["items"]))
    except AwxError as e:
        print("from_created_at", fmt, "ERR", e.status, e.code, e.message[:120])
