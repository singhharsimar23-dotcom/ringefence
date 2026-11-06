"""Probe: what is the namespace of a transfer request_id, the only thing that makes an agent's retry safe?
  1. Northwind and Kestrel (two of OUR accounts) create a transfer with the SAME request_id.
     Per account: both 201. Global: Kestrel gets duplicate_request_id, and details.id is Northwind's transfer.
  2. Northwind creates a transfer whose request_id is the example in Airwallex's own Create-a-Transfer docs, the id a
     model that has read those docs is likely to copy. A duplicate means someone already used it; we do not look it up.
GBP 1 transfers to throwaway beneficiaries, all cancelled, beneficiaries deleted. Prints ids and codes only.
Proof shows FAIL for these on both tenants (no ledger intent) until the next reset."""
import sys
import time

sys.path.insert(0, "scripts")
import awx  # noqa: E402

A, B = awx.env("AWX_EMPLOYER_A"), awx.env("AWX_EMPLOYER_B")
DOCS_EXAMPLES = ("e26fe780-ac29-4130-b650-edb1cc1bd4a4", "ffb277f7-c10d-4e46-ab1e-25acd90a79fc")
STAMP = str(int(time.time()))
BEN = {"entity_type": "PERSONAL", "first_name": "Rid", "last_name": "Probe",
       "address": {"country_code": "GB", "city": "London", "street_address": "1 Test St", "postcode": "EC1A 1BB"},
       "bank_details": {"bank_country_code": "GB", "account_currency": "GBP", "account_name": "Rid Probe", "bank_name": "HSBC",
                        "account_routing_type1": "sort_code", "account_routing_value1": "040004", "account_number": "12345678"}}
made, bens = [], []


def ben(acct):
    code, b = awx.call("POST", "/beneficiaries/create", {"nickname": f"probe-rid-{STAMP}", "transfer_methods": ["LOCAL"],
                                                          "beneficiary": BEN}, acct)
    assert code == 201, (code, b)
    bens.append((acct, b["id"]))
    return b["id"]


def transfer(acct, bid, rid):
    code, t = awx.call("POST", "/transfers/create", {
        "request_id": rid, "beneficiary_id": bid, "transfer_amount": 1, "transfer_currency": "GBP", "source_currency": "GBP",
        "transfer_method": "LOCAL", "reason": "professional_business_services", "reference": "probe rid scope"}, acct)
    if code == 201:
        made.append((acct, t["id"]))
        return code, t["id"], None
    return code, None, (t.get("code"), (t.get("details") or {}).get("id")) if isinstance(t, dict) else (str(t)[:80], None)


try:
    ba, bb = ben(A), ben(B)
    rid = f"probe-rid-scope-{STAMP}"
    ca, ta, _ = transfer(A, ba, rid)
    print("1a Northwind, request_id R      ", ca, ta)
    cb, tb, err = transfer(B, bb, rid)
    print("1b Kestrel,   same request_id R ", cb, tb or err)
    if err and err[1]:
        print("   details.id is Northwind's transfer:", err[1] == ta, " -> GLOBAL namespace, cross-tenant")
    elif cb == 201:
        print("   -> per-account namespace: tenants cannot collide")
    for i, ex in enumerate(DOCS_EXAMPLES, 1):
        c, t, err = transfer(A, ba, ex)
        ours = err and err[1] in {x[1] for x in made}
        print(f"2.{i} Northwind, docs example id    ", c, t or err[0],
              "" if c == 201 else ("(details.id is ours)" if ours else "(already used by someone else; not looked up)"))
finally:
    for acct, tid in made:
        code, c = awx.call("POST", f"/transfers/{tid}/cancel", {}, acct)
        print("  cleanup cancel", tid[:8], code, c.get("status") if isinstance(c, dict) else str(c)[:60])
    for acct, bid in bens:
        print("  cleanup delete beneficiary", bid[:8], awx.call("POST", f"/beneficiaries/{bid}/delete", None, acct)[0])
