from datetime import date
from decimal import Decimal as D

import pytest
from helpers import acct, sim
from test_funding import harbour_ga

from ringfence import inbox, store
from ringfence.orchestrator import Orchestrator, Refused
from ringfence.setup_demo import setup

PAY = date(2026, 11, 14)


@pytest.fixture
def orch(awx, L):
    setup(awx)
    o = Orchestrator(awx, L)
    o.ex._sleep = lambda s: None
    return o


def test_kestrel_unchanged_timesheet_auto_releases_without_approval(orch, fake, L):
    rid = orch.run_id(PAY)
    assert orch.create_run("kestrel", PAY) == rid
    assert orch.submit(rid, "kestrel") == "READY"
    assert orch.advance(rid, "kestrel") == "RELEASED"
    assert len(fake.accounts[acct("kestrel")].transfers) == 2
    assert L.entries(kind="APPROVED")[0]["payload"]["auto_release"] is True
    assert orch.advance(rid, "kestrel") == "RELEASED"  # a repeat tick is a no-op
    assert len(fake.accounts[acct("kestrel")].transfers) == 2


def test_northwind_needs_the_right_role_then_pays(orch, fake, L):
    rid = orch.create_run("northwind", PAY)
    assert orch.submit(rid, "northwind") == "AWAITING_APPROVAL"
    assert orch.advance(rid, "northwind") == "AWAITING_APPROVAL"  # nothing moves without approval
    assert fake.accounts[acct("northwind")].transfers == {}
    with pytest.raises(Refused):
        orch.approve(rid, "northwind", "intruder", "viewer")
    assert orch.approve(rid, "northwind", "pat", store.latest_mandate(L, "northwind").mandate.approver_role) == "READY"
    assert orch.advance(rid, "northwind") == "RELEASED"
    assert len(fake.accounts[acct("northwind")].transfers) == 3
    with pytest.raises(Refused):
        orch.submit(rid, "northwind")  # not a DRAFT any more


def test_harbour_short_asks_for_funds_then_pays_after_a_matched_deposit(orch, fake, L):
    rid = orch.create_run("harbour", PAY)
    assert orch.submit(rid, "harbour") == "AWAITING_FUNDS"
    (req,) = L.entries(kind="FUNDING_REQUESTED")
    assert req["payload"]["currency"] == "AUD" and D(req["payload"]["amount"]) == D("1240.17")
    assert orch.advance(rid, "harbour") == "AWAITING_FUNDS"
    fake.deposit(acct("harbour"), harbour_ga(fake)["id"], D("1240.17"), req["payload"]["reference"], "SETTLED")
    assert orch.advance(rid, "harbour") == "AWAITING_APPROVAL"
    role = store.latest_mandate(L, "harbour").mandate.approver_role
    orch.approve(rid, "harbour", "hana", role)
    assert orch.advance(rid, "harbour") == "RELEASED"
    assert len(fake.accounts[acct("harbour")].transfers) == 3


def test_only_the_tenants_own_funds_count(orch, fake, L):
    """Money sitting in Northwind's AUD or Kestrel's accounts never covers Harbour."""
    rid = orch.create_run("harbour", PAY)
    fake.accounts[acct("northwind")].balances["AUD"] = D(999999)
    assert orch.submit(rid, "harbour") == "AWAITING_FUNDS"


def test_bad_timesheet_and_foreign_contractor_are_rejected(orch):
    with pytest.raises(inbox.TimesheetError):
        inbox.parse_timesheet("kestrel", "contractor_id,hours\nada,10\n")
    with pytest.raises(inbox.TimesheetError):
        inbox.parse_timesheet("kestrel", "contractor_id,hours\nnoah,81\n")
    with pytest.raises(inbox.TimesheetError):
        inbox.parse_timesheet("kestrel", "contractor_id,hours\nnoah,1\nnoah,2\n")


def test_create_run_refuses_a_contractor_from_another_tenant(orch):
    with pytest.raises(KeyError):
        orch.create_run("kestrel", PAY, {"ada": D(1)})


def test_a_changed_amount_blocks_kestrel_auto_release(orch):
    rid = orch.create_run("kestrel", PAY, {"noah": D(11), "zoe": D(8)})
    assert orch.submit(rid, "kestrel") == "AWAITING_APPROVAL"


def test_poll_pays_out_and_charges_the_fee_once(orch, fake, L):
    rid = orch.create_run("kestrel", PAY)
    orch.submit(rid, "kestrel")
    orch.advance(rid, "kestrel")
    for t in list(fake.accounts[acct("kestrel")].transfers.values()):
        sim(orch.awx, "kestrel", t["id"], "SENT")
        sim(orch.awx, "kestrel", t["id"], "PAID")
    orch.poll()
    orch.poll()
    assert store.get_run(L, rid, "kestrel")["state"] == "DONE"
    assert len(L.entries(kind="FEE_CHARGED")) == 1
    assert L.verify().ok


def test_scripted_demo_pays_everyone_once_on_the_fake(monkeypatch, capsys):
    from ringfence import __main__ as cli
    monkeypatch.setattr("sys.argv", ["ringfence", "--backend", "fake", "demo"])
    assert cli.main() == 0
    out = capsys.readouterr().out
    assert "kestrel: READY" in out and "harbour: AWAITING_FUNDS" in out and "[SIMULATED] top-up" in out
    assert out.count("DONE") == 3 and "ledger: OK" in out
