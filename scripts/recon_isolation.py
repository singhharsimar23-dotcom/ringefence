"""Live check: per-employer tokens are isolated; AUD wallet + employer->platform fee path."""
import json
import sys
import uuid

import httpx

sys.path.insert(0, "scripts")
import awx  # noqa: E402

E = {k: awx.env(f"AWX_EMPLOYER_{k}") for k in "ABC"}
PLATFORM = awx.env("AWX_PLATFORM_ACCOUNT")
RUN = uuid.uuid4().hex[:8]


def req(method, path, tok, body=None, obo=None):
    h = {"Authorization": f"Bearer {tok}", **({"x-on-behalf-of": obo} if obo else {})}
    r = httpx.request(method, f"{awx.BASE}/api/v1{path}", headers=h, json=body, timeout=60)
    try:
        return r.status_code, r.json()
    except ValueError:
        return r.status_code, r.text[:200]


tok = {k: awx.token(v) for k, v in {**E, "P": PLATFORM}.items()}

print("## balances per account (non-zero)")
for k, t in tok.items():
    c, d = req("GET", "/balances/current", t)
    print(k, c, [(b["currency"], b["available_amount"]) for b in d if b["total_amount"]] if c == 200 else d)

print("\n## cross-tenant attempts with Employer A's token")
for label, obo in (("obo B", E["B"]), ("obo platform", PLATFORM)):
    print(label, *req("GET", "/balances/current", tok["A"], obo=obo))

print("\n## Employer A global accounts")
c, d = req("GET", "/global_accounts", tok["A"])
print(c, [(g["id"], g["country_code"], g["status"]) for g in d.get("items", [])] if c == 200 else d)

print("\n## Employer C: create AUD global account")
c, ga = req("POST", "/global_accounts/create", tok["C"], {"request_id": str(uuid.uuid4()), "country_code": "AU",
                                                          "nick_name": "Harbour payroll float AUD",
                                                          "required_features": [{"currency": "AUD", "transfer_method": "LOCAL"}]})
print(c, json.dumps(ga)[:400])
if c < 300:
    c, dep = req("POST", "/simulation/deposit/create", tok["C"], {"global_account_id": ga["id"], "amount": 3000, "payer_name": "Harbour Foods payroll float"})
    print("deposit", c, json.dumps(dep)[:200])
    c, d = req("GET", "/balances/current", tok["C"])
    print("C AUD now", [b for b in d if b["currency"] == "AUD"])

print("\n## Platform GBP global account details (fee destination)")
c, d = req("GET", "/global_accounts", tok["P"])
g = d["items"][0]
print(g["account_number"], [r for f in g["supported_features"] for r in f.get("routing_codes", [])][:2])

print("\n## Employer A: beneficiary = platform GBP account, then fee transfer")
ben = {"nickname": "Ringfence platform fees", "transfer_methods": ["LOCAL"],
       "beneficiary": {"entity_type": "COMPANY", "company_name": "Sandbox Business",
                       "address": {"country_code": "GB", "city": "London", "street_address": "15-19 Bloomsbury Way", "postcode": "WC1A 2TH"},
                       "bank_details": {"bank_country_code": "GB", "account_currency": "GBP", "account_name": "Sandbox Business",
                                        "bank_name": "Airwallex", "account_routing_type1": "sort_code",
                                        "account_routing_value1": "041907", "account_number": g["account_number"]}}}
c, b = req("POST", "/beneficiaries/create", tok["A"], ben)
print("beneficiary", c, json.dumps(b)[:300])
if c < 300:
    c, t = req("POST", "/transfers/create", tok["A"], {"request_id": f"fee-{RUN}-A", "beneficiary_id": b["id"], "transfer_amount": 25,
                                                       "transfer_currency": "GBP", "source_currency": "GBP", "transfer_method": "LOCAL",
                                                       "reason": "professional_business_services", "reference": f"Ringfence fee {RUN}"})
    print("fee transfer", c, json.dumps({k: t.get(k) for k in ("id", "status", "code", "message")} if isinstance(t, dict) else t))

print("\n## Employer B can see Employer A's beneficiaries?")
c, d = req("GET", "/beneficiaries", tok["B"])
print(c, "B beneficiary count:", len(d.get("items", [])) if c == 200 else d)
