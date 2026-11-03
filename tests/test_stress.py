"""BUILD_SPEC section 11 rows that the module tests do not already cover. Invariants run after every test."""
import threading
from datetime import date
from decimal import Decimal as D

import pytest
from helpers import RUN, acct, new_run
from invariants import assert_invariants

from ringfence import store
from ringfence.orchestrator import Orchestrator
from ringfence.setup_demo import setup

PAY = date(2026, 11, 14)


@pytest.fixture(autouse=True)
def _invariants(L, fake):
    yield
    assert_invariants(L, fake)


@pytest.fixture
def orch(awx, L, tmp_path, monkeypatch):
    monkeypatch.setattr("ringfence.orchestrator.ROOT", tmp_path)
    setup(awx)
    o = Orchestrator(awx, L)
    o.ex._sleep = lambda s: None
    return o


def harbour(orch, fake):
    """A Harbour run that is short in AUD, with its open funding request and its AUD global account."""
    rid = orch.create_run("harbour", PAY)
    assert orch.submit(rid, "harbour") == "AWAITING_FUNDS"
    req = next(e["payload"] for e in orch.L.entries(run_id=rid, kind="FUNDING_REQUESTED", tenant="harbour"))
    return rid, req


def state(orch, rid, t="harbour"):
    return store.get_run(orch.L, rid, t)["state"]


def short(orch, rid):
    return D(store.get_run(orch.L, rid, "harbour")["shortfall"]["AUD"])


def pay_into(fake, req, amount, **kw):
    fake.deposit(acct("harbour"), req["ga_id"], D(amount), kw.get("reference", req["reference"]), kw.get("status", "SETTLED"))


def test_a_deposit_one_cent_short_stays_open_and_the_remainder_under_the_same_reference_completes_it(orch, fake):
    rid, req = harbour(orch, fake)
    pay_into(fake, req, D(req["amount"]) - D("0.01"))
    assert orch.advance(rid, "harbour") == "AWAITING_FUNDS"
    assert orch.L.entries(kind="FUNDING_MATCHED") == []
    pay_into(fake, req, "0.01")
    assert orch.advance(rid, "harbour") == "AWAITING_APPROVAL"
    assert orch.L.entries(kind="FUNDING_MATCHED")[0]["payload"]["amount"] == req["amount"]


def test_two_deposits_with_the_same_reference_summing_to_the_need_cover_it(orch, fake):
    rid, req = harbour(orch, fake)
    need = D(req["amount"])
    pay_into(fake, req, need / 2)
    assert orch.advance(rid, "harbour") == "AWAITING_FUNDS"
    pay_into(fake, req, need - need / 2)
    assert orch.advance(rid, "harbour") == "AWAITING_APPROVAL"


@pytest.mark.parametrize("why", ["wrong_reference", "wrong_tenant", "wrong_currency", "rejected"])
def test_a_deposit_that_is_not_ours_never_changes_the_run(orch, fake, why):
    rid, req = harbour(orch, fake)
    need = D(req["amount"])
    if why == "wrong_reference":
        pay_into(fake, req, need, reference="RF-HAR-NOPE")
        assert orch.advance(rid, "harbour") == "AWAITING_FUNDS"  # unmatched; balance in the right currency still rose
        return
    if why == "wrong_tenant":
        ga = next(iter(fake.accounts[acct("kestrel")].gas))
        fake.deposit(acct("kestrel"), ga, need, req["reference"], "SETTLED")
    elif why == "wrong_currency":
        ga = next(g["id"] for g in fake.accounts[acct("harbour")].gas.values() if g["required_features"][0]["currency"] != "AUD")
        fake.deposit(acct("harbour"), ga, need, req["reference"], "SETTLED")
    else:
        pay_into(fake, req, need, status="REJECTED")
    assert orch.advance(rid, "harbour") == "AWAITING_FUNDS"
    assert short(orch, rid) == need


def test_a_deposit_reversed_before_release_sends_the_run_back_for_funds(orch, fake):
    rid, req = harbour(orch, fake)
    pay_into(fake, req, req["amount"])
    assert orch.advance(rid, "harbour") == "AWAITING_APPROVAL"
    orch.approve(rid, "harbour", "lee", store.latest_mandate(orch.L, "harbour").mandate.approver_role)
    dep = next(iter(fake.accounts[acct("harbour")].deposits.values()))
    fake.reverse_deposit(acct("harbour"), dep["id"])
    assert orch.advance(rid, "harbour") == "AWAITING_FUNDS"  # the gate saw the empty balance; nothing was sent
    assert not fake.all_transfers(acct("harbour"))
    for _ in range(2):  # and it asks again rather than waiting on a request that is already matched
        orch.advance(rid, "harbour")
    open_ = orch.L.query("SELECT 1 FROM funding_requests WHERE run_id=? AND tenant='harbour' AND status='OPEN'", (rid,))
    assert open_


def test_a_deposit_reversed_after_release_is_an_alert_not_a_second_payment(orch, fake):
    rid, req = harbour(orch, fake)
    pay_into(fake, req, req["amount"])
    orch.advance(rid, "harbour")
    orch.approve(rid, "harbour", "lee", store.latest_mandate(orch.L, "harbour").mandate.approver_role)
    assert orch.advance(rid, "harbour") in ("RELEASED", "DONE")
    sent = len(fake.all_transfers(acct("harbour")))
    dep = next(iter(fake.accounts[acct("harbour")].deposits.values()))
    fake.reverse_deposit(acct("harbour"), dep["id"])
    orch.advance(rid, "harbour")
    orch.poll()
    assert len(fake.all_transfers(acct("harbour"))) == sent


def test_twenty_threads_releasing_one_run_send_each_line_once(awx, fake, L):
    new_run(awx, L, "kestrel")
    L.append("APPROVED", {"auto_release": True, "rule": "mandate auto_release if_no_diff, no changes"}, RUN, "kestrel")
    from ringfence.executor import Executor
    ex = Executor(awx, L, sleep=lambda s: None)
    gate = threading.Barrier(20)

    def go():
        gate.wait()
        ex.release(RUN, "kestrel")

    ts = [threading.Thread(target=go) for _ in range(20)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert len(fake.all_transfers(acct("kestrel"))) == 2  # noah and zoe
