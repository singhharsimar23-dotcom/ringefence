"""WP1: judge-proofing the shared demo. One test per failure a stranger clicking in a hurry could cause."""
import datetime as dt
import threading
import time
from concurrent.futures import Future
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from invariants import assert_invariants
from test_play import Rig, spec

from ringfence import copy, play_routes
from ringfence import playground as P
from ringfence.agent import loop
from ringfence.app import Engine, create_app
from ringfence.awx import AwxError
from ringfence.config import clock, var_dir
from ringfence.orchestrator import Orchestrator
from ringfence.scenarios import SCENARIOS, TAMPER_RESTORE_S, Simulator
from ringfence.setup_demo import setup


@pytest.fixture(autouse=True)
def _invariants(L, fake):
    yield
    assert_invariants(L, fake)


@pytest.fixture
def E(awx, L):
    setup(awx)
    e = Engine(awx, L, "fake", "scripted", idle=3600, release_delay=0)
    e.o.ex._sleep = lambda s: None
    return e


@pytest.fixture
def c(E):
    return TestClient(create_app(E))


def settle(E):
    E.call(lambda: None)  # a barrier behind whatever is queued on the one worker


def hold_worker(E):
    gate, taken = threading.Event(), threading.Event()
    E.q.put((lambda: (taken.set(), gate.wait(10)), Future()))
    assert taken.wait(5)  # the worker is inside the job, so the queue count below is only what we add
    return gate


# -- the app ------------------------------------------------------------------------------------------------
def test_healthz_reports_alive_and_the_queue(c):
    j = c.get("/healthz").json()
    assert j["ok"] is True and j["queue"] == 0 and j["backend"] == "fake"


def test_a_big_body_is_refused_by_header_and_by_stream(c):
    big = b'{"user":"maya","pad":"' + b"x" * (70 * 1024) + b'"}'
    r = c.post("/api/start", content=big, headers={"content-type": "application/json"})
    assert r.status_code == 413 and r.json()["detail"] == copy.TOO_BIG
    r = c.post("/api/start", content=(chunk for chunk in (big[:40000], big[40000:])), headers={"content-type": "application/json"})
    assert r.status_code == 413  # no content-length: counted as it arrives
    assert c.post("/api/start", json={"user": "maya"}).status_code == 200


def test_autosettle_needs_a_known_user(c, E):
    assert c.post("/api/autosettle", json={"user": "nobody", "on": False}).status_code == 422
    assert E.autosettle is True
    assert c.post("/api/autosettle", json={"user": "maya", "on": False}).status_code == 200
    assert E.autosettle is False


def test_a_second_start_is_the_same_job_and_the_queue_is_capped(c, E):
    gate = hold_worker(E)
    try:
        assert c.post("/api/start", json={}).json() == {"ok": True, "queued": True}
        job = E.start_job
        assert c.post("/api/start", json={}).json() == {"ok": True, "queued": True}
        assert E.start_job is job and E.q.qsize() == 1  # not queued twice
        for _ in range(E.max_queue - 1):
            E.submit(lambda: None)
        with pytest.raises(HTTPException):  # the queue is full: one more is refused outright
            E.submit(lambda: None)
        r = c.post("/api/approve", json={"user": "priya", "tenant": "northwind"})
        assert r.status_code == 429 and r.json()["detail"] == copy.BUSY
    finally:
        gate.set()
    while E.q.qsize():
        time.sleep(0.05)
    settle(E)


def test_proof_polling_is_quiet_and_cached(c, E):
    c.post("/api/start", json={})
    settle(E)
    c.get("/api/proof")
    ver = E.ver
    for _ in range(5):
        assert c.get("/api/proof").status_code == 200
    assert E.ver == ver  # a quiet job does not wake every page
    assert E.proof_cache is not None


def test_proof_polling_does_not_starve_the_run_that_is_settling(c, E):
    c.post("/api/start", json={})
    settle(E)
    stop, errors = threading.Event(), []

    def poll():
        while not stop.is_set():
            r = c.get("/api/proof")
            if r.status_code != 200:
                errors.append(r.status_code)
    threads = [threading.Thread(target=poll) for _ in range(4)]
    [t.start() for t in threads]
    try:
        assert c.post("/api/approve", json={"user": "priya", "tenant": "northwind"}).status_code == 200
        end = time.time() + 20
        while time.time() < end and c.get("/api/state").json()["lanes"]["northwind"]["state"] != "DONE":
            E.call(E._autopilot)
    finally:
        stop.set()
        [t.join() for t in threads]
    assert not errors
    assert c.get("/api/state").json()["lanes"]["northwind"]["state"] == "DONE"


