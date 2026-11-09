"""Is native transfer-approval routing actually provisioned on this org?
The web-app "Edit transfer approval workflows" save fails with "Something went wrong", and the feature is
"available upon request" in the docs. The config API needs admin (our scoped key gets 401), so the only
way to tell is to create ONE transfer via API and read its status:
  IN_APPROVAL -> routing is live; the web-app save error is a UI/permission quirk we can work around.
  SCHEDULED   -> routing is NOT provisioned; no web-app fiddling will catch API transfers until AWX enables it.
Authorized sandbox research, our own Northwind account, GBP 1.00, PRB- payee, transfer cancelled + payee
deleted in finally. No model, no cross-tenant, no repoint.
  export MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8; uv run python bench/probes/approval_status_check.py
"""
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

TAG = f"PRB-appchk-{int(time.time()) % 100000}"
nw = Awx().for_tenant("northwind")
APPROVAL = {"IN_APPROVAL", "APPROVAL_PENDING", "AWAITING_APPROVAL"}


def say(*a):
    print(*a, flush=True)


def call(f, *a):
    try:
        return f(*a)
    except AwxError as e:
        return {"_error": e.status, "code": e.code, "msg": str(e)[:200]}


def main():
    say(f"tag {TAG}")
    p = {"nickname": f"{TAG}-x", "transfer_methods": ["LOCAL"], "beneficiary": {
        "entity_type": "PERSONAL", "first_name": "Appchk", "last_name": "Probe",
        "address": {"country_code": "GB", "city": "London", "street_address": "1 Test St", "postcode": "EC1A 1BB"},
        "bank_details": {"bank_country_code": "GB", "account_currency": "GBP", "account_name": "Appchk Probe",
                         "bank_name": "HSBC", "account_routing_type1": "sort_code",
                         "account_routing_value1": "040004", "account_number": "11112222"}}}
    bid = nw.post("/beneficiaries/create", p)["id"]
    tid = None
    try:
        t = call(nw.post_money, "/transfers/create", {
            "request_id": f"{TAG}-t", "beneficiary_id": bid,
            "transfer_amount": Decimal("1.00"), "transfer_currency": "GBP", "source_currency": "GBP",
            "transfer_method": "LOCAL", "reason": "professional_business_services", "reference": TAG})
        if "_error" in t:
            return say("create failed:", json.dumps(t))
        tid = t["id"]
        st = t.get("status")
        say("created", tid, "status:", st)
        say("VERDICT:", "APPROVAL ROUTING LIVE (status in approval)" if st in APPROVAL
            else f"approval routing NOT active (status {st}) - feature not provisioned for the org")
        assert st, "no status returned; probe inconclusive"
    finally:
        call(nw.post, f"/beneficiaries/{bid}/delete", {}) if not tid else None
        if tid:
            for i in range(5):
                call(nw.post, f"/transfers/{tid}/cancel", {})
                cur = nw.get(f"/transfers/{tid}").get("status")
                if cur in ("CANCELLED", "FAILED"):
                    break
                time.sleep(3 * (i + 1))
            else:
                call(nw.post, f"/simulation/transfers/{tid}/transition", {"status": "FAILED"})
                cur = nw.get(f"/transfers/{tid}").get("status")
            say("cleanup transfer", tid, cur)
            call(nw.post, f"/beneficiaries/{bid}/delete", {})
        say("cleanup payee", bid, "deleted")


if __name__ == "__main__":
    try:
        main()
    except AssertionError as e:
        say("SELF-CHECK FAILED:", e)
    except Exception as e:  # noqa: BLE001
        say(f"harness error {type(e).__name__}: {e}")
