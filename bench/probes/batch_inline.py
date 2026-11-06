"""Fix check: a batch item that carries the bank details inline (no beneficiary_id) has nothing to repoint. Live, Northwind, GBP 1.00."""
import time
from snapshot_timing import TAG, ben, body, call, dest, made_t, nw, say, cleanup

try:
    _, p = ben(nw, "In", "77778888")  # only to borrow a valid payload shape; the item does not reference it
    b = nw.post("/batch_transfers/create", {"request_id": f"{TAG}-inl", "name": f"{TAG}-inline"})
    item = {k: v for k, v in body("x", f"{TAG}-inli").items() if k != "beneficiary_id"} | {"reason": "wages_salary", "beneficiary": p["beneficiary"]}
    say("add_items inline:", str(call(nw.post_money, f"/batch_transfers/{b['id']}/add_items", {"items": [item]}))[:300])
    say("submit:", call(nw.post, f"/batch_transfers/{b['id']}/submit", {"request_id": f"{TAG}-inls"}).get("status"))
    for i in range(10):
        time.sleep(4)
        mine = [t for t in nw.get("/transfers", {"page_num": 0, "page_size": 30}).get("items", []) if t.get("reference") == TAG and t.get("request_id") == f"{TAG}-inli"]
        if mine:
            made_t.extend((nw, t["id"]) for t in mine)
            say("transfer", [(t["id"], t["status"], dest(t), t.get("beneficiary_id")) for t in mine]); break
finally:
    cleanup()
