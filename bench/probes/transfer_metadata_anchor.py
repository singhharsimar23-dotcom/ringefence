"""Does Airwallex store and return `metadata` on a transfer (the H4 ledger-head anchor)? Live, Northwind, GBP 1.00,
cancelled and deleted after.  python bench/probes/transfer_metadata_anchor.py"""
from __future__ import annotations

import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import awx as _env  # noqa: E402

for n in ("AWX_CLIENT_ID", "AWX_API_KEY", "AWX_BASE_URL", "AWX_EMPLOYER_A", "AWX_EMPLOYER_B", "AWX_EMPLOYER_C", "AWX_PLATFORM_ACCOUNT"):
    os.environ.setdefault(n, _env.env(n) or "")
from ringfence.awx import Awx, AwxError  # noqa: E402

TAG = f"PRB-meta-{int(time.time()) % 100000}"
ks = Awx().for_tenant("northwind")
stamp = json.loads(os.environ["STAMP"]) if os.environ.get("STAMP") else {"rf_seq": "123", "rf_hash": "ab" * 32}
NO_META = os.environ.get("NO_META") == "1"
p = {"nickname": TAG, "transfer_methods": ["LOCAL"], "beneficiary": {
    "entity_type": "PERSONAL", "first_name": "Meta", "last_name": "Probe",
    "address": {"country_code": "GB", "city": "London", "street_address": "1 Test St", "postcode": "EC1A 1BB"},
    "bank_details": {"bank_country_code": "GB", "account_currency": "GBP", "account_name": "Meta Probe", "bank_name": "HSBC",
                     "account_routing_type1": "sort_code", "account_routing_value1": "040004", "account_number": "12345678"}}}
bid = tid = None
try:
    bid = ks.post("/beneficiaries/create", p)["id"]
    t = ks.post_money("/transfers/create", {"request_id": f"{TAG}-1", "beneficiary_id": bid, "transfer_amount": Decimal("1.00"),
                                           "transfer_currency": "GBP", "source_currency": "GBP", "transfer_method": "LOCAL",
                                           "reason": "professional_business_services", "reference": TAG, **({} if NO_META else {"metadata": stamp})})
    tid = t["id"]
    print("create", tid, t.get("status"), "metadata on create response:", t.get("metadata"))
    g = ks.get(f"/transfers/{tid}")
    print("GET   metadata:", g.get("metadata"), "| round-trips exactly:", g.get("metadata") == stamp)
    lst = [x for x in ks.get("/transfers", {"page": "0", "page_size": 100}).get("items", []) if x["id"] == tid]
    print("LIST  metadata:", lst[0].get("metadata") if lst else "not listed")
except AwxError as e:
    print("ERROR", e.status, e.code, str(e)[:300], json.dumps(e.details)[:200])
finally:
    if tid:
        for i in range(5):
            try:
                ks.post(f"/transfers/{tid}/cancel", {})
            except AwxError as e:
                print("cancel", e.status, e.code)
            if ks.get(f"/transfers/{tid}").get("status") in ("CANCELLED", "FAILED"):
                break
            time.sleep(3 * (i + 1))
        print("final status", ks.get(f"/transfers/{tid}").get("status"))
    if bid:
        try:
            ks.post(f"/beneficiaries/{bid}/delete", {})
            print("deleted payee", bid)
        except AwxError as e:
            print("delete payee failed", e.status, e.code)
