"""P4: validate corridor payloads (AU BSB, DE EUR LOCAL/SWIFT, US ABA) under the right tenant tokens."""
import copy
import json

from ringfence.awx import Awx, AwxError

a = Awx()


def payload(country, ccy, bank, method="LOCAL", first="Test", last="Payee", addr=None):
    return {"nickname": f"probe-{country}-{method}", "transfer_methods": [method], "beneficiary": {
        "entity_type": "PERSONAL", "first_name": first, "last_name": last,
        "address": addr or {"country_code": country, "city": "City", "street_address": "1 Main St", "postcode": "2000", "state": "NSW"},
        "bank_details": {"bank_country_code": country, "account_currency": ccy, "account_name": f"{first} {last}", **bank}}}


cases = {
    "AU_bsb": ("harbour", payload("AU", "AUD", {"bank_name": "Commonwealth Bank", "account_routing_type1": "bsb",
                                                 "account_routing_value1": "062000", "account_number": "12345678"})),
    "DE_EUR_LOCAL_iban": ("northwind", payload("DE", "EUR", {"bank_name": "Commerzbank", "iban": "DE89370400440532013000",
                                                              "swift_code": "COBADEFFXXX"},
                                                addr={"country_code": "DE", "city": "Berlin", "street_address": "1 Strasse", "postcode": "10115"})),
    "DE_EUR_SWIFT_iban": ("northwind", payload("DE", "EUR", {"bank_name": "Commerzbank", "iban": "DE89370400440532013000",
                                                              "swift_code": "COBADEFFXXX"}, method="SWIFT",
                                                addr={"country_code": "DE", "city": "Berlin", "street_address": "1 Strasse", "postcode": "10115"})),
    "US_aba": ("kestrel", payload("US", "USD", {"bank_name": "JPMorgan Chase", "account_routing_type1": "aba",
                                                 "account_routing_value1": "021000021", "account_number": "123456789",
                                                 "bank_account_category": "Checking"},
                                   addr={"country_code": "US", "city": "New York", "street_address": "1 Broadway", "postcode": "10004", "state": "NY"})),
}
for name, (tenant, body) in cases.items():
    try:
        r = a.for_tenant(tenant).post("/beneficiaries/validate", copy.deepcopy(body))
        print(name, "OK", json.dumps(r)[:200])
    except AwxError as e:
        print(name, "ERR", e.status, e.code, e.message[:300], json.dumps(e.details)[:300])
