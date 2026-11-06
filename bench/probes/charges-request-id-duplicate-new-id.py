"""Probe: charges-request-id-duplicate-new-id (live part). Raw output -> charges-request-id-duplicate-new-id.out.txt

Live rules honoured: writes only under Northwind (A) with Kestrel (B) as counterparty; platform is READ-ONLY (GETs only);
every possible money move is 1 GBP; at most 4 creates (+2 identical repeats only if a create returns 2xx).
Never prints tokens. Run: uv run python bench/probes/charges-request-id-duplicate-new-id.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import awx  # noqa: E402

A, B, P = awx.env("AWX_EMPLOYER_A"), awx.env("AWX_EMPLOYER_B"), awx.env("AWX_PLATFORM_ACCOUNT")
EPOCH = int(time.time())
created = []  # (kind, id) for cleanup


def show(label, s, d):
    keys = sorted((d.get("details") or {}).keys()) if isinstance(d, dict) and isinstance(d.get("details"), dict) else None
    print(f"--- {label}\nHTTP {s} code={d.get('code') if isinstance(d, dict) else None} details_keys={keys}")
    print(json.dumps(d, indent=1)[:1500] if isinstance(d, dict) else str(d)[:400])


def create_twice(label, path, body):
    s, d = awx.call("POST", path, body, login_as=A)
    show(f"{label} #1", s, d)
    if 200 <= s < 300:
        created.append((path, d.get("id")))
        s2, d2 = awx.call("POST", path, body, login_as=A)  # IDENTICAL retry: what the vendor's code says
        show(f"{label} #2 identical", s2, d2)
        if 200 <= s2 < 300:
            created.append((path, d2.get("id")))


print("== platform READ-ONLY: is Charges / CA transfers enabled at all?")
for p in ("/charges?page_num=0&page_size=10", "/connected_account_transfers?page_num=0&page_size=10"):
    show(f"GET {p} as platform", *awx.call("GET", p, login_as=P))

print("\n== Northwind (write-allowed) attempts, 1 GBP, Kestrel as counterparty")
create_twice("POST /charges/create (A token, source=B)", "/charges/create",
             {"request_id": f"prb-chg-{EPOCH}", "source": B, "amount": "1", "currency": "GBP",
              "reason": "professional_business_services", "reference": "PRB-charges-request-id-duplicate-new-id"})
create_twice("POST /connected_account_transfers/create (A token, destination=B)", "/connected_account_transfers/create",
             {"request_id": f"prb-cat-{EPOCH}", "destination": B, "amount": "1", "currency": "GBP",
              "reason": "professional_business_services", "reference": "PRB-charges-request-id-duplicate-new-id"})

print("\n== live control: transfers duplicate code + details key (Northwind)")
for tid, cap in (("0846530a-a249-4940-b895-dadd254ddb94", None),  # 1 GBP BENCH transfer: exact original body
                 ("e32f97fd-af14-413d-8114-218e5f6a7cb2", "1")):  # rf- 450 GBP: same request_id, amount capped at 1
    s, t = awx.call("GET", f"/transfers/{tid}", login_as=A)
    print(f"original {tid}: HTTP {s} request_id={t.get('request_id')} status={t.get('status')} amount={t.get('transfer_amount')}")
    body = {"request_id": t["request_id"], "beneficiary_id": t["beneficiary_id"],
            "transfer_amount": cap or str(t["transfer_amount"]), "transfer_currency": t["transfer_currency"],
            "source_currency": t["source_currency"], "transfer_method": t["transfer_method"],
            "reason": t["reason"], "reference": t["reference"]}
    s, d = awx.call("POST", "/transfers/create", body, login_as=A)
    show(f"re-POST request_id={t['request_id']} amount={body['transfer_amount']}", s, d)
    if 200 <= s < 300:
        created.append(("/transfers/create", d.get("id")))
    elif isinstance(d, dict):
        print("details.id == original:", (d.get("details") or {}).get("id") == tid)

print("\n== cleanup")
for path, cid in created:
    if path == "/transfers/create" and cid:
        for i in range(4):
            s, d = awx.call("POST", f"/transfers/{cid}/cancel", "PRB cleanup", login_as=A)
            st = awx.call("GET", f"/transfers/{cid}", login_as=A)[1].get("status")
            print("cancel", cid, s, st)
            if st == "CANCELLED":
                break
            time.sleep(2 ** i)
    else:
        print("created (no cancel API known):", path, cid)
print("created:", created or "nothing")
