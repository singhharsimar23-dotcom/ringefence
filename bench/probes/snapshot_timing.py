"""When does Airwallex bind a payout to bank details? Live, Northwind, GBP 1.00, everything cancelled/deleted after.
  A  future-dated transfer (transfer_date +5d): edit the payee in place after create -> does the transfer's destination follow?
  B  batch transfer (Airwallex's payroll API): add item, edit the payee in place, submit -> where does the item's transfer go?
  C  cross-employer reference: Kestrel's token, Northwind's beneficiary_id -> read / pay?
  python bench/probes/snapshot_timing.py"""
from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import awx as _env  # noqa: E402

for n in ("AWX_CLIENT_ID", "AWX_API_KEY", "AWX_BASE_URL", "AWX_EMPLOYER_A", "AWX_EMPLOYER_B", "AWX_EMPLOYER_C", "AWX_PLATFORM_ACCOUNT"):
    os.environ.setdefault(n, _env.env(n) or "")
from ringfence.awx import Awx, AwxError  # noqa: E402

TAG = f"PRB-snap-{int(time.time()) % 100000}"
MULE = "99999901"
awx = Awx()
nw, ks = awx.for_tenant("northwind"), awx.for_tenant("kestrel")
made_t: list[tuple] = []
made_b: list[tuple] = []


def say(*a):
    print(*a, flush=True)


def call(f, *a):
    try:
        return f(*a)
    except AwxError as e:
        return {"_error": e.status, "code": e.code, "msg": str(e)[:200], "details": e.details}


def ben(c, who, acct):
    p = {"nickname": f"{TAG}-{who}", "transfer_methods": ["LOCAL"], "beneficiary": {
        "entity_type": "PERSONAL", "first_name": who, "last_name": "Probe",
        "address": {"country_code": "GB", "city": "London", "street_address": "1 Test St", "postcode": "EC1A 1BB"},
        "bank_details": {"bank_country_code": "GB", "account_currency": "GBP", "account_name": f"{who} Probe", "bank_name": "HSBC",
                         "account_routing_type1": "sort_code", "account_routing_value1": "040004", "account_number": acct}}}
    bid = c.post("/beneficiaries/create", p)["id"]
    made_b.append((c, bid))
    return bid, p


def repoint(c, bid, p):
    b = json.loads(json.dumps(p["beneficiary"]))
    b["bank_details"].update(account_number=MULE, account_routing_value1="200000", bank_name="Barclays")
    return call(c.post, f"/beneficiaries/{bid}/update", {"transfer_methods": ["LOCAL"], "beneficiary": b})


def dest(t):
    bd = ((t or {}).get("beneficiary") or {}).get("bank_details") or {}
    return f"..{str(bd.get('account_number', '?'))[-4:]} sort {bd.get('account_routing_value1')}"


def body(bid, rid, **kw):
    return {"request_id": rid, "beneficiary_id": bid, "transfer_amount": Decimal("1.00"), "transfer_currency": "GBP",
            "source_currency": "GBP", "transfer_method": "LOCAL", "reason": "professional_business_services",
            "reference": TAG, **kw}


def test_future():
    say("\n== A future-dated transfer")
    bid, p = ben(nw, "Fd", "11112222")
    when = (date.today() + timedelta(days=5)).isoformat()
    t = call(nw.post_money, "/transfers/create", body(bid, f"{TAG}-fd", transfer_date=when))
    if "_error" in t:
        return say("create", t)
    made_t.append((nw, t["id"]))
    say("created", t["id"], t.get("status"), "transfer_date", t.get("transfer_date"), "dest", dest(t))
    say("payee update", "ok" if "_error" not in (r := repoint(nw, bid, p)) else r)
    t2 = nw.get(f"/transfers/{t['id']}")
    say("re-GET after edit:", t2.get("status"), "dest", dest(t2), "| live payee now", dest({"beneficiary": nw.get(f"/beneficiaries/{bid}")["beneficiary"]}))


def test_batch():
    say("\n== B batch transfer, edit between add_items and submit")
    bid, p = ben(nw, "Bt", "33334444")
    b = call(nw.post, "/batch_transfers/create", {"request_id": f"{TAG}-batch", "name": TAG})
    say("batch create", {k: b.get(k) for k in ("id", "status", "_error", "code", "msg")})
    if "_error" in b:
        return
    made_t.append((nw, ("batch", b["id"])))
    r = call(nw.post_money, f"/batch_transfers/{b['id']}/add_items", {"items": [
        {k: v for k, v in body(bid, f"{TAG}-bi1").items()} | {"reason": "wages_salary"}]})
    say("add_items", json.dumps(r, default=str)[:400])
    say("payee update", "ok" if "_error" not in (u := repoint(nw, bid, p)) else u)
    s = call(nw.post, f"/batch_transfers/{b['id']}/submit", {"request_id": f"{TAG}-bsub"})
    say("submit", json.dumps(s, default=str)[:400])
    for i in range(10):
        time.sleep(4)
        g = nw.get(f"/batch_transfers/{b['id']}")
        mine = [t for t in nw.get("/transfers", {"page_num": 0, "page_size": 50}).get("items", []) if t.get("beneficiary_id") == bid]
        say(f"  poll {i}: batch {g.get('status')}  transfers for payee: {[(t['id'], t['status'], dest(t)) for t in mine]}")
        for t in mine:
            if (nw, t["id"]) not in made_t:
                made_t.append((nw, t["id"]))
        if mine or g.get("status") in ("FAILED", "CANCELLED", "COMPLETED", "FINISHED"):
            say("  batch detail", json.dumps(g, default=str)[:900])
            break


def test_cross():
    say("\n== C Kestrel token, Northwind beneficiary_id")
    bid, _ = ben(nw, "Cx", "55556666")
    say("GET with Kestrel token:", json.dumps(call(ks.get, f"/beneficiaries/{bid}"), default=str)[:300])
    t = call(ks.post_money, "/transfers/create", body(bid, f"{TAG}-cx"))
    say("create with Kestrel token:", json.dumps({k: t.get(k) for k in ("id", "status", "_error", "code", "msg")}, default=str))
    if "id" in t:
        made_t.append((ks, t["id"]))
        say("!!! CROSS-TENANT 2xx", dest(t))


def cleanup():
    say("\n== cleanup")
    for c, x in made_t:
        if isinstance(x, tuple):
            say("batch", x[1], json.dumps(call(c.post, f"/batch_transfers/{x[1]}/cancel", {}), default=str)[:160])
            continue
        st = "?"
        for i in range(5):
            call(c.post, f"/transfers/{x}/cancel", {})
            st = c.get(f"/transfers/{x}").get("status")
            if st in ("CANCELLED", "FAILED"):
                break
            time.sleep(3 * (i + 1))
        if st not in ("CANCELLED", "FAILED"):
            call(c.post, f"/simulation/transfers/{x}/transition", {"status": "FAILED"})
            st = c.get(f"/transfers/{x}").get("status")
        say("transfer", x, st)
    for c, b in made_b:
        call(c.post, f"/beneficiaries/{b}/delete", {})
        say("beneficiary deleted", b)


if __name__ == "__main__":
    try:
        for f in (test_future, test_batch, test_cross):
            try:
                f()
            except Exception as e:  # noqa: BLE001
                say(f"{f.__name__} harness error {type(e).__name__}: {e}")
    finally:
        cleanup()
