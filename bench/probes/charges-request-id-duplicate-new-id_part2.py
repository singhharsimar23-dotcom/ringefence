"""Part 2 (live): reverse the 1 GBP CA transfer (no cancel API for CA transfers; it SETTLED instantly), and a self-owned
transfers control: create 1 GBP to a Northwind-owned GBP beneficiary, re-POST identical, record code + details keys, cancel."""
import json, sys, time
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import awx  # noqa: E402

A, B = awx.env("AWX_EMPLOYER_A"), awx.env("AWX_EMPLOYER_B")
EPOCH = int(time.time())
CAT = "tr_iJL2nwzWO46QVtihKjf6OQ"


def show(label, s, d):
    det = d.get("details") if isinstance(d, dict) else None
    print(f"--- {label}\nHTTP {s} code={d.get('code') if isinstance(d, dict) else None} "
          f"details_keys={sorted(det) if isinstance(det, dict) else None}")
    print(json.dumps(d, indent=1)[:1200])


print("== reverse CA transfer", CAT, "(Kestrel -> Northwind, 1 GBP)")
s, d = awx.call("POST", "/connected_account_transfers/create",
                {"request_id": f"prb-cat-rev-{EPOCH}", "destination": A, "amount": "1", "currency": "GBP",
                 "reason": "professional_business_services", "reference": f"PRB-charges-request-id-duplicate-new-id reverse {CAT}"},
                login_as=B)
show("reverse CAT", s, d)
rev = d.get("id") if 200 <= s < 300 else None

print("\n== transfers control (self-owned)")
items = awx.call("GET", "/beneficiaries?page_num=0&page_size=100", login_as=A)[1]["items"]
ben = next(b for b in items if (b.get("beneficiary") or {}).get("bank_details", {}).get("account_currency") == "GBP"
           and not str(b.get("nickname", "")).startswith("PRB-"))
print("beneficiary", ben["id"], ben.get("nickname"))
body = {"request_id": f"prb-ctl-{EPOCH}", "beneficiary_id": ben["id"], "transfer_amount": "1", "transfer_currency": "GBP",
        "source_currency": "GBP", "transfer_method": "LOCAL", "reason": "professional_business_services",
        "reference": "PRB-chg-dup-ctl"}
s, d = awx.call("POST", "/transfers/create", body, login_as=A)
show("create #1", s, d)
tid = d.get("id") if 200 <= s < 300 else None
s2, d2 = awx.call("POST", "/transfers/create", body, login_as=A)
show("create #2 identical", s2, d2)
if 200 <= s2 < 300:
    print("!! second create succeeded:", d2.get("id"))
print("details.id == first id:", isinstance(d2, dict) and (d2.get("details") or {}).get("id") == tid)

print("\n== cleanup")
for t in filter(None, [tid, d2.get("id") if 200 <= s2 < 300 else None]):
    for i in range(4):
        cs, _ = awx.call("POST", f"/transfers/{t}/cancel", "PRB cleanup", login_as=A)
        st = awx.call("GET", f"/transfers/{t}", login_as=A)[1].get("status")
        print("cancel", t, cs, st)
        if st == "CANCELLED":
            break
        time.sleep(2 ** i)
    else:
        ts, td = awx.call("POST", f"/simulation/transfers/{t}/transition", {"status": "FAILED"}, login_as=A)
        print("transition FAILED", t, ts, awx.call("GET", f"/transfers/{t}", login_as=A)[1].get("status"))
for cid, who in ((CAT, A), (rev, B)):
    if cid:
        print("CA transfer", cid, awx.call("GET", f"/connected_account_transfers/{cid}", login_as=who)[1].get("status"))
