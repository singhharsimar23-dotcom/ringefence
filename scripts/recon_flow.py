"""End-to-end sandbox recon of the payroll money path. Prints compact results per step."""
import datetime as dt
import json
import sys
import uuid

sys.path.insert(0, "scripts")
from awx import call  # noqa: E402

RUN = uuid.uuid4().hex[:8]
US_LOCAL_BEN = "bf408d15-205a-4673-bdba-9157a08f2d3c"  # seeded sandbox beneficiary


def show(step, code, data, keys=None):
    if isinstance(data, dict) and keys and code < 300:
        data = {k: data.get(k) for k in keys}
    print(f"\n## {step} -> HTTP {code}\n{json.dumps(data)[:700]}")
    return data


def transfer(rid, **extra):
    body = {"request_id": rid, "beneficiary_id": US_LOCAL_BEN, "transfer_amount": 125.50,
            "transfer_currency": "USD", "source_currency": "USD", "transfer_method": "LOCAL",
            "reason": "wages_salary", "reference": f"payroll {RUN}", **extra}
    return call("POST", "/transfers/create", body)


K = ["id", "status", "request_id", "transfer_date", "amount_beneficiary_receives", "failure_reason", "failure_type", "code", "message"]

# 1. beneficiary validate (GB GBP LOCAL)
ben = {"beneficiary": {"entity_type": "PERSONAL", "first_name": "Ada", "last_name": "Contractor",
                       "address": {"country_code": "GB", "city": "London", "street_address": "1 High St", "postcode": "EC1A 1BB"},
                       "bank_details": {"bank_country_code": "GB", "account_currency": "GBP", "account_name": "Ada Contractor",
                                        "bank_name": "NatWest", "account_routing_type1": "sort_code",
                                        "account_routing_value1": "601613", "account_number": "31926819"}},
       "transfer_methods": ["LOCAL"]}
show("beneficiary validate GB", *call("POST", "/beneficiaries/validate", ben))

# 2. transfer + idempotent retry with same request_id
rid = f"pay-{RUN}-emp1-c1"
c, t = transfer(rid)
t = show("transfer create", c, t, K)
c, t2 = transfer(rid)
show("SAME request_id retry", c, t2, K)
c, t3 = transfer(f"pay-{RUN}-emp1-c1", transfer_amount=999)
show("SAME request_id, DIFFERENT amount", c, t3, K)

# 3. status machine incl. FAILED after PAID
tid = t.get("id")
for s in ("SENT", "PAID", "FAILED"):
    body = {"next_status": s}
    if s == "FAILED":
        body["failure_type"] = "BENEFICIARY_BANK_RETURNED"
    show(f"simulate -> {s}", *call("POST", f"/simulation/transfers/{tid}/transition", body), K)

# 4. scheduled transfer (future date)
tomorrow = (dt.date.today() + dt.timedelta(days=1)).isoformat()
c, st = transfer(f"pay-{RUN}-sched-01", transfer_date=tomorrow)
st = show("scheduled transfer", c, st, K)
if st.get("id"):
    show("simulate scheduled -> OVERDUE", *call("POST", f"/simulation/transfers/{st['id']}/transition", {"next_status": "OVERDUE"}), K)

# 5. deposit simulate + reverse
c, d = call("POST", "/simulation/deposit/create", {"global_account_id": "50317107-2330-4e33-8c74-2285042d16b6", "amount": 1000, "payer_name": "Employer A funding"})
d = show("deposit simulate", c, d, ["id", "status", "amount", "currency"])
if d.get("id"):
    show("deposit settle", *call("POST", f"/simulation/deposits/{d['id']}/settle", {}), ["id", "status"])
    show("deposit reverse", *call("POST", f"/simulation/deposits/{d['id']}/reverse", {}), ["id", "status"])

# 6. FX quote + conversion
c, q = call("POST", "/fx/quotes/create", {"buy_currency": "GBP", "sell_currency": "USD", "buy_amount": 500, "validity": "MIN_1"})
q = show("fx quote", c, q, ["quote_id", "client_rate", "buy_amount", "sell_amount", "validity"])
c, cv = call("POST", "/fx/conversions/create", {"request_id": f"fx-{RUN}-0001", "buy_currency": "GBP", "sell_currency": "USD", "buy_amount": 500, **({"quote_id": q["quote_id"]} if q.get("quote_id") else {})})
show("fx conversion", c, cv, ["conversion_id", "status", "client_rate", "buy_amount", "sell_amount"])

# 7. batch transfer
c, b = call("POST", "/batch_transfers/create", {"request_id": f"batch-{RUN}-01", "name": f"payroll {RUN}"})
b = show("batch create", c, b, ["id", "status", "request_id"])
if b.get("id"):
    item = {"request_id": f"bi-{RUN}-0001", "beneficiary_id": US_LOCAL_BEN, "transfer_amount": 10,
            "transfer_currency": "USD", "source_currency": "USD", "transfer_method": "LOCAL", "reason": "wages_salary", "reference": "batch item"}
    show("batch add_items", *call("POST", f"/batch_transfers/{b['id']}/add_items", {"items": [item]}))
    show("batch submit", *call("POST", f"/batch_transfers/{b['id']}/submit", {"request_id": f"bsub-{RUN}-01"}), ["id", "status"])
