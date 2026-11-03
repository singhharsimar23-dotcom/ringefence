import pytest
from helpers import acct
from invariants import assert_invariants

from ringfence import copy, store
from ringfence.agent import loop
from ringfence.orchestrator import Orchestrator
from ringfence.scenarios import SCENARIOS, Simulator
from ringfence.setup_demo import setup


@pytest.fixture(autouse=True)
def _invariants(L, fake):
    yield
    assert_invariants(L, fake)



@pytest.fixture
def world(awx, L):
    setup(awx)
    o = Orchestrator(awx, L)
    o.ex._sleep = lambda s: None
    rid = lambda: o.run_id(loop.pay_date())
    sim = Simulator(o, rid, lambda t: loop.run_tick(o, t, mode="scripted"))
    return o, sim, rid


def approve(o, L, rid, tenant):
    o.approve(rid(), tenant, "approver", store.latest_mandate(L, tenant).mandate.approver_role)


def test_every_card_has_a_handler():
    for name in SCENARIOS:
        assert hasattr(Simulator, f"_{name}")


def test_double_click_pays_each_line_once(world, L, fake):
    o, sim, rid = world
    sim._tick("northwind")
    approve(o, L, rid, "northwind")
    r = sim.run("double_click")
    assert r["ok"], r["summary"]
    assert len(fake.all_transfers(acct("northwind"))) == 3


def test_network_drop_still_leaves_one_payment_per_line(world, fake):
    sim = world[1]
    sim._tick("kestrel")
    r = sim.run("network_drop")
    assert r["ok"], r["summary"]
    assert len(fake.all_transfers(acct("kestrel"))) == 2


def test_rate_move_sends_the_run_back_to_approval_and_pays_nobody(world, L, fake):
    o, sim, rid = world
    sim._tick("northwind")
    approve(o, L, rid, "northwind")
    r = sim.run("rate_move")
    assert r["ok"], r["summary"]
    assert store.get_run(L, rid(), "northwind")["state"] == "AWAITING_APPROVAL"
    assert not fake.all_transfers(acct("northwind"))


def test_tamper_breaks_the_chain_at_the_row_and_repair_restores_it(world, L):
    o, sim, rid = world
    sim._tick("kestrel")
    o.advance(rid(), "kestrel")
    r = sim.run("tamper_ledger")
    assert r["ok"] and not L.verify().ok and L.verify().bad_seq == r["bad_seq"]
    assert sim.run("tamper_ledger")["ok"] and L.verify().ok


def test_cross_tenant_probes_are_all_refused(world):
    assert world[1].run("cross_tenant_call")["ok"]


def test_bank_change_email_quarantines_and_pays_nobody(world, fake):
    r = world[1].run("bank_change_email")
    assert r["ok"] and "quarantined" in r["summary"]
    assert not fake.all_transfers(acct("northwind"))


def test_cards_that_need_a_run_say_so_instead_of_failing(world):
    r = world[1].run("rate_move")
    assert not r["ok"] and "ready to send" in r["summary"]


def test_late_return_and_topup_story_beats(world, L, fake):
    o, sim, rid = world
    sim._tick("harbour")
    assert sim.run("harbour_topup")["ok"]
    assert sim.run("other_tenant_deposit")["ok"]
    sim._tick("northwind")
    approve(o, L, rid, "northwind")
    o.advance(rid(), "northwind")
    from ringfence.scenarios import settle_step
    for _ in range(3):
        settle_step(o.awx, L, rid(), "northwind")
        o.poll()
    o.advance(rid(), "northwind")
    assert sim.run("late_return")["ok"]


def test_copy_covers_every_ledger_entry_without_crashing(world, L):
    o, sim, rid = world
    sim._tick("kestrel")
    o.advance(rid(), "kestrel")
    rows = [copy.timeline_row(e) for e in L.entries()]
    assert any(rows)
    for row in filter(None, rows):
        assert row["text"] and row["phase"]
