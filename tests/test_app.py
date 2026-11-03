import threading
from concurrent.futures import Future

import pytest
from fastapi.testclient import TestClient
from invariants import assert_invariants

from ringfence import copy
from ringfence.app import Engine, create_app
from ringfence.setup_demo import setup


@pytest.fixture(autouse=True)
def _invariants(L, fake):
    yield
    assert_invariants(L, fake)



@pytest.fixture
def E(awx, L):
    setup(awx)
    e = Engine(awx, L, "fake", "scripted", idle=3600, release_delay=0)  # idle=3600: the test drives the autopilot
    e.o.ex._sleep = lambda s: None
    return e


@pytest.fixture
def c(E):
    return TestClient(create_app(E))


def cycle(E, n=1):
    for _ in range(n):
        E.call(E._autopilot)


def start(c, E, user="maya"):
    """/api/start only queues the job; E.call is a barrier behind it on the single worker."""
    r = c.post("/api/start", json={"user": user})
    E.call(lambda: None)
    return r


def lane(c, t):
    return c.get("/api/state").json()["lanes"][t]


def test_empty_state_offers_the_start_action(c):
    s = c.get("/api/state").json()
    assert s["agent"] == "offline agent" and s["kill"]["on"] is False
    assert all(ln["state"] is None and ln["text"]["action"] == "start" for ln in s["lanes"].values())
    assert c.get("/").status_code == 200


def test_start_puts_each_employer_in_its_own_state_and_harbour_gets_a_funding_card(c, E):
    assert start(c, E).json()["ok"]
    assert lane(c, "kestrel")["state"] == "READY"
    assert lane(c, "northwind")["state"] == "AWAITING_APPROVAL" and lane(c, "northwind")["text"]["action"] == "approve"
    h = lane(c, "harbour")
    assert h["state"] == "AWAITING_FUNDS" and h["funding"]["currency"] == "AUD" and h["text"]["action"] == "copy_funding"
    assert lane(c, "northwind")["approve_label"].startswith("Approve ")


def test_only_the_named_approver_can_approve(c, E):
    start(c, E)
    r = c.post("/api/approve", json={"tenant": "northwind", "user": "maya"})
    assert r.status_code == 409 and "may not approve" in r.json()["detail"]
    assert c.post("/api/approve", json={"tenant": "northwind", "user": "nobody"}).status_code == 422
    assert c.post("/api/approve", json={"tenant": "bogus", "user": "priya"}).status_code == 422
    assert c.post("/api/approve", json={"tenant": "northwind", "user": "priya"}).json()["ok"]


def test_the_whole_story_runs_to_done_through_the_api_and_the_proof_passes(c, E, fake):
    start(c, E)
    c.post("/api/scenario/other_tenant_deposit")
    assert lane(c, "harbour")["state"] == "AWAITING_FUNDS"  # another employer's money changes nothing
    assert c.post("/api/scenario/harbour_topup").json()["result"]["ok"]
    cycle(E)
    assert lane(c, "harbour")["state"] == "AWAITING_APPROVAL"
    for t, u in (("northwind", "priya"), ("harbour", "lee")):
        assert c.post("/api/approve", json={"tenant": t, "user": u}).json()["ok"]
    cycle(E, 6)
    assert {t: lane(c, t)["state"] for t in ("northwind", "kestrel", "harbour")} == {"northwind": "DONE", "kestrel": "DONE", "harbour": "DONE"}
    assert all(ln["pill"] == "Paid" for t in ("northwind", "kestrel", "harbour") for ln in lane(c, t)["lines"])
    p = c.get("/api/proof").json()
    bad = [(t, c) for t, r in p["report"]["tenants"].items() for c in r["checks"] if not c["ok"]]
    assert not bad, bad
    assert p["report"]["ok"] and all(v["valid"] and v["result"] == "PASS" for v in p["certs"].values())
    assert c.get("/api/cert/northwind").json()["body"]["tenant"] == "northwind"
    rows = c.get("/api/timeline").json()
    assert {r["phase"] for r in rows} == {"Observe", "Decide", "Act", "Reconcile"}
    assert any(r["simulated"] for r in rows)


def test_cert_is_404_until_the_proof_page_issued_it(c):
    assert c.get("/api/cert/kestrel").status_code == 404


def test_kill_switch_pauses_release_and_resume_continues(c, E):
    start(c, E)
    assert c.post("/api/kill", json={"on": True, "user": "maya"}).json()["ok"]
    s = c.get("/api/state").json()
    assert s["kill"] == {"on": True, "by": "Maya", "ts": s["kill"]["ts"]}
    cycle(E)
    assert lane(c, "kestrel")["state"] == "HELD"
    c.post("/api/kill", json={"on": False, "user": "maya"})
    assert c.post("/api/resume", json={"tenant": "kestrel", "user": "maya"}).json()["ok"]
    cycle(E, 6)
    assert lane(c, "kestrel")["state"] == "DONE"


def test_every_scenario_endpoint_answers_and_unknown_ones_404(c, E):
    start(c, E)
    assert c.post("/api/scenario/cross_tenant_call").json()["result"]["ok"]
    assert c.post("/api/scenario/bank_change_email").json()["result"]["ok"]
    assert c.post("/api/scenario/nope").status_code == 404
    last = c.get("/api/state").json()["scenarios"]
    assert {s["id"]: s["last"] is not None for s in last}["cross_tenant_call"]


def test_reset_clears_the_take(c, E):
    start(c, E)
    c.post("/api/scenario/cross_tenant_call")
    assert c.post("/api/reset", json={}).json()["ok"]
    s = c.get("/api/state").json()
    assert all(ln["state"] is None for ln in s["lanes"].values()) and all(x["last"] is None for x in s["scenarios"])