def test_kill_switch_turns_itself_off_after_five_minutes_on_the_public_demo(c, E, monkeypatch):
    monkeypatch.setenv("RF_PUBLIC", "1")
    c.post("/api/kill", json={"user": "maya", "on": True})
    at = c.get("/api/state").json()["kill"]["resumes_at"]
    assert at
    monkeypatch.setattr(clock, "utc_now", lambda: dt.datetime.fromisoformat(at) + dt.timedelta(seconds=1))
    E.call(E._autopilot)
    assert c.get("/api/state").json()["kill"]["on"] is False


def test_the_daily_claude_count_survives_a_restart_and_a_fallback_is_flagged(awx, L, monkeypatch):
    setup(awx)
    e = Engine(awx, L, "fake", "scripted", idle=3600, release_delay=0)
    e.llm = SimpleNamespace(model="claude-sonnet-5-5")
    monkeypatch.setattr(loop, "run_tick", lambda *a, **k: SimpleNamespace(mode="offline agent", headline="", explanation=""))
    e.tick("northwind")
    assert e.fell_back is True and e.llm_ticks == 1
    again = Engine(awx, L, "fake", "scripted", idle=3600, release_delay=0)
    assert (again.llm_day, again.llm_ticks) == (e.llm_day, 1)


def test_a_signed_rule_with_no_account_for_its_currency_holds_the_run_with_a_reason(c, E, monkeypatch):
    def nope(*a, **k):
        raise LookupError("harbour has no JPY global account")
    monkeypatch.setattr("ringfence.orchestrator.funding.request_funding", nope)
    c.post("/api/start", json={})
    settle(E)
    ln = c.get("/api/state").json()["lanes"]["harbour"]
    assert ln["state"] == "HELD"
    assert any("account" in e["payload"]["reason"] for e in E.L.entries(kind="HOLD", tenant="harbour"))


def test_start_over_checks_airwallex_first_and_wipes_nothing_when_it_cannot_answer(c, E, monkeypatch):
    c.post("/api/start", json={})
    settle(E)
    head = E.L.head()[0]

    def down(*a, **k):
        raise AwxError(503, None, "down")
    monkeypatch.setattr(E.awx.for_tenant("northwind").__class__, "balances", down)
    r = c.post("/api/reset", json={"user": "maya"})
    assert r.status_code == 502 and r.json()["detail"] == copy.RESET_UNREACHABLE
    assert E.L.head()[0] == head  # still the same take


def test_start_over_that_fails_after_the_wipe_says_so_and_still_clears_the_page_state(c, E, monkeypatch):
    c.post("/api/start", json={})
    settle(E)
    E.results["x"] = {"ok": True}
    monkeypatch.setattr(E.o, "reset", lambda by: (_ for _ in ()).throw(AwxError(500, None, "boom")))
    r = c.post("/api/reset", json={"user": "maya"})
    assert r.status_code == 502 and r.json()["detail"] == copy.RESET_PARTIAL
    assert E.results == {} and E.autosettle is True and E.start_job is None


def test_start_over_clears_a_tamper_and_puts_autosettle_back_on(c, E):
    c.post("/api/start", json={})
    settle(E)
    c.post("/api/autosettle", json={"user": "maya", "on": False})
    c.post("/api/scenario/tamper_ledger")
    assert c.get("/api/state").json()["tamper"]
    assert c.post("/api/reset", json={"user": "maya"}).status_code == 200
    s = c.get("/api/state").json()
    assert s["tamper"] is None and E.autosettle is True and E.L.verify().ok


def test_a_metal_card_already_running_is_a_plain_409(c, E, monkeypatch):
    monkeypatch.setenv("RF_METAL", "1")
    monkeypatch.setattr(E.sim, "run", lambda *a, **k: (_ for _ in ()).throw(AssertionError("must not run")))
    app = create_app(E)
    cl = TestClient(app)
    # take the guard by hand: the route's lock is closed over, so hold it by running one card that blocks
    gate, entered = threading.Event(), threading.Event()

    def slow(*a, **k):
        entered.set()
        gate.wait(10)
        return {"id": "metal_topup", "ok": True}
    monkeypatch.setattr(E.sim, "run", slow)
    first = threading.Thread(target=lambda: cl.post("/api/scenario/metal_topup"))
    first.start()
    try:
        assert entered.wait(10)
        r = cl.post("/api/scenario/metal_overpull")
        assert r.status_code == 409 and r.json()["detail"] == copy.BUSY_METAL
    finally:
        gate.set()
        first.join()


