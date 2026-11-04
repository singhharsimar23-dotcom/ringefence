"""WP2: every card, timeline row and payout says how real it is."""
import pytest
from fastapi.testclient import TestClient

from ringfence import copy
from ringfence.app import Engine, create_app
from ringfence.scenarios import ALL_SCENARIOS
from ringfence.setup_demo import setup


@pytest.fixture
def c(awx, L):
    setup(awx)
    e = Engine(awx, L, "fake", "scripted", idle=3600, release_delay=0)
    e.o.ex._sleep = lambda s: None
    return TestClient(create_app(e)), e


def test_every_scenario_card_has_a_known_level():
    assert set(ALL_SCENARIOS) <= set(copy.CARD_REALITY)
    assert set(copy.CARD_REALITY.values()) <= set(copy.REALITY)
    assert {k: v for k, v in copy.REALITY.items() if k != "fake"} == {
        "live": "Live on Airwallex", "chain": "On Metal testnet", "awx_sim": "Airwallex simulator", "ours": "Simulated by us"}


def test_state_exports_the_map_and_each_card_and_payout_carries_its_level(c):
    cl, e = c
    cl.post("/api/start", json={})
    e.call(lambda: None)
    s = cl.get("/api/state").json()
    assert s["reality"] == copy.REALITY
    assert all(x["reality"] in copy.REALITY for x in s["scenarios"])
    lines = [ln for lane in s["lanes"].values() for ln in lane["lines"]]
    assert lines and all(ln["reality"] == "live" for ln in lines)


def test_timeline_rows_for_outside_events_carry_a_level_and_our_own_decisions_none(c):
    cl, e = c
    cl.post("/api/start", json={})
    e.call(lambda: None)
    cl.post("/api/approve", json={"user": "priya", "tenant": "northwind"})
    rows = cl.get("/api/timeline?after=0").json()
    by_kind = {r["kind"]: r.get("reality") for r in rows}
    assert by_kind["SUBMITTED"] == "live"
    assert by_kind["GATE_ALLOW"] is None and by_kind["APPROVED"] is None


@pytest.mark.parametrize("what,level", [("[SIMULATED] platform fee credit", "ours"), ("[SIMULATED] employer top-up deposit", "awx_sim"),
                                        ("[SIMULATED] beneficiary bank returns a paid payout", "awx_sim")])
def test_simulated_rows_split_between_the_airwallex_simulator_and_us(what, level):
    assert copy.row_reality("SIMULATED", {"what": what}) == level


def test_the_network_drop_card_says_what_is_real_about_it(c):
    cl, _ = c
    s = {x["id"]: x for x in cl.get("/api/state").json()["scenarios"]}
    assert "The transfer really reached Airwallex. Only the lost reply is simulated." in s["network_drop"]["line"]
