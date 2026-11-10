"""On camera: Airwallex's own recommended way, broken live; then Ringfence on the same fault.
  uv run python scripts/breakit.py [approval|batch|retry|pages|sdk ...]   (no args = all five)
Writes only Northwind/Kestrel, GBP <= 2. Transfers cancelled, CA transfers reversed, payees deleted."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bench" / "probes"))
from snapshot_timing import TAG, ben, body, call, cleanup, dest, ks, made_t, nw, repoint  # noqa: E402

from ringfence import verify  # noqa: E402

R, G, D, B, X = "\033[91m", "\033[92m", "\033[90m", "\033[1m", "\033[0m"


def step(s):
    print(f"  {s}", flush=True)
    time.sleep(0.8)  # readable on camera


def bad(s):
    print(f"  {R}{B}✗ {s}{X}", flush=True)


def good(s):
    print(f"  {G}{B}✓ {s}{X}", flush=True)


def head(n, title, says):
    print(f"\n{B}{n} · {title}{X}\n  {D}Airwallex: {says}{X}", flush=True)


def ringfence(fault):
    print(f"\n  {B}RINGFENCE · same fault, live{X}", flush=True)
    out = subprocess.run([sys.executable, "bench/ringfence_bench.py", fault, "1"], cwd=ROOT, capture_output=True,
                         text=True, encoding="utf-8").stdout
    line = next((ln.strip() for ln in out.splitlines() if "trial 0" in ln), out.strip()[-300:] or "bench gave no output")
    (good if "to_mule=0" in line and "paid_twice=[]" in line else bad)(line)


def approval():
    head("1", "A human approves every payment", '"Require manual approval for tool calls"')
    bid, p = ben(nw, "Ben", "44440002")
    step(f"payee Ben · id {bid[:8]}… · bank ..0002")
    step(f"approval card: beneficiary {bid[:8]}… · GBP 2.00 → {G}APPROVED{X}")
    repoint(nw, bid, p)
    step(f"meanwhile: /beneficiaries/{bid[:8]}…/update · same id · bank ..9901")
    t = nw.post_money("/transfers/create", body(bid, f"{TAG}-ap", transfer_amount=Decimal("2.00")))
    made_t.append((nw, t["id"]))
    bad(f"paid {t['id']} {t['status']} → {dest(t)}")
    ringfence("approval")


def batch():
    head("2", "Batch payroll", '"for payroll runs and supplier payments"')
    bid, p = ben(nw, "Bt", "33334444")
    b = nw.post("/batch_transfers/create", {"request_id": f"{TAG}-batch", "name": TAG})
    nw.post_money(f"/batch_transfers/{b['id']}/add_items", {"items": [body(bid, f"{TAG}-bi") | {"reason": "wages_salary"}]})
    it = nw.get(f"/batch_transfers/{b['id']}/items", {"page_num": 0, "page_size": 10})["items"][0]
    shown = ((it.get("transfer_draft") or {}).get("beneficiary") or {}).get("bank_details")
    step(f"batch {b['id'][:8]}… · 1 item · payee ..4444 · bank details shown to reviewer: {shown or 'NONE'}")
    repoint(nw, bid, p)
    step("payee edited in place · same id · bank ..9901")
    nw.post(f"/batch_transfers/{b['id']}/submit", {"request_id": f"{TAG}-bs"})
    step("submit")
    mine = []
    for _ in range(12):
        time.sleep(3)
        if mine := [t for t in nw.get("/transfers", {"page_num": 0, "page_size": 50}).get("items", []) if t.get("beneficiary_id") == bid]:
            break
    for t in mine:
        made_t.append((nw, t["id"]))
        bad(f"BOOKED {t['id']} → {dest(t)}")
    e = call(nw.post, f"/batch_transfers/{b['id']}/cancel", {})
    bad(f"cancel the batch → {str(e.get('msg', ''))[:60]}")
    ringfence("race")


def retry():
    head("3", "The response got lost. Retry the documented way", '"Retry the request with a new request_id"')
    A, K = os.environ["AWX_EMPLOYER_A"], os.environ["AWX_EMPLOYER_B"]

    def ca(c, rid, to, amt="1"):
        return c.post_money("/connected_account_transfers/create", {
            "request_id": rid, "destination": to, "amount": amt, "currency": "GBP",
            "reason": "professional_business_services", "reference": TAG})

    a = ca(nw, f"{TAG}-ca1", K)
    step(f"Northwind → Kestrel · GBP 1 · {a['id']} {a.get('status')} · response lost")
    b = ca(nw, f"{TAG}-ca2", K)
    bad(f"new request_id → {b['id']} {b.get('status')} · GBP 2 moved for GBP 1 · no cancel endpoint")
    print(f"\n  {B}RINGFENCE · same id, never a new one{X}", flush=True)
    e = call(ca, nw, f"{TAG}-ca1", K)
    orig = (e.get("details") or {}).get("id")
    (good if orig == a["id"] else bad)(f"{e.get('code')} → adopts {orig} · moved once")
    r = ca(ks, f"{TAG}-carev", A, "2")
    step(f"{D}[cleanup] Kestrel → Northwind GBP 2 · {r['id']}{X}")


def pages():
    head("4", "Who's been paid?", '"use the pagination parameters (page_num, page_size)"')
    ids = [{t["id"] for t in nw.get("/transfers", {"page_num": n, "page_size": 100})["items"]} for n in range(3)]
    step(f"page_num=0,1,2 → {len(ids[0])}, {len(ids[1])}, {len(ids[2])} transfers · same ones: {ids[0] == ids[1] == ids[2]}")
    every = verify._transfers(nw, "2026-10-01T00:00:00+0000")
    bad(f"the guide's reconcile sees {len(ids[0])} of {len(every)} · {len(every) - len(ids[0])} look UNPAID → paid again")
    good(f"Ringfence (cursor): {len(every)} of {len(every)}")


def sdk():
    head("5", "Did it land? The official Node SDK", '"get a payout with this request_id to find out"')
    rid = "prb-never-used-000001"
    step(f"GET /transfers?request_id={rid} → {len(nw.get('/transfers', {'request_id': rid})['items'])} items")
    step("network blip · SDK retries · apiClient.js:157 _request(method, url, config, data)  ← args swapped")
    bad(f"the retry drops the filter → {len(nw.get('/transfers')['items'])} items → 'it landed' → never paid")
    good(f"Ringfence matches request_id on each item → {nw.transfer_by_request(rid) or 'no match'} → reconcile")


ACTS = {"approval": approval, "batch": batch, "retry": retry, "pages": pages, "sdk": sdk}

if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    try:
        for name in sys.argv[1:] or ACTS:
            try:
                ACTS[name]()
            except Exception as e:  # noqa: BLE001
                bad(f"{name}: harness error {type(e).__name__}: {e}")
    finally:
        print(f"{D}", end="")
        cleanup()
        print(X, end="")
