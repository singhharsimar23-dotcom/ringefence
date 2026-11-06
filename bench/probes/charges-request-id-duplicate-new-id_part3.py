"""Part 3 (live): the docs-following handler on a real Connected Account Transfer (Northwind -> Kestrel, 1 GBP).
Attempt 1 lands; we discard its response (models a timeout). The integration retries with the SAME request_id (Airwallex
idempotency guidance), gets request_id_duplicate, and follows the error table: 'Retry the request with a new request_id'.
Then the adopt arm (GET details.source_id, no write), then one reversal CA transfer Kestrel -> Northwind for the total."""
import json, sys, time, uuid
from decimal import Decimal
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import awx  # noqa: E402

A, B = awx.env("AWX_EMPLOYER_A"), awx.env("AWX_EMPLOYER_B")
EPOCH = int(time.time())
REF = f"PRB-charges-request-id-duplicate-new-id docs-handler {EPOCH}"
body = {"request_id": f"prb-cat-dh-{EPOCH}", "destination": B, "amount": "1", "currency": "GBP",
        "reason": "professional_business_services", "reference": REF}
P = "/connected_account_transfers/create"


def docs_following_create(body):
    s, d = awx.call("POST", P, body, login_as=A)
    print("  retry same id ->", s, d.get("code"), "details", d.get("details"))
    if s == 400 and d.get("code") == "request_id_duplicate":  # error table: "Retry the request with a new request_id."
        s, d = awx.call("POST", P, {**body, "request_id": f"prb-{uuid.uuid4().hex[:28]}"}, login_as=A)
        print("  new id         ->", s, d.get("id"), d.get("status"))
    return s, d


s, first = awx.call("POST", P, body, login_as=A)
print("attempt 1 (response 'lost'):", s, first.get("id"), first.get("status"))
mine = [first.get("id")] if 200 <= s < 300 else []
s2, d2 = docs_following_create(body)
if 200 <= s2 < 300 and d2.get("id") not in mine:
    mine.append(d2.get("id"))

print("\n== what Northwind actually sent for this one payable")
total = Decimal(0)
for cid in mine:
    t = awx.call("GET", f"/connected_account_transfers/{cid}", login_as=A)[1]
    print(" ", cid, t.get("request_id"), t.get("status"), t.get("amount"), t.get("currency"), "->", t.get("destination"))
    total += Decimal(str(t.get("amount")))
print("total moved for one intended 1 GBP:", total)

print("\n== adopt arm (Ringfence-style, GET only): source_id -> original")
s3, d3 = awx.call("POST", P, body, login_as=A)
sid = (d3.get("details") or {}).get("source_id")
print("  dup:", s3, d3.get("code"), "source_id", sid, "== attempt 1:", sid == first.get("id"))
print("  GET original:", awx.call("GET", f"/connected_account_transfers/{sid}", login_as=A)[1].get("status"))

print("\n== cleanup: one reversal Kestrel -> Northwind for", total)
if total:
    s4, d4 = awx.call("POST", P, {"request_id": f"prb-cat-dh-rev-{EPOCH}", "destination": A, "amount": str(total),
                                  "currency": "GBP", "reason": "professional_business_services",
                                  "reference": f"PRB reverse {','.join(mine)}"[:140]}, login_as=B)
    print("  reverse:", s4, d4.get("id"), d4.get("status"))
    time.sleep(3)
    if d4.get("id"):
        print("  reverse now:", awx.call("GET", f"/connected_account_transfers/{d4['id']}", login_as=B)[1].get("status"))
print("created:", mine)
