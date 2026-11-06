"""Offline Ringfence arm for charges-request-id-duplicate-new-id (FakeAirwallex only, no network).

The fake answers a reused request_id with the LIVE Connected-Account-Transfer shape
  400 {code: request_id_duplicate, details: {source_id, source_type: transfer_id}}
(captured live 6 Nov, see charges-request-id-duplicate-new-id.out.txt) instead of the transfers shape
  400 {code: duplicate_request_id, details: {id}}.
That is what Ringfence meets the day fees move to Charges / CA transfers, or a transfers call returns the
code the transfer error table still lists as `request_id_duplicate (legacy)`.

A) fee sweep: a crash after the fee POST, then fees.charge again   -> today: fails closed, fee taken but unrecorded
B) same with the 3-line normaliser in awx._raise_for (proposed fix) -> adopts the original, one fee, recorded
C) payroll line re-submit with the legacy code                      -> today FAILED_TO_SUBMIT while the money is out; fixed: RECONCILED
D) a 'docs-following' handler (Resolution column: retry with a new request_id) -> two debits
Run: uv run python bench/probes/probe_request_id_duplicate_codes.py
"""
import os
import sys
import tempfile
import uuid
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
os.environ["RF_VAR"] = tempfile.mkdtemp(prefix="rfprobe-dup-")  # before ringfence reads var_dir()
os.environ["RF_MANDATE_KEY"], os.environ["RF_APPROVAL_KEY"] = "probe-mandate-key", "probe-approval-key"
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]

import httpx  # noqa: E402

from ringfence import awx as awx_mod, fees, store, verify  # noqa: E402
from ringfence.awx import Awx, AwxError  # noqa: E402
from ringfence.config import tenants  # noqa: E402
from ringfence.executor import Executor  # noqa: E402
from ringfence.fake_awx import FakeAirwallex  # noqa: E402
from ringfence.ledger import Ledger  # noqa: E402

verify.PUB_PATH = Path(os.environ["RF_VAR"]) / "cert_pub.pem"
from helpers import RUN, acct, new_run, sim  # noqa: E402

T = "kestrel"
ORIG_CREATE, ORIG_RAISE = FakeAirwallex._create_transfer, awx_mod._raise_for


def legacy_create(self, a, b):
    """Rewrite only the duplicate answer into the live CA-transfer shape."""
    r = ORIG_CREATE(self, a, b)
    if r.status_code == 400 and r.json().get("code") == "duplicate_request_id":
        tid = r.json()["details"]["id"]
        return httpx.Response(400, json={"code": "request_id_duplicate", "source": "request_id",
                                         "message": f"request_id '{b['request_id']}' has been used in the past.  please use a different request_id for this request",
                                         "details": {"source_id": tid, "source_type": "transfer_id"}})
    return r


DUP = {"duplicate_request_id", "request_id_duplicate"}


def fixed_raise_for(r):
    """Proposed fix for ringfence/awx.py:_raise_for: one duplicate code, one id key, for every caller."""
    try:
        return ORIG_RAISE(r)
    except AwxError as e:
        if e.code in DUP and isinstance(e.details, dict):
            d = e.details
            e.code, e.details = "duplicate_request_id", {**d, "id": d.get("id") or d.get("source_id") or d.get("wallet_transfer_id")}
        raise


def world():
    os.environ["RF_VAR"] = tempfile.mkdtemp(prefix="rfprobe-dup-")  # fresh ledger + registry per scenario
    fake = FakeAirwallex({k: t.account_id for k, t in tenants(fake=True).items()})
    awx = Awx(transport=fake.transport, tenant_map=tenants(fake=True), sleep=lambda s: None)
    return fake, awx, Ledger()


def done_run(fake, awx, L):
    ex = Executor(awx, L, sleep=lambda s: None)  # no on_done: the fee is driven by hand below
    new_run(awx, L, T)
    ex.release(RUN, T)
    for ln in store.get_lines(L, RUN, T):
        sim(awx, T, ln["transfer_id"], "SENT")
        sim(awx, T, ln["transfer_id"], "PAID")
    ex.poll_inflight()
    assert store.get_run(L, RUN, T)["state"] == "DONE"
    return ex


def fee_transfers(fake):
    return [t for t in fake.accounts[acct(T)].transfers.values() if t["request_id"].startswith("fee-")]


def kinds(L, k):
    return L.entries(kind=k, tenant=T)


def crash_after_fee_post(fake, awx, L):
    """Process dies after Airwallex debited the fee and before the ledger write (the lost-response case)."""
    real = fees.store.set_run
    fees.store.set_run = lambda *a, **k: (_ for _ in ()).throw(RuntimeError("crash after POST"))
    try:
        fees.charge(awx, L, RUN, T)
    except RuntimeError:
        pass
    finally:
        fees.store.set_run = real
    assert len(fee_transfers(fake)) == 1, "the fee was taken"


def scenario(fix: bool):
    fake, awx, L = world()
    done_run(fake, awx, L)
    crash_after_fee_post(fake, awx, L)
    FakeAirwallex._create_transfer = legacy_create
    awx_mod._raise_for = fixed_raise_for if fix else ORIG_RAISE
    try:
        res = [fees.charge(awx, L, RUN, T) for _ in range(3)]  # operator presses retry three times
    finally:
        FakeAirwallex._create_transfer, awx_mod._raise_for = ORIG_CREATE, ORIG_RAISE
    return fake, L, res, store.get_run(L, RUN, T)


