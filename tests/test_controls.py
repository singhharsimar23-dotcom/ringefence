from datetime import date
from decimal import Decimal as D

import pytest
from helpers import acct

from ringfence import shadow, store
from ringfence.orchestrator import Orchestrator, Refused
from ringfence.setup_demo import setup

PAY = date(2026, 11, 14)
NEW_BANK = {"country": "GB", "bank_name": "Barclays", "routing_type": "sort_code", "routing_value": "200000",
            "account_number": "99999901"}


@pytest.fixture
def orch(awx, L, tmp_path, monkeypatch):
    monkeypatch.setattr("ringfence.orchestrator.ROOT", tmp_path)  # reset() moves artifacts/certs under ROOT
    setup(awx)
    o = Orchestrator(awx, L)
    o.ex._sleep = lambda s: None
    return o


def role(L, t):
    return store.latest_mandate(L, t).mandate.approver_role


def test_bank_change_is_quarantined_and_does_not_touch_the_run(orch, L):
    rid = orch.create_run("northwind", PAY)
    old = store.get_line(L, rid, "northwind", "ada")["beneficiary_id"]
    q = orch.propose_bank_change(rid, "northwind", "ada", NEW_BANK, "email-1", "maya")
    assert q["valid"]
    assert store.get_line(L, rid, "northwind", "ada")["beneficiary_id"] == old
    assert store.get_run(L, rid, "northwind")["beneficiary_editors"] == ["maya"]
    assert orch.diff(rid, "northwind")["bank_changes"][0]["last4"] == "9901"
    assert orch.propose_bank_change(rid, "northwind", "ada", NEW_BANK, "email-1", "maya")["id"] == q["id"]  # idempotent


def test_callback_needs_a_different_person_and_a_reference_then_voids_the_old_approval(orch, fake, L):
    rid = orch.create_run("northwind", PAY)
    orch.submit(rid, "northwind")
    r = role(L, "northwind")
    orch.approve(rid, "northwind", "priya", r)
    q = orch.propose_bank_change(rid, "northwind", "ada", NEW_BANK, "email-1", "maya")
    with pytest.raises(PermissionError):
        orch.confirm_bank_change("northwind", q["id"], "maya", r, "call-4411")  # the requester cannot confirm
    with pytest.raises(PermissionError):
        orch.confirm_bank_change("northwind", q["id"], "priya", "viewer", "call-4411")  # wrong role
    with pytest.raises(ValueError):
        orch.confirm_bank_change("northwind", q["id"], "priya", r, "x")  # no callback reference
    new_id = orch.confirm_bank_change("northwind", q["id"], "priya", r, "call-4411")
    assert store.get_line(L, rid, "northwind", "ada")["beneficiary_id"] == new_id
    run = store.get_run(L, rid, "northwind")
    assert run["state"] == "AWAITING_APPROVAL"  # approval was over the old batch hash
    assert {ln["state"] for ln in store.get_lines(L, rid, "northwind")} == {"PLANNED"}
    assert orch.advance(rid, "northwind") == "AWAITING_APPROVAL"
    assert fake.accounts[acct("northwind")].transfers == {}
    orch.approve(rid, "northwind", "priya", r)
    assert orch.advance(rid, "northwind") == "RELEASED"
    t = [x for x in fake.accounts[acct("northwind")].transfers.values() if x["beneficiary_id"] == new_id]
    assert len(t) == 1


def test_rate_request_is_recorded_flagged_and_never_applied(orch, L):
    rid = orch.create_run("northwind", PAY)
    before = store.get_line(L, rid, "northwind", "ada")["amount"]
    req = orch.note_rate_request(rid, "northwind", "ada", D(300), "email-2", "pay me 3x")
    assert req["over_25pct"]
    assert store.get_line(L, rid, "northwind", "ada")["amount"] == before
    assert orch.diff(rid, "northwind")["rate_requests"][0]["new_rate"] == "300"


def test_hold_blocks_release_and_resume_goes_back_through_the_gate(orch, fake, L):
    rid = orch.create_run("kestrel", PAY)
    assert orch.submit(rid, "kestrel") == "READY"
    orch.hold(rid, "kestrel", "operator_hold", "checking")
    assert orch.advance(rid, "kestrel") == "HELD"
    assert fake.accounts[acct("kestrel")].transfers == {}
    assert orch.resume(rid, "kestrel") == "READY"
    assert orch.advance(rid, "kestrel") == "RELEASED"
    with pytest.raises(Refused):
        orch.hold(rid, "kestrel", "too_late")


def test_kill_switch_stops_release_and_clearing_it_allows_it(orch, fake, L):
    rid = orch.create_run("kestrel", PAY)
    orch.submit(rid, "kestrel")
    orch.set_kill_switch(True, "maya")
    assert orch.advance(rid, "kestrel") == "HELD"  # the gate holds the run; it does not silently retry
    assert fake.accounts[acct("kestrel")].transfers == {}
    orch.set_kill_switch(False, "maya")
    assert orch.resume(rid, "kestrel") == "READY"
    assert orch.advance(rid, "kestrel") == "RELEASED"


def test_diff_shows_changes_totals_and_shortfall(orch, L):
    rid = orch.create_run("harbour", PAY)
    orch.submit(rid, "harbour")
    d = orch.diff(rid, "harbour")
    assert d["totals"] == {"AUD": "1240.17"} and d["shortfall"] == {"AUD": "1240.17"}
    assert d["approver_role"] == role(L, "harbour")
    n = orch.diff(orch.create_run("northwind", PAY), "northwind")
    assert n["unchanged"]["count"] + len(n["changes"]) == 3


def test_reset_archives_starts_clean_and_keeps_the_archive_chain(orch, L, tmp_path):
    rid = orch.create_run("kestrel", PAY)
    orch.submit(rid, "kestrel")
    old_epoch = L.epoch()
    orch.reset("maya")
    assert L.epoch() != old_epoch or L.entries(kind="RESET")
    assert orch.runs() == []
    assert L.verify().ok
    assert list(L.entries(kind="RESET"))
    assert orch.create_run("kestrel", PAY)  # same pay date works again


def test_shadow_total_pools_every_tenant_for_display_only(awx):
    setup(awx)
    total, complete = shadow.naive_total(awx, "AUD")
    assert total > D(1000000) and complete
