"""P4a: required fields per corridor via POST /beneficiaries/schema."""
import json
import sys

from ringfence.awx import Awx, AwxError

a = Awx()
cases = [("harbour", "AU", "AUD", "LOCAL"), ("northwind", "DE", "EUR", "LOCAL"), ("northwind", "DE", "EUR", "SWIFT"),
         ("kestrel", "US", "USD", "LOCAL"), ("northwind", "GB", "GBP", "LOCAL")]
for tenant, country, ccy, method in cases:
    body = {"bank_country_code": country, "account_currency": ccy, "entity_type": "PERSONAL",
            "transfer_method": method}
    try:
        r = a.for_tenant(tenant).post("/beneficiaries/schema", body)
        print(tenant, country, ccy, method, json.dumps(r)[:1500])
    except AwxError as e:
        print(tenant, country, ccy, method, "ERR", e.status, e.code, e.message[:300])