def test_ledger_rows_are_linkable_and_carry_no_secrets(c, E):
    start(c, E)
    rows = c.get("/api/ledger", params={"seqs": "1,2,3"}).json()
    assert [r["seq"] for r in rows] == [1, 2, 3] and all("hash" in r for r in rows)


def test_rules_endpoints_draft_without_applying_and_only_the_tenants_approver_signs(c, E):
    body = {"tenant": "northwind", "text": "No single payment over 400 GBP", "user": "priya"}
    d = c.post("/api/rules/draft", json=body).json()["draft"]
    assert d["after"]["per_line_cap"]["GBP"] == "400.00" and d["base_version"] == 1
    assert c.post("/api/rules/sign", json={**body, "user": "sam"}).status_code == 409  # Kestrel finance
    assert c.post("/api/rules/sign", json={**body, "user": "maya"}).status_code == 409  # operator
    assert c.post("/api/rules/sign", json=body).json()["version"] == 2
    assert c.post("/api/rules/draft", json={**body, "text": "pay everyone double"}).status_code == 409


def test_track_links_are_per_contractor_and_unknown_tokens_are_404(c, E):
    start(c, E)
    link = lane(c, "kestrel")["lines"][0]["track"]
    got = c.get("/api/" + link.lstrip("/")).json()
    assert got["employer"] == "Kestrel" and "balances" not in got
    assert c.get(link).status_code == 200  # the page
    assert c.get("/api/track/" + "0" * 24).status_code == 404


def test_webhook_endpoint_rejects_unsigned_posts(c, monkeypatch):
    monkeypatch.setenv("AWX_WEBHOOK_SECRET", "whsec_fake")
    assert c.post("/webhooks/airwallex", content=b"{}").status_code == 401
    monkeypatch.delenv("AWX_WEBHOOK_SECRET")
    assert c.post("/webhooks/airwallex", content=b"{}", headers={"x-timestamp": "1", "x-signature": "a"}).status_code == 401


def test_public_mode_spaces_out_operator_buttons_and_shows_the_banner_flag(E, monkeypatch):
    monkeypatch.setenv("RF_PUBLIC", "1")
    pc = TestClient(create_app(E))
    assert pc.get("/api/state").json()["public"] is True
    assert pc.post("/api/autosettle", json={"user": "maya", "on": True}).status_code == 200
    r = pc.post("/api/autosettle", json={"user": "maya", "on": True})
    assert r.status_code == 429 and "shared demo" in r.json()["detail"]
    assert pc.post("/webhooks/airwallex", content=b"{}").status_code == 401  # webhooks are never throttled


def test_public_reset_has_its_own_20_second_gap(E, monkeypatch):
    import ringfence.app as app_mod
    monkeypatch.setenv("RF_PUBLIC", "1")
    monkeypatch.setattr(app_mod, "PUBLIC_GAP_S", 0.0)
    pc = TestClient(create_app(E))
    assert pc.post("/api/reset", json={"user": "maya"}).status_code == 200
    r = pc.post("/api/reset", json={"user": "maya"})
    assert r.status_code == 429 and r.json()["detail"] == copy.BUSY_RESET
    assert pc.post("/api/autosettle", json={"user": "maya", "on": True}).status_code == 200


def test_private_mode_has_no_throttle(c):
    assert c.get("/api/state").json()["public"] is False
    assert all(c.post("/api/autosettle", json={"user": "maya", "on": True}).status_code == 200 for _ in range(3))


def test_start_returns_at_once_and_lanes_fill_in_with_agent_notes(c, E):
    import time
    gate = threading.Event()
    E.q.put((lambda: gate.wait(5), Future()))  # hold the worker so we can see that start does not wait for it
    r = c.post("/api/start", json={})
    assert r.status_code == 200 and r.json() == {"ok": True, "queued": True}
    assert lane(c, "northwind")["state"] is None
    gate.set()
    end = time.time() + 5
    while time.time() < end and any(ln["agent_note"] is None for ln in c.get("/api/state").json()["lanes"].values()):
        time.sleep(0.05)
    s = c.get("/api/state").json()
    assert s["agent_busy"] is None and s["model"] is None
    assert all(ln["agent_note"]["mode"] == "offline agent" and ln["agent_note"]["headline"] for ln in s["lanes"].values())
    assert lane(c, "kestrel")["state"] == "READY"


def test_a_failed_start_sets_the_error_and_an_alert_and_the_worker_survives(c, E, monkeypatch):
    def boom(t):
        raise RuntimeError("x")
    monkeypatch.setattr(E, "tick", boom)
    start(c, E)
    assert c.get("/api/state").json()["error"] == copy.START_FAILED
    assert any(e["kind"] == "ALERT" for e in E.L.entries())
    assert E.call(lambda: 1) == 1


def test_daily_claude_cap_forces_the_rules_engine(c, E, monkeypatch):
    class Boom:
        model = "claude-sonnet-5-5"

        def create(self, *a):
            raise AssertionError("Claude must not be called past the cap")
    E.llm = Boom()
    monkeypatch.setenv("RF_LLM_DAILY_CAP", "0")
    s = c.get("/api/state").json()
    assert s["agent_capped"] is True and s["model"] == "claude-sonnet-5-5"
    start(c, E)
    assert lane(c, "northwind")["agent_note"]["mode"] == "offline agent"


def test_inbox_shows_what_the_agent_read_and_rejects_other_names(c):
    docs = c.get("/api/inbox/harbour").json()
    assert docs[0]["source"] == "timesheet" and docs[0]["text"].startswith("contractor_id")
    assert c.get("/api/inbox/..%2Fsecrets").status_code == 404
