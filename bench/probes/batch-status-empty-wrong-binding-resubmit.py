"""Batch status under the wrong employer binding, then Airwallex's own "resubmit a new batch" recovery.
Live. Writes only on Northwind (A) and Kestrel (B), GBP 1.00 per item, <= 3 money moves. Every transfer cancelled, every PRB payee deleted.
  python bench/probes/batch-status-empty-wrong-binding-resubmit.py"""
from __future__ import annotations

import json
import sys
import tempfile
import time
import uuid
import os
from decimal import Decimal

os.environ.setdefault("RF_VAR", tempfile.mkdtemp(prefix="rf_prb_bx_"))  # keep the call log out of the repo var/
sys.path.insert(0, os.path.dirname(__file__))
import snapshot_timing as st  # noqa: E402
from snapshot_timing import body, call, dest, made_b, made_t, nw, ks, say  # noqa: E402

EP = int(time.time())
st.TAG = TAG = f"PRB-bxbind-{EP % 100000}"
BX, ITEM = f"prb-bx-{EP}", f"prb-bi-{EP}-01"
J = lambda o, n=600: json.dumps(o, default=str)[:n]  # noqa: E731


def gbp(c):
    return c.balances().get("GBP")


def items(c, bid):
    return call(c.get, f"/batch_transfers/{bid}/items", {"page_size": 100})


def item_view(r):
    if "_error" in r:
        return r
    return {"keys": sorted(r.keys()), "items": [{k: i.get(k) for k in ("request_id", "status", "transfer_id", "errors")} for i in r.get("items", [])]}


def run_batch(c, label, rid_batch, ben_id, item_rid):
    b = call(c.post, "/batch_transfers/create", {"request_id": rid_batch, "name": f"{TAG}-{label}"})
    say(f"[{label}] create", J({k: b.get(k) for k in ("id", "status", "funding", "_error", "code", "msg")}))
    if "_error" in b:
        return None
    made_t.append((c, ("batch", b["id"])))
    r = call(c.post_money, f"/batch_transfers/{b['id']}/add_items",
             {"items": [body(ben_id, item_rid) | {"reason": "wages_salary"}]})
    say(f"[{label}] add_items", J(r, 300))
    say(f"[{label}] items (draft)", J(item_view(items(c, b["id"]))))
    pre = gbp(c)
    s = call(c.post, f"/batch_transfers/{b['id']}/submit", {"request_id": f"{rid_batch}-s"})
    t_sub = time.monotonic()
    say(f"[{label}] submit", J({k: s.get(k) for k in ("status", "_error", "code", "msg")}), "GBP pre", pre, "right after", gbp(c))
    last = None
    for i in range(15):
        time.sleep(4)
        g = c.get(f"/batch_transfers/{b['id']}")
        iv = item_view(items(c, b["id"]))
        last = iv
        say(f"  [{label}] poll {i} +{time.monotonic() - t_sub:.0f}s batch {g.get('status')} GBP {gbp(c)} items {J(iv.get('items'), 500)}")
        for it in iv.get("items", []):
            if it.get("transfer_id") and (c, it["transfer_id"]) not in made_t:
                made_t.append((c, it["transfer_id"]))
        if g.get("status") not in ("BOOKING", "SUBMITTED", "DRAFTING", "IN_APPROVAL", "APPROVAL_PENDING", None):
            say(f"  [{label}] final batch", J(g, 900))
            break
    return b["id"], last


def main():
    say("TAG", TAG, "batch rid", BX, "item rid", ITEM)
    say("identity: A GET /account id", call(nw.get, "/account").get("id"), "| B", call(ks.get, "/account").get("id"))
    a_ben, p = st.ben(nw, "Ada", "55667788")
    b_ben = ks.post("/beneficiaries/create", p | {"nickname": f"{TAG}-Ada-B"})["id"]  # same bank details, B's own book
    made_b.append((ks, b_ben))

    # 1-3: A books one GBP 1.00 line in batch X
    res = run_batch(nw, "A-X", BX, a_ben, ITEM)
    if not res:
        return
    ax, ax_items = res
    a_tr = next((i["transfer_id"] for i in ax_items.get("items", []) if i.get("transfer_id")), None)
    say("A-X transfer", a_tr, dest(call(nw.get, f"/transfers/{a_tr}")) if a_tr else "")

    # 4: the recommended status check, done with the WRONG employer's client (B), plus a non-existent batch
    say("\n== 4 status check under B's binding")
    say("B GET /batch_transfers/{A_X}/items ->", J(items(ks, ax)))
    say("B GET /batch_transfers/{A_X}       ->", J(call(ks.get, f"/batch_transfers/{ax}"), 300))
    say("B GET /batch_transfers?request_id  ->", J(call(ks.get, "/batch_transfers", {"request_id": BX, "page_size": 10}), 300))
    say("B GET /transfers?request_id=item   ->", J(call(ks.get, "/transfers", {"request_id": ITEM, "page_size": 100}).get("items"), 300))
    if a_tr:
        say("B GET /transfers/{A_tr}            ->", J(call(ks.get, f"/transfers/{a_tr}"), 300))
    ghost = str(uuid.uuid4())
    say("A GET /batch_transfers/{random}/items ->", J(items(nw, ghost)))
    say("A GET /batch_transfers/{random}       ->", J(call(nw.get, f"/batch_transfers/{ghost}"), 300))

    # 5: 'nothing booked' -> resubmit under B with the SAME deterministic item id (per-account namespace: no dedupe)
    say("\n== 5 resubmit under B, same item request_id")
    rb = run_batch(ks, "B-X", BX, b_ben, ITEM)

    # 6: resubmit under A (correct binding) with the same item id -> BOOKING_FAILED shape
    say("\n== 6 resubmit under A, same item request_id, new batch id")
    ry = run_batch(nw, "A-Y", f"{BX}-y", a_ben, ITEM)
    if ry:
        say("A-Y item errors full:", J(ry[1], 1200))

    # 7: same batch request_id again on A
    say("\n== 7 A re-create batch with X's request_id")
    say(J(call(nw.post, "/batch_transfers/create", {"request_id": BX, "name": f"{TAG}-dup"}), 600))

    # 8: the recovery path the docs do not mention
    say("\n== 8 A GET /batch_transfers?request_id=", J(call(nw.get, "/batch_transfers", {"request_id": BX, "page_size": 10}), 600))
    say("A GET /transfers?request_id=item ->", J([(t["id"], t.get("status")) for t in call(nw.get, "/transfers", {"request_id": ITEM, "page_size": 100}).get("items", [])]))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001
        say(f"harness error {type(e).__name__}: {e}")
    finally:
        st.cleanup()
        for c, x in made_t:
            if isinstance(x, tuple):
                say("final batch", x[1], call(c.get, f"/batch_transfers/{x[1]}").get("status"))
