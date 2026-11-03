import shutil
from datetime import date
from decimal import Decimal as D

import pytest
from helpers import FakeLLM, acct

from ringfence import inbox, store
from ringfence.agent import loop, prompts
from ringfence.agent.tools import ToolBox
from ringfence.config import ROOT
from ringfence.orchestrator import Orchestrator
from ringfence.setup_demo import setup


@pytest.fixture
def orch(awx, L):
    setup(awx)
    o = Orchestrator(awx, L)
    o.ex._sleep = lambda s: None
    return o


def drop(tenant, name):
    shutil.copy(ROOT / "demo" / "attacks" / f"{name}.txt", inbox.drop_dir(tenant) / f"{name}.txt")


def kinds(L, kind, tenant=None):
    return [e["payload"] for e in L.entries(kind=kind, tenant=tenant)]


def nothing_moved(fake):
    return all(not fake.accounts[acct(t)].transfers for t in ("northwind", "kestrel", "harbour"))


def test_tool_schemas_are_strict_and_none_can_move_money():
    names = {t["name"] for t in prompts.TOOLS}
    assert not names & {"transfer", "pay", "approve", "release", "create_beneficiary", "sign_mandate", "convert"}
    for t in prompts.TOOLS:
        s = t["input_schema"]
        assert t["strict"] and s["additionalProperties"] is False and set(s["required"]) == set(s["properties"])
        assert "tenant" not in s["properties"]  # the harness binds the tenant, never the model


def test_scripted_tick_quarantines_the_bank_change_flags_the_injection_and_pays_nobody(orch, fake, L):
    drop("northwind", "bank_change_northwind")
    res = loop.run_tick(orch, "northwind", mode="scripted")
    assert res.mode == "offline agent" and res.next_step == "WAIT_APPROVAL"
    rid = res.run_id
    (q,) = orch.diff(rid, "northwind")["bank_changes"]
    assert q["status"] == "ACTIVE" and q["last4"] == "9901"
    assert res.flagged == ["bank_change_northwind"] and kinds(L, "ALERT", "northwind")
    ada = store.get_line(L, rid, "northwind", "ada")
    assert D(ada["amount"]) == D("450.00") and ada["state"] == "PLANNED"
    assert store.get_run(L, rid, "northwind")["state"] == "AWAITING_APPROVAL" and nothing_moved(fake)
    assert "quarantined" in res.explanation


def test_scripted_tick_records_a_rate_request_without_applying_it(orch, fake, L):
    drop("kestrel", "rate_kestrel")
    res = loop.run_tick(orch, "kestrel", mode="scripted")
    (r,) = orch.diff(res.run_id, "kestrel")["rate_requests"]
    assert r["contractor_id"] == "noah" and r["new_rate"] == "95" and r["over_25pct"]
    noah = store.get_line(L, res.run_id, "kestrel", "noah")
    assert D(noah["amount"]) == D(noah["hours"]) * D(r["old_rate"])


def test_harbour_scripted_tick_requests_funding_and_quarantines_omar(orch, fake, L):
    drop("harbour", "bank_change_harbour")
    drop("harbour", "injection_harbour")
    res = loop.run_tick(orch, "harbour", mode="scripted")
    assert res.next_step == "WAIT_FUNDS" and res.flagged == ["injection_harbour"]
    assert [b["contractor_id"] for b in orch.diff(res.run_id, "harbour")["bank_changes"]] == ["omar"]
    assert kinds(L, "FUNDING_REQUESTED", "harbour")[0]["currency"] == "AUD" and nothing_moved(fake)


def test_a_document_is_read_once_and_a_second_tick_changes_nothing(orch, L):
    drop("northwind", "bank_change_northwind")
    first = loop.run_tick(orch, "northwind", mode="scripted")
    loop.run_tick(orch, "northwind", mode="scripted")
    assert len(L.entries(tenant="northwind", kind="BENEFICIARY_QUARANTINED")) == 1
    assert store.get_run(L, first.run_id, "northwind")["state"] == "AWAITING_APPROVAL"


