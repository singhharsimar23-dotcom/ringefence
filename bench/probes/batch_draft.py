"""Batch transfers: what the batch shows (items[].transfer_draft) vs where its transfer pays, when the payee is edited in place
between add_items and submit. Live, Northwind, GBP 1.00 per trial; transfers cancelled, payees deleted.
  python bench/probes/batch_draft.py [trials=3]"""
from __future__ import annotations

import json
import sys
import time

from snapshot_timing import TAG, ben, body, call, dest, made_b, made_t, nw, repoint, say, cleanup  # noqa: F401


def draft_dest(bid_batch):
    items = call(nw.get, f"/batch_transfers/{bid_batch}/items", {"page_num": 0, "page_size": 10})
    if not isinstance(items, dict) or "_error" in items:
        return f"items error {json.dumps(items, default=str)[:200]}"
    return [(i.get("status"), dest(i.get("transfer_draft"))) for i in items.get("items", [])]


def trial(n):
    say(f"\n== trial {n}")
    bid, p = ben(nw, f"Bd{n}", f"4444{n:04d}")
    b = nw.post("/batch_transfers/create", {"request_id": f"{TAG}-b{n}", "name": f"{TAG}-{n}"})
    call(nw.post_money, f"/batch_transfers/{b['id']}/add_items", {"items": [body(bid, f"{TAG}-i{n}") | {"reason": "wages_salary"}]})
    say("batch", b["id"], "draft after add_items:", draft_dest(b["id"]))
    say("payee update", "ok" if "_error" not in (u := repoint(nw, bid, p)) else u)
    say("draft after payee edit:", draft_dest(b["id"]))
    say("submit:", call(nw.post, f"/batch_transfers/{b['id']}/submit", {"request_id": f"{TAG}-s{n}"}).get("status"))
    for i in range(10):
        time.sleep(4)
        mine = [t for t in nw.get("/transfers", {"page_num": 0, "page_size": 50}).get("items", []) if t.get("beneficiary_id") == bid]
        if mine:
            for t in mine:
                made_t.append((nw, t["id"]))
            say("batch", nw.get(f"/batch_transfers/{b['id']}").get("status"), "-> transfer", [(t["id"], t["status"], dest(t)) for t in mine])
            say("draft after booking:", draft_dest(b["id"]))
            return
    say("no transfer after 40 s; batch", nw.get(f"/batch_transfers/{b['id']}").get("status"))


if __name__ == "__main__":
    try:
        for n in range(int(sys.argv[1]) if len(sys.argv) > 1 else 3):
            try:
                trial(n)
            except Exception as e:  # noqa: BLE001
                say(f"trial {n} harness error {type(e).__name__}: {e}")
    finally:
        cleanup()
