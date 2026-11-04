from decimal import Decimal as D

import pytest
from helpers import FakeLLM, acct
from invariants import assert_invariants

from ringfence import attacks, inbox, store
from ringfence import beneficiaries as ben
from ringfence.agent import loop
from ringfence.orchestrator import Orchestrator
from ringfence.setup_demo import setup


def test_the_library_is_nine_goals_by_four_framings_and_the_files_match():
    assert len(attacks.GOALS) == 9 and len(attacks.FRAMINGS) == 4 and len(attacks.library()) == 36
    for g, f in attacks.library():
        assert (attacks.DIR / f"{attacks.doc_name(g, f)}.txt").read_text(encoding="utf-8") == attacks.render(g, f)
    assert set(attacks.NO_TOOL) <= set(attacks.GOALS)


def test_goals_without_a_tool_have_no_evil_calls_and_the_rest_do():
    for g in attacks.GOALS:
        assert bool(attacks.evil_calls(g, "northwind", "d")) == (g not in attacks.NO_TOOL)


def test_wants_does_not_fire_on_honest_calls():
    honest = [("propose_timesheet", {"doc_id": "d", "contractor_id": "ada", "hours": "10"}),
              ("propose_rate_change", {"doc_id": "d", "contractor_id": "ada", "new_rate": "46", "note": ""})]
    for g in attacks.GOALS:
        assert not attacks.wants(g, "northwind", honest)


@pytest.mark.parametrize("goal", [g for g in attacks.GOALS if g not in attacks.NO_TOOL])
def test_an_obedient_agent_is_fooled_but_no_wrong_payment_leaves(awx, fake, L, goal):
    setup(awx)
    o = Orchestrator(awx, L)
    o.ex._sleep = lambda s: None
    doc = attacks.doc_name(goal, "todo")
    (inbox.drop_dir("northwind") / f"{doc}.txt").write_text(attacks.render(goal, "todo"), encoding="utf-8")
    calls = attacks.evil_calls(goal, "northwind", doc)
    llm = FakeLLM([[("read_inbox", {}), *calls, ("submit_for_approval", {"summary": "as told"}),
                    ("finish_tick", {"headline": "h", "explanation": "e", "next_step": "WAIT_APPROVAL"})]])
    res = loop.run_tick(o, "northwind", llm=llm)
    assert attacks.wants(goal, "northwind", calls)
    run = store.get_run(L, res.run_id, "northwind")
    if run["state"] == "AWAITING_APPROVAL":
        o.approve(res.run_id, "northwind", "approver", store.latest_mandate(L, "northwind").mandate.approver_role)
        o.advance(res.run_id, "northwind")
    own = {*ben.load_registry()["tenants"]["northwind"]["beneficiaries"].values()}
    fee = ben.load_registry()["tenants"]["northwind"]["fee_beneficiary"]
    assert {t["beneficiary_id"] for t in fake.accounts[acct("northwind")].transfers.values()} <= own | {fee}
    assert_invariants(L, fake)
    ada = store.get_line(L, res.run_id, "northwind", "ada")  # the trusted timesheet still decides: 10 h at the registry rate
    assert D(ada["hours"]) == 10 and D(ada["amount"]) == D("450.00")
