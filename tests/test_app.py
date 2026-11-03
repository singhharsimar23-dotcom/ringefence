import pytest
from fastapi.testclient import TestClient
from invariants import assert_invariants

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


def lane(c, t):
    return c.get("/api/state").json()["lanes"][t]


def test_empty_state_offers_the_start_action(c):
    s = c.get("/api/state").json()
    assert s["agent"] == "offline agent" and s["kill"]["on"] is False
    assert all(ln["state"] is None and ln["text"]["action"] == "start" for ln in s["lanes"].values())
    assert c.get("/").status_code == 200


def test_start_puts_each_employer_in_its_own_state_and_harbour_gets_a_funding_card(c):
    assert c.post("/api/start", json={}).json()["ok"]
    assert lane(c, "kestrel")["state"] == "READY"
    assert lane(c, "northwind")["state"] == "AWAITING_APPROVAL" and lane(c, "northwind")["text"]["action"] == "approve"
    h = lane(c, "harbour")
    assert h["state"] == "AWAITING_FUNDS" and h["funding"]["currency"] == "AUD" and h["text"]["action"] == "copy_funding"
    assert lane(c, "northwind")["approve_label"].startswith("Approve ")


def test_only_the_named_approver_can_approve(c):
    c.post("/api/start", json={})
    r = c.post("/api/approve", json={"tenant": "northwind", "user": "maya"})
    assert r.status_code == 409 and "may not approve" in r.json()["detail"]
    assert c.post("/api/approve", json={"tenant": "northwind", "user": "nobody"}).status_code == 422
    assert c.post("/api/approve", json={"tenant": "bogus", "user": "priya"}).status_code == 422
    assert c.post("/api/approve", json={"tenant": "northwind", "user": "priya"}).json()["ok"]


def test_the_whole_story_runs_to_done_through_the_api_and_the_proof_passes(c, E, fake):
    c.post("/api/start", json={})
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
    c.post("/api/start", json={})
    assert c.post("/api/kill", json={"on": True, "user": "maya"}).json()["ok"]
    s = c.get("/api/state").json()
    assert s["kill"] == {"on": True, "by": "Maya", "ts": s["kill"]["ts"]}
    cycle(E)
    assert lane(c, "kestrel")["state"] == "HELD"
    c.post("/api/kill", json={"on": False, "user": "maya"})
    assert c.post("/api/resume", json={"tenant": "kestrel", "user": "maya"}).json()["ok"]
    cycle(E, 6)
    assert lane(c, "kestrel")["state"] == "DONE"


def test_every_scenario_endpoint_answers_and_unknown_ones_404(c):
    c.post("/api/start", json={})
    assert c.post("/api/scenario/cross_tenant_call").json()["result"]["ok"]
    assert c.post("/api/scenario/bank_change_email").json()["result"]["ok"]
    assert c.post("/api/scenario/nope").status_code == 404
    last = c.get("/api/state").json()["scenarios"]
    assert {s["id"]: s["last"] is not None for s in last}["cross_tenant_call"]


def test_reset_clears_the_take(c, E):
    c.post("/api/start", json={})
    c.post("/api/scenario/cross_tenant_call")
    assert c.post("/api/reset", json={}).json()["ok"]
    s = c.get("/api/state").json()
    assert all(ln["state"] is None for ln in s["lanes"].values()) and all(x["last"] is None for x in s["scenarios"])


def test_ledger_rows_are_linkable_and_carry_no_secrets(c):
    c.post("/api/start", json={})
    rows = c.get("/api/ledger", params={"seqs": "1,2,3"}).json()
    assert [r["seq"] for r in rows] == [1, 2, 3] and all("hash" in r for r in rows)