# -- the cards ----------------------------------------------------------------------------------------------
@pytest.fixture
def world(awx, L):
    setup(awx)
    o = Orchestrator(awx, L)
    o.ex._sleep = lambda s: None
    rid = lambda: o.run_id(loop.pay_date())
    sim = Simulator(o, rid, lambda t: loop.run_tick(o, t, mode="scripted"))
    return o, sim, rid


def test_every_card_works_twice_and_in_reverse_order(world, L):
    _o, sim, _rid = world
    names = list(SCENARIOS)
    for name in [*names, *names, *reversed(names), *names]:
        r = sim.run(name)
        assert isinstance(r.get("summary"), str) and r["summary"], name
        assert "Traceback" not in r["summary"]
    assert L.verify().ok


def test_a_tampered_row_survives_a_restart_and_repairs_itself(world, L):
    o, sim, rid = world
    sim._tick("northwind")
    assert sim.run("tamper_ledger")["ok"] is False or not L.verify().ok
    assert not L.verify().ok
    restarted = Simulator(o, rid, lambda t: None)  # a new process reads var/tamper.json
    st = restarted.tamper_state()
    assert st and st["restores_at"] - restarted._tamper_load()["at"] == TAMPER_RESTORE_S
    assert restarted.restore_if_due() is False
    restarted.now = lambda: restarted._tamper_load()["at"] + TAMPER_RESTORE_S + 1
    assert restarted.restore_if_due() is True
    assert L.verify().ok and restarted.tamper_state() is None


def test_tamper_refuses_when_the_chain_is_already_broken(world, L):
    o, sim, rid = world
    sim._tick("northwind")
    sim.run("tamper_ledger")
    other = Simulator(o, rid, lambda t: None)
    other._tamper_path = var_dir() / "other-tamper.json"  # a second simulator that does not know about the first
    r = other.run("tamper_ledger")
    assert r["ok"] is False and not (var_dir() / "other-tamper.json").exists()
    sim.restore()
    assert L.verify().ok


def test_a_fault_is_disarmed_when_the_release_is_held(world, L):
    o, sim, _rid = world
    sim._tick("northwind")
    o.set_kill_switch(True, "Maya")  # the release will hold and never reach the faulted call
    sim.run("network_drop", "northwind")
    assert o.awx.disarm() == 0
    sim.run("rate_move", "northwind")
    assert o.awx.disarm() == 0


def test_a_fault_on_one_employer_never_fires_on_another(world):
    o, _sim, _rid = world
    o.awx.inject("timeout_after_commit", "transfers/create", tenant="kestrel")
    assert o.awx.disarm("northwind") == 0
    assert o.awx.disarm("kestrel") == 1


def test_start_over_sells_kestrels_demo_deposit_back(world, awx):
    _o, sim, _rid = world
    c = awx.for_tenant("kestrel")
    before = c.balances()["USD"]
    assert sim.run("other_tenant_deposit")["ok"]
    assert c.balances()["USD"] == before + 50000
    assert sim.run("other_tenant_deposit")["ok"] is False  # once per take
    setup(awx)  # what Start over does
    assert c.balances()["USD"] == before


# -- the playground -----------------------------------------------------------------------------------------
def test_one_visitor_cannot_open_more_than_their_share_of_worlds_a_day(tmp_path, monkeypatch):
    monkeypatch.setenv("RF_PLAY_IP_DAILY", "2")
    monkeypatch.setenv("RF_PLAY_DAILY", "50")
    r = Rig(tmp_path)
    for i in range(2):
        r.m.create(spec(name=f"Ip{i} Co"), "fake", "5.5.5.5")
    with pytest.raises(P.PlayError) as ei:
        r.m.create(spec(name="Ip Three"), "fake", "5.5.5.5")
    assert ei.value.status == 429 and ei.value.detail == copy.PLAY_IP_DAILY
    assert r.m.create(spec(name="Someone Else"), "fake", "6.6.6.6")  # another visitor is unaffected


def test_too_many_event_streams_get_a_429_so_the_page_falls_back_to_polling(E, tmp_path, monkeypatch):
    r = Rig(tmp_path)
    w = r.m.create(spec(), "fake", "1.1.1.1")
    r.ready(w)
    cl = TestClient(create_app(E, r.m))
    monkeypatch.setattr(play_routes, "MAX_STREAMS_IP", 0)
    resp = cl.get(f"/play/{w.wid}/events")
    assert resp.status_code == 429 and resp.json()["detail"] == copy.PLAY_STREAMS
    monkeypatch.setattr(play_routes, "MAX_STREAMS_IP", 4)
    monkeypatch.setattr(play_routes, "MAX_STREAMS", 0)
    assert cl.get(f"/play/{w.wid}/events").status_code == 429

