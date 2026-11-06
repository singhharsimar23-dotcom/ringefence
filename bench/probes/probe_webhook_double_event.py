"""Offline (fake Airwallex): one bank return = two signed events (payout.transfer.failed, then the automatic
payout.transfer.cancelled), different event ids. Live (webhook-failed-cancelled-double-repay.out.txt) showed the
auto-cancel lands ~0.1 s after FAILED and the GET then has failure_type/failure_reason = null; the fake is set up the same.

  1  Ringfence: [failed, cancelled] and [cancelled, failed] -> exactly 1 REOPENED, 1 re-pay after approval.
  2  Airwallex-recommended handler (HMAC verify, dedupe by event id, payload used directly, re-pay with uuid4):
     re-pays on both events -> 2 replacement transfers for 1 return. Variants: created_at ordering, failed-only,
     deterministic re-pay id.
  3  Stale paid (an undelivered payout.transfer.paid retried later): payload handler ends PAID; Ringfence does not.
  4  Residual: lines A and B PAID; A returns (run -> AWAITING_APPROVAL); B returns with no webhook -> poll_inflight?
  uv run python bench/probes/probe_webhook_double_event.py"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import sys
import tempfile
import time
import uuid
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ.update(RF_MANDATE_KEY="probe-mandate-key", RF_APPROVAL_KEY="probe-approval-key")
os.environ["RF_VAR"] = tempfile.mkdtemp(prefix="prb-wh-")

import ringfence.verify  # noqa: E402

ringfence.verify.PUB_PATH = Path(os.environ["RF_VAR"]) / "cert_pub.pem"  # never touch the published key

from helpers import RUN, acct, new_run, sim  # noqa: E402
from invariants import assert_invariants  # noqa: E402

from ringfence import store, webhooks  # noqa: E402
from ringfence.awx import Awx, AwxError  # noqa: E402
from ringfence.config import tenants  # noqa: E402
from ringfence.executor import Executor  # noqa: E402
from ringfence.fake_awx import FakeAirwallex  # noqa: E402
from ringfence.ledger import Ledger  # noqa: E402
from ringfence.money import dumps_money  # noqa: E402
from ringfence.orchestrator import Orchestrator  # noqa: E402

T = "kestrel"
results: list[tuple[str, bool, str]] = []


def check(name, ok, detail=""):
    results.append((name, bool(ok), detail))
    print(("PASS " if ok else "FAIL ") + name + (f"  [{detail}]" if detail else ""), flush=True)


def world():
    os.environ["RF_VAR"] = tempfile.mkdtemp(prefix="prb-wh-")
    fake = FakeAirwallex({k: t.account_id for k, t in tenants(fake=True).items()})
    fake.auto_cancel_failed = True  # live: FAILED -> CANCELLED within seconds
    awx = Awx(transport=fake.transport, tenant_map=tenants(fake=True), sleep=lambda s: None)
    L = Ledger()
    ex = Executor(awx, L, sleep=lambda s: None)
    return fake, awx, L, ex


def bank_return(fake, tid):
    """What live showed: FAILED, then auto-CANCELLED with the failure fields wiped. Refund happens once."""
    fake.late_failure(acct(T), tid)
    failed = dict(fake.accounts[acct(T)].transfers[tid])
    fake.set_status(acct(T), tid, "CANCELLED", failure_type=None, failure_reason=None)
    return failed, dict(fake.accounts[acct(T)].transfers[tid])


def ev(name, snap, eid, created_at):
    return {"id": eid, "name": name, "account_id": acct(T), "created_at": created_at, "version": "2025-02-14",
            "data": json.loads(dumps_money(snap))}


def signed(fake, e):
    raw = json.dumps(e).encode()
    ts = str(int(time.time() * 1000))
    return {"x-timestamp": ts, "x-signature": fake.sign_webhook(ts, raw)}, raw


def to_paid(awx, ex, tid):
    sim(awx, T, tid, "SENT")
    sim(awx, T, tid, "PAID")
    ex.poll_inflight()


# ---------------------------------------------------------------------------------------------------------------
# the handler Airwallex's docs describe (dedupe by event id; payload used directly; failed/cancelled -> create anew)
# ---------------------------------------------------------------------------------------------------------------
def recommended_handler(st, client, secret, headers, raw, *, order_by_created=False, repay_on=("failed", "cancelled"),
                        repay_id=lambda d: str(uuid.uuid4())):
    want = hmac.new(secret.encode(), headers["x-timestamp"].encode() + raw, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(want, headers["x-signature"]):
        return 401
    e = json.loads(raw)
    if e["id"] in st["seen"]:
        return 200  # 'idempotent handling by tracking the event id'
    st["seen"].add(e["id"])
    d, kind = e["data"], e["name"].rsplit(".", 1)[-1]
    if order_by_created and e["created_at"] < st["last"].get(d["id"], ""):
        return 200  # 'use the created_at field' to order
    st["last"][d["id"]], st["status"][d["id"]] = e["created_at"], d["status"]  # 'used directly after parsing'
    if kind in repay_on:  # failed: 'You can retry'; failed/cancelled: 'create a new one'
        try:
            t = client.post_money("/transfers/create", {
                "request_id": repay_id(d), "beneficiary_id": d["beneficiary_id"], "source_currency": d["source_currency"],
                "transfer_currency": d["transfer_currency"], "transfer_amount": D(d["transfer_amount"]),
                "transfer_method": d["transfer_method"], "reason": d["reason"], "reference": d["reference"]})
            st["status"][t["id"]] = t["status"]
        except AwxError as x:
            if x.code != "duplicate_request_id":
                raise  # duplicate = this re-pay already exists
    return 200


def reference_world():
    fake, awx, L, ex = world()
    new_run(awx, L, T, {"noah": D(10)}, approve=False)  # registry + beneficiaries; the run itself is not used
    c = awx.for_tenant(T)
    bid = next(iter(store.get_lines(L, RUN, T)))["beneficiary_id"]
    t = c.post_money("/transfers/create", {"request_id": str(uuid.uuid4()), "beneficiary_id": bid,
                                           "source_currency": "USD", "transfer_currency": "USD",
                                           "transfer_amount": D("550.00"), "transfer_method": "LOCAL",
                                           "reason": "professional_business_services", "reference": "PAYROLL"})
    sim(awx, T, t["id"], "SENT")
    sim(awx, T, t["id"], "PAID")
    paid = dict(fake.accounts[acct(T)].transfers[t["id"]])
    return fake, c, t["id"], paid


def run_reference(order, **kw):
    fake, c, tid, paid = reference_world()
    failed, cancelled = bank_return(fake, tid)
    evs = {"failed": ev("payout.transfer.failed", failed, "evt_f", "2026-11-06T15:18:19.100Z"),
           "cancelled": ev("payout.transfer.cancelled", cancelled, "evt_c", "2026-11-06T15:18:19.240Z"),
           "paid": ev("payout.transfer.paid", paid, "evt_p", "2026-11-06T15:18:18.000Z")}
    st = {"seen": set(), "status": {}, "last": {}}
    for k in order:
        h, raw = signed(fake, evs[k])
        recommended_handler(st, c, fake.webhook_secret, h, raw, **kw)
    live = [x for x in fake.all_transfers(acct(T)) if x["status"] not in ("CANCELLED", "FAILED")]
    return len(fake.all_transfers(acct(T))) - 1, st["status"][tid], len(live)


# ---------------------------------------------------------------------------------------------------------------
def ringfence_arm(order, stale_paid=False):
    fake, awx, L, ex = world()
    orch = Orchestrator(awx, L, ex)
    new_run(awx, L, T, {"noah": D(10)})
    L.append("APPROVED", {"auto_release": True, "rule": "probe"}, RUN, T)
    ex.release(RUN, T)
    tid = store.get_line(L, RUN, T, "noah")["transfer_id"]
    to_paid(awx, ex, tid)
    paid = dict(fake.accounts[acct(T)].transfers[tid])
    failed, cancelled = bank_return(fake, tid)
    evs = {"failed": ev("payout.transfer.failed", failed, "evt_f", "2026-11-06T15:18:19.100Z"),
           "cancelled": ev("payout.transfer.cancelled", cancelled, "evt_c", "2026-11-06T15:18:19.240Z"),
           "paid": ev("payout.transfer.paid", paid, "evt_p", "2026-11-06T15:18:18.000Z")}
    out = [webhooks.handle(L, ex, fake.webhook_secret, *signed(fake, evs[k])) for k in order]
    reopened = L.entries(kind="REOPENED")
    ln = store.get_line(L, RUN, T, "noah")
    role = store.latest_mandate(L, T).mandate.approver_role
    orch.approve(RUN, T, "pat", role)
    orch.advance(RUN, T)
    n_new = len(fake.all_transfers(acct(T))) - 1
    assert_invariants(L, fake)
    return out, len(reopened), ln["state"], n_new, reopened


def main():
    print("== 1 Ringfence on one bank return (two signed events)")
    for order in (["failed", "cancelled"], ["cancelled", "failed"]):
        out, n_re, st, n_new, re = ringfence_arm(order)
        check(f"RF {order}: exactly 1 REOPENED", n_re == 1, f"webhook results {out}")
        check(f"RF {order}: exactly 1 re-pay after approve+release", n_new == 1, f"new transfers {n_new}")
        print("   REOPENED failure_type/reason as recorded:", re[0]["payload"].get("failure_type"),
              re[0]["payload"].get("failure_reason"))

    print("\n== 2 Airwallex-recommended handler on the same two events")
    n, _, live = run_reference(["failed", "cancelled"])
    check("REF uuid4 re-pay on failed+cancelled: 2 replacement transfers for 1 return", n == 2, f"{n} new, {live} live")
    n, _, _ = run_reference(["failed", "cancelled"], order_by_created=True)
    check("REF + created_at ordering: still 2 (both events are newer)", n == 2, f"{n} new")
    n, _, _ = run_reference(["failed", "cancelled"], repay_on=("failed",))
    check("REF re-pay on failed only: 1 (correct count)", n == 1, f"{n} new")
    n, _, _ = run_reference(["cancelled", "failed"], repay_on=("failed",))
    check("REF re-pay on failed only, cancelled first: 1", n == 1, f"{n} new")
    n, _, _ = run_reference(["failed", "cancelled"], repay_id=lambda d: f"repay-{d['id']}"[:50])
    check("REF deterministic re-pay id (keyed on original transfer): 1 (dup id joins them)", n == 1, f"{n} new")

    print("\n== 3 Stale payout.transfer.paid delivered after the return")
    n, status, _ = run_reference(["failed", "cancelled", "paid"], repay_on=())
    check("REF payload-trusting handler ends PAID while money is back in the wallet", status == "PAID", status)
    n, status, _ = run_reference(["failed", "cancelled", "paid"], repay_on=(), order_by_created=True)
    check("REF + created_at ordering rejects the stale paid", status == "CANCELLED", status)
    out, n_re, st, n_new, _ = ringfence_arm(["failed", "cancelled", "paid"])
    check("RF stale paid: line is not marked PAID (stays reopened)", st == "PLANNED" and n_re == 1,
          f"state before approve {st}, webhook results {out}")

    print("\n== 4 Residual: second late return in a run that is already AWAITING_APPROVAL")
    fake, awx, L, ex = world()
    new_run(awx, L, T)  # noah + zoe, auto-release
    ex.release(RUN, T)
    tids = {c: store.get_line(L, RUN, T, c)["transfer_id"] for c in ("noah", "zoe")}
    for tid in tids.values():
        to_paid(awx, ex, tid)
    print("   run after both PAID:", store.get_run(L, RUN, T)["state"])
    bank_return(fake, tids["noah"])
    ex.poll_inflight()
    print("   after A returns:", store.get_run(L, RUN, T)["state"])
    usd_before = fake.balance(acct(T), "USD")
    bank_return(fake, tids["zoe"])  # no webhook arrives (endpoint down / missed)
    ex.poll_inflight()
    zoe = store.get_line(L, RUN, T, "zoe")
    check("RF poll_inflight detects B's late return while run is AWAITING_APPROVAL", zoe["state"] != "PAID",
          f"zoe={zoe['state']}, wallet USD +{fake.balance(acct(T), 'USD') - usd_before} back, Airwallex says "
          f"{fake.accounts[acct(T)].transfers[tids['zoe']]['status']}")
    print("   (webhook path would catch it: poll_one looks at every PAID line):", ex.poll_one(T, tids["zoe"]),
          store.get_line(L, RUN, T, "zoe")["state"])

    print("\n== 4b same residual with the one-line fix (poll PAID lines of any run that is not DRAFT)")
    fake, awx, L, ex = world()
    new_run(awx, L, T)
    ex.release(RUN, T)
    tids = {c: store.get_line(L, RUN, T, c)["transfer_id"] for c in ("noah", "zoe")}
    for tid in tids.values():
        to_paid(awx, ex, tid)
    bank_return(fake, tids["noah"])
    ex.poll_inflight()
    bank_return(fake, tids["zoe"])
    orig = store.get_run
    store.get_run = lambda db, r, t: (lambda x: x and {**x, "state": "RELEASED"} if x["state"] in (
        "AWAITING_APPROVAL", "READY", "AWAITING_FUNDS", "HELD") else x)(orig(db, r, t))  # == widen the filter
    try:
        ex.poll_inflight()
    finally:
        store.get_run = orig
    zoe = store.get_line(L, RUN, T, "zoe")
    check("RF with widened PAID filter detects B", zoe["state"] == "PLANNED" and zoe["attempt"] == 2, zoe["state"])

    print("\nsummary:", sum(ok for _, ok, _ in results), "pass /", len(results))


if __name__ == "__main__":
    main()
