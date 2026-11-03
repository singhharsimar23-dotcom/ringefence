import json

import pytest
from invariants import assert_invariants

from ringfence import copy, metal, store
from ringfence.agent import loop
from ringfence.orchestrator import Orchestrator
from ringfence.scenarios import SCENARIOS, Simulator, scenario_cards
from ringfence.setup_demo import setup

TX, REFUSAL = "0x" + "a" * 64, "0x" + "b" * 64


@pytest.fixture(autouse=True)
def _invariants(L, fake):
    yield
    assert_invariants(L, fake)


@pytest.fixture
def world(awx, L, tmp_path):
    setup(awx)
    o = Orchestrator(awx, L)
    o.ex._sleep = lambda s: None
    rid = lambda: o.run_id(loop.pay_date())
    sim = Simulator(o, rid, lambda t: loop.run_tick(o, t, mode="scripted"))
    (tmp_path / "state.json").write_text(json.dumps({"principal": "0xPRINCIPAL", "settlement": "0xSETTLE"}))
    calls = []

    def runner(args, cwd):
        calls.append(args)
        if "pull" in args and "--record-refusal" in args:
            return 1, f"transaction {REFUSAL}\noutcome refused\nreason mandate_cap_exceeded (the amount is above the cap)\n"
        if "pull" in args:
            return 0, f"transaction {TX}\noutcome paid\nspent 3 *USDZ of 3 *USDZ\n"
        if "bind" in args:
            return 0, f"bound 0x{'c' * 64}\ntransaction 0x{'d' * 64}\n"
        return 0, "credential m.json\n"
    sim.metal = metal.Metal(runner, tmp_path)
    sim.metal.recycle_later = sim.metal.recycle  # same steps, on this thread, so the test can look at them
    return o, sim, rid, calls


def test_topup_pulls_on_metal_then_the_matcher_closes_the_request(world, L, monkeypatch):
    monkeypatch.setenv("METAL_RPC_SECRET", "s3cret-value")
    o, sim, rid, calls = world
    sim._tick("harbour")
    r = sim.run("metal_topup")
    assert r["ok"], r["summary"]
    pull = L.entries(kind="METAL_PULL")[0]["payload"]
    assert 0 < metal.Decimal(pull["usdz"]) < metal.Decimal(pull["aud"]) / 10  # testnet scale: 1 USDZ = USD 10
    assert pull["tx"] == TX and pull["explorer_url"].endswith(TX) and pull["bind_tx"] == "0x" + "d" * 64
    req = L.entries(kind="FUNDING_REQUESTED", tenant="harbour")[-1]["payload"]
    pull_args = next(a for a in calls if "pull" in a)
    assert pull_args[pull_args.index("--payment-id") + 1].startswith("RF-")  # the funding reference, so a retry is "already paid"
    assert pull_args[pull_args.index("--to") + 1] == "0xSETTLE"
    assert all("s3cret" not in " ".join(a) for a in calls)
    o.advance(rid(), "harbour")
    assert L.entries(kind="FUNDING_MATCHED", tenant="harbour")[-1]["payload"]["reference"] == req["reference"]


def test_over_pull_is_refused_and_recorded(world, L):
    sim = world[1]
    sim._tick("harbour")
    assert sim.run("metal_overpull")["ok"] is False  # nothing to over-pull yet
    assert sim.run("metal_topup")["ok"]
    r = sim.run("metal_overpull")
    assert r["ok"] and r["links"][0]["url"].endswith(REFUSAL)
    row = L.entries(kind="METAL_REFUSED")[0]["payload"]
    assert row["code"] == "mandate_cap_exceeded" and Decimal_gt(row["usdz"], L.entries(kind="METAL_PULL")[0]["payload"]["usdz"])


def Decimal_gt(a, b):
    from decimal import Decimal
    return Decimal(a) == Decimal(b) + 1


def test_metal_down_falls_back_without_touching_the_ledger_or_airwallex(world, L):
    _, sim, rid, _ = world

    def down(args, cwd):
        raise metal.MetalError("Metal CLI did not finish: TimeoutExpired")
    sim.metal = metal.Metal(down, sim.metal.dir)
    sim._tick("harbour")
    r = sim.run("metal_topup")
    assert not r["ok"] and r["summary"] == copy.METAL_FALLBACK
    assert not L.entries(kind="METAL_PULL") and store.get_run(L, rid(), "harbour")["state"] == "AWAITING_FUNDS"


def test_not_set_up_is_a_fallback_too(world, L, tmp_path):
    _, sim, _, calls = world
    sim.metal = metal.Metal(sim.metal.runner, tmp_path / "missing")
    sim._tick("harbour")
    assert sim.run("metal_topup")["summary"] == copy.METAL_FALLBACK and not calls


def test_parse_and_scrub(monkeypatch):
    monkeypatch.setenv("METAL_RPC_URL", "https://rpc-testnet.metalntwx.com/v1/abc123")
    monkeypatch.setenv("METAL_RPC_SECRET", "hunter2")
    out = metal.scrub("error: https://rpc-testnet.metalntwx.com/v1/abc123 rejected hunter2")
    assert "abc123" not in out and "hunter2" not in out
    f = metal.parse("outcome refused, not sent\nreason mandate_payee_not_listed (not allowed)\nerror: boom")
    assert f["reason"] == "mandate_payee_not_listed" and f["error"] == "boom" and f["outcome"].startswith("refused")


def test_cards_only_appear_with_rf_metal(monkeypatch):
    monkeypatch.delenv("RF_METAL", raising=False)
    monkeypatch.delenv("RF_WORLD", raising=False)
    assert scenario_cards() is SCENARIOS
    monkeypatch.setenv("RF_METAL", "1")
    assert {"metal_topup", "metal_overpull"} <= set(scenario_cards())
    monkeypatch.setenv("RF_WORLD", "w1")
    assert not {"metal_topup", "metal_overpull"} & set(scenario_cards())


def test_pulled_usdz_is_sent_back_by_the_settlement_account(world, L):
    _, sim, _, calls = world
    sim._tick("harbour")
    assert sim.run("metal_topup")["ok"]
    back = [a for a in calls if "credential" in a and "0xSETTLE" in a and a[a.index("--principal") + 1] == "0xSETTLE"]
    assert back and back[0][back[0].index("--payee") + 1] == "0xPRINCIPAL"
    pull = L.entries(kind="METAL_PULL")[0]["payload"]
    assert back[0][back[0].index("--cap") + 1] == pull["usdz"]
    assert not L.entries(kind="METAL_RETURNED")  # plumbing: no ledger row