if __name__ == "__main__":
    print("== A) today: fees.charge after a crash, the API answers with request_id_duplicate/source_id")
    fake, L, res, run = scenario(fix=False)
    fts = fee_transfers(fake)
    print("results:", res, "| fee transfers at Airwallex:", [(t["id"], str(t["transfer_amount"])) for t in fts])
    print("run.fee_charged:", run.get("fee_charged", "0"), "| fee_transfer_id:", run.get("fee_transfer_id"))
    print("platform [SIMULATED] credits:", [str(d["amount"]) for d in fake.accounts[fake.platform].deposits.values()])
    alerts = [e["payload"] for e in kinds(L, "ALERT")]
    print("ALERT rows:", alerts, "| FEE_CHARGED rows:", len(kinds(L, "FEE_CHARGED")))
    assert alerts and all(a.get("code") == "request_id_duplicate" for a in alerts) and not kinds(L, "FEE_CHARGED")
    assert res == ["DENIED"] * 3 and len(fts) == 1 and run.get("fee_charged", "0") in ("0", None)
    assert not fake.accounts[fake.platform].deposits, "no platform credit recorded"

    print("\n== B) with the 3-line normaliser in awx._raise_for")
    fake, L, res, run = scenario(fix=True)
    fts = fee_transfers(fake)
    print("results:", res, "| fee transfers:", [(t["id"], str(t["transfer_amount"])) for t in fts])
    print("run.fee_charged:", run.get("fee_charged"), "| fee_transfer_id:", run.get("fee_transfer_id"))
    assert res == ["CHARGED", "NONE", "NONE"] and len(fts) == 1
    assert run["fee_transfer_id"] == fts[0]["id"] and D(run["fee_charged"]) == fts[0]["transfer_amount"]

    print("\n== C) payroll line re-submitted after its create landed (same request_id), legacy code")
    for fix in (False, True):
        fake, awx, L = world()
        ex = done_run(fake, awx, L)
        ln = store.get_lines(L, RUN, T)[0]
        tid = ln["transfer_id"]
        with L.tx() as tx:  # model: create landed, response lost, lookup by request_id lagged -> one re-create, same id
            store.set_line(tx, RUN, T, ln["contractor_id"], "UNKNOWN", transfer_id=None)
        ln = store.get_line(L, RUN, T, ln["contractor_id"]) | {"transfer_id": tid}
        before = len(fake.accounts[acct(T)].transfers)
        FakeAirwallex._create_transfer = legacy_create
        awx_mod._raise_for = fixed_raise_for if fix else ORIG_RAISE
        try:
            ex._submit(awx.for_tenant(T), ln)
        finally:
            FakeAirwallex._create_transfer, awx_mod._raise_for = ORIG_CREATE, ORIG_RAISE
        after = store.get_line(L, RUN, T, ln["contractor_id"])
        print(f"fix={fix}: line {ln['contractor_id']} state {ln['state']} -> {after['state']} error={after.get('error')} "
              f"transfers {before} -> {len(fake.accounts[acct(T)].transfers)} (original {ln['transfer_id']} is PAID)")
        assert len(fake.accounts[acct(T)].transfers) == before
        assert after["state"] == ("PAID" if fix else "FAILED_TO_SUBMIT")

    print("\n== D) docs-following reference handler (Airwallex Resolution: 'Retry the request with a new request_id')")
    fake, awx, L = world()
    FakeAirwallex._create_transfer = legacy_create
    c = awx.for_tenant(T)
    from ringfence import beneficiaries as bmod
    from ringfence.setup_demo import setup
    reg = bmod.load_registry() if bmod.load_registry()["tenants"] else setup(awx)
    fbid = reg["tenants"][T]["fee_beneficiary"]
    body = {"request_id": "prb-docs-handler-0001", "beneficiary_id": fbid, "transfer_amount": D("1.50"),
            "transfer_currency": "GBP", "source_currency": "GBP", "transfer_method": "LOCAL",
            "reason": "professional_business_services", "reference": "PRB fee"}

    def docs_following_create(c, body):
        """10 lines, as the Charges/CA-transfer error table says."""
        try:
            return c.post_money("/transfers/create", body)
        except AwxError as e:
            if e.code != "request_id_duplicate":
                raise
            return c.post_money("/transfers/create", {**body, "request_id": uuid.uuid4().hex[:32]})

    bal0 = c.balances()["GBP"]
    c.post_money("/transfers/create", body)  # attempt 1 lands; its response is lost (timeout)
    docs_following_create(c, body)          # retry with the SAME id, per the idempotency guidance -> dup -> new id
    FakeAirwallex._create_transfer = ORIG_CREATE
    debits = [t for t in fake.accounts[acct(T)].transfers.values() if t["beneficiary_id"] == fbid]
    print("fee debits:", [(t["request_id"], str(t["transfer_amount"])) for t in debits],
          "| GBP balance", bal0, "->", c.balances()["GBP"])
    assert len(debits) == 2 and bal0 - c.balances()["GBP"] == D("3.00")
    print("\nALL ASSERTS PASSED")