def test_a_malicious_model_is_denied_at_every_step_and_no_money_moves(orch, fake, L):
    rid = orch.create_run("northwind", date(2026, 11, 14))
    bad = [("propose_timesheet", {"doc_id": "x", "contractor_id": "noah", "hours": "10"}),  # another tenant's contractor
           ("propose_timesheet", {"doc_id": "x", "contractor_id": "ada", "hours": "80"}),  # not the parsed hours
           ("propose_timesheet", {"doc_id": "x", "contractor_id": "ada", "hours": 10}),  # wrong type
           ("propose_rate_change", {"doc_id": "x", "contractor_id": "ada", "new_rate": "-1", "note": ""}),
           ("propose_bank_change", {"doc_id": "x", "contractor_id": "ada", "bank_details": {"evil": "1"}}),
           ("transfer_money", {"to": "me", "amount": "1000000"})]
    llm = FakeLLM([bad, [("propose_rate_change", {"doc_id": "x", "contractor_id": "ada", "new_rate": "450", "note": "10x"}),
                         ("hold_run", {"reason_code": "BOGUS", "note": ""}),
                         ("finish_tick", {"headline": "done", "explanation": "ok", "next_step": "WAIT_APPROVAL"})]])
    res = loop.run_tick(orch, "northwind", llm=llm)
    assert res.mode == "claude" and [c["ok"] for c in res.calls] == [False] * 6 + [True, False, True]
    assert len(kinds(L, "GATE_DENY", "northwind")) == 7
    assert D(store.get_line(L, rid, "northwind", "ada")["amount"]) == D("450.00")
    assert store.get_run(L, rid, "northwind")["state"] == "DRAFT" and nothing_moved(fake)


def test_model_gets_documents_wrapped_as_untrusted(orch, L):
    drop("northwind", "bank_change_northwind")
    rid = orch.create_run("northwind", date(2026, 11, 14))
    text, err = ToolBox(orch, "northwind", rid).dispatch("read_inbox", {})
    assert not err and '<untrusted_document id="bank_change_northwind" source="email">' in text


@pytest.mark.parametrize("turn", ["refusal", "max_tokens"])
def test_refusal_or_truncation_falls_back_to_the_scripted_agent(orch, fake, L, turn):
    res = loop.run_tick(orch, "kestrel", llm=FakeLLM([turn]))
    assert res.mode == "offline agent" and res.next_step == "PAYING" and res.calls == []


def test_two_api_errors_fall_back_to_the_scripted_agent(orch):
    res = loop.run_tick(orch, "kestrel", llm=FakeLLM([ConnectionError("x"), ConnectionError("x")]))
    assert res.mode == "offline agent" and "ConnectionError" in res.note


def test_more_than_six_tool_calls_in_a_turn_are_refused(orch):
    turn = [("get_run", {})] * 7 + [("finish_tick", {"headline": "h", "explanation": "e", "next_step": "HOLD"})]
    res = loop.run_tick(orch, "kestrel", llm=FakeLLM([turn]))
    assert [c["ok"] for c in res.calls] == [True] * 6 + [False, False]


def test_a_tick_without_finish_tick_writes_a_generic_note(orch, L):
    res = loop.run_tick(orch, "kestrel", llm=FakeLLM([[("get_run", {})], []]))
    assert res.headline.endswith("tick ended") and any(p.get("generic") for p in kinds(L, "AGENT_NOTE", "kestrel"))


def test_a_rejected_timesheet_creates_no_run(orch, L, monkeypatch):
    monkeypatch.setattr(inbox, "INBOX", ROOT / "tests")  # no such csv there
    res = loop.run_tick(orch, "kestrel", mode="scripted")
    assert res.run_id is None and res.next_step == "HOLD" and orch.runs() == []
