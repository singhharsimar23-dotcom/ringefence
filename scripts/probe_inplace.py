"""Probe: can a beneficiary's bank details be changed IN PLACE (same id), and does that redirect transfers?
Runs on Northwind (Employer A) (throwaway beneficiary, GBP 1 transfers, all cancelled, beneficiary deleted).
Northwind Proof shows FAIL for these (no ledger intent) until the next reset: detection working. Prints ids, statuses and last-4 digits only."""
import copy
import sys
import time

sys.path.insert(0, "scripts")
import awx  # noqa: E402

P = awx.env("AWX_EMPLOYER_A")  # the platform account cannot send (fee_unknown); Northwind can
BEN = {"entity_type": "PERSONAL", "first_name": "Ada", "last_name": "Probe",
       "address": {"country_code": "GB", "city": "London", "street_address": "1 Test St", "postcode": "EC1A 1BB"},
       "bank_details": {"bank_country_code": "GB", "account_currency": "GBP", "account_name": "Ada Probe", "bank_name": "HSBC",
                        "account_routing_type1": "sort_code", "account_routing_value1": "040004", "account_number": "12345678"}}
STAMP = str(int(time.time()))


def last4(t):
    return t["beneficiary"]["bank_details"]["account_number"][-4:]


def transfer(bid, n):
    code, t = awx.call("POST", "/transfers/create", {
        "request_id": f"probe-inplace-{STAMP}-{n}", "beneficiary_id": bid, "transfer_amount": 1, "transfer_currency": "GBP",
        "source_currency": "GBP", "transfer_method": "LOCAL", "reason": "professional_business_services",
        "reference": "probe in-place"}, P)
    assert code == 201, (code, t)
    return t


code, b = awx.call("POST", "/beneficiaries/create", {"nickname": f"probe-inplace-{STAMP}", "transfer_methods": ["LOCAL"],
                                                      "beneficiary": BEN}, P)
assert code == 201, (code, b)
bid = b["id"]
print("1 beneficiary created     ", code, bid, "acct ..", b["beneficiary"]["bank_details"]["account_number"][-4:])
t1 = transfer(bid, 1)
print("2 transfer T1 created     ", t1["status"], t1["id"], "pays acct ..", last4(t1))

mule = copy.deepcopy(BEN)
mule["bank_details"].update(account_number="99999901", account_routing_value1="200000", bank_name="Barclays")
code, _ = awx.call("POST", f"/beneficiaries/{bid}/update", {"transfer_methods": ["LOCAL"], "beneficiary": mule}, P)
code2, g = awx.call("GET", f"/beneficiaries/{bid}", None, P)
print("3 beneficiary UPDATED     ", code, "same id:", g["id"] == bid, "now acct ..", g["beneficiary"]["bank_details"]["account_number"][-4:],
      "name still:", g["beneficiary"]["bank_details"]["account_name"])

t2 = transfer(bid, 2)
print("4 transfer T2, SAME id    ", t2["status"], t2["id"], "pays acct ..", last4(t2))
_, t1b = awx.call("GET", f"/transfers/{t1['id']}", None, P)
print("5 T1 re-read after update ", t1b["status"], "pays acct ..", last4(t1b), "(scheduled transfers keep their snapshot)"
      if last4(t1b) == last4(t1) else "(REDIRECTED: the snapshot follows the pointer)")

for t in (t1, t2):
    code, c = awx.call("POST", f"/transfers/{t['id']}/cancel", {}, P)
    print("  cleanup cancel", t["id"][:8], code, c.get("status") if isinstance(c, dict) else c[:80])
code, _ = awx.call("POST", f"/beneficiaries/{bid}/delete", None, P)
print("  cleanup delete beneficiary", code)
