import json
import time

import pytest
from invariants import assert_invariants

from ringfence import copy, metal
from ringfence.agent import loop
from ringfence.orchestrator import Orchestrator
from ringfence.scenarios import SCENARIOS, Simulator, scenario_cards
from ringfence.setup_demo import setup

TX, REFUSAL = "0x" + "a" * 64, "0x" + "b" * 64
SETTLE = "0x4b4dFF14d5cb002036A8ac2201F038A3f2654b00"


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
    (tmp_path / "state.json").write_text(json.dumps({"principal": "0xPRINCIPAL", "settlement": SETTLE}))
    (tmp_path / "owner.json").write_text("{}")  # legacy mode: Harbour's owner key on this server (device-signed tests remove it)
    calls = []

    def runner(args, cwd):
        calls.append(args)
        if "pull" in args and "--record-refusal" in args:
            why = "mandate_cap_exceeded" if args[args.index("--to") + 1] == SETTLE else "mandate_payee_not_listed"
            return 1, f"transaction {REFUSAL}\noutcome refused\nreason {why} (explanation)\n"
        if "pull" in args:
            return 0, f"transaction {TX}\noutcome paid\nspent 3 *USDZ of 3 *USDZ\n"
        if "bind" in args:
            return 0, f"bound 0x{'c' * 64}\ntransaction 0x{'d' * 64}\n"
        return 0, "credential m.json\n"
    sim.metal = metal.Metal(runner, tmp_path)
    sim.metal.recycle_later = lambda pay, alert=None: sim.metal.recycle(pay)  # same steps, on this thread, so the test can look at them
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
    assert pull_args[pull_args.index("--to") + 1] == SETTLE
    assert all("s3cret" not in " ".join(a) for a in calls)
    o.advance(rid(), "harbour")
    assert L.entries(kind="FUNDING_MATCHED", tenant="harbour")[-1]["payload"]["reference"] == req["reference"]


def test_device_signed_mode_never_binds_here_and_a_retry_cannot_pull_twice(world, L, tmp_path):
    o, sim, rid, calls = world
    (tmp_path / "owner.json").unlink()  # the fix: Harbour's owner key lives on Harbour's device, not on this server
    for name, cap in (("a-small", "1"), ("b-big", "500")):
        (tmp_path / "signed" / name).mkdir(parents=True)
        (tmp_path / "signed" / name / "m.json").write_text("{}")
        (tmp_path / "signed" / name / "cap").write_text(cap)
    base = sim.metal.runner

    def runner(args, cwd):
        if "status" in args:
            return 0, (f"mandate 0x{'e' * 64}\nper-payment-cap {(cwd / 'cap').read_text()} *USDZ\n"
                       f"expiry {int(time.time()) + 3600} (later)\nbound yes\nrevoked no\npayments 0\n")
        return base(args, cwd)
    sim.metal.runner = runner
    sim._tick("harbour")
    assert sim.run("metal_topup")["ok"]
    harbour = [a for a in calls if "--principal" in a and a[a.index("--principal") + 1] == "0xPRINCIPAL"]
    assert harbour == [] and not any("owner" in x for a in calls for x in a)  # nothing signed for Harbour here (the recycle is the platform's own key)
    pay = L.entries(kind="METAL_PULL")[0]["payload"]
    rd = tmp_path / "runs" / pay["run_dir"]
    assert (rd / "cap").read_text() == "500" and not (tmp_path / "signed" / "b-big").exists()  # the one that covers it, used up
    sim.metal._mandate(rd, metal.Decimal(pay["usdz"]), pay["run_dir"], 3600)  # a crash-retry of the same top-up
    assert (tmp_path / "signed" / "a-small").exists()  # reused its own credential, did not take another
    with pytest.raises(metal.MetalError):  # nothing Harbour signed covers 2 USDZ: no pull, the caller falls back
        sim.metal._presigned(tmp_path / "runs" / "next", metal.Decimal("2"))


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


def test_metal_down_falls_back_to_a_real_simulated_topup_and_says_so(world, L):
    o, sim, rid, _ = world

    def down(args, cwd):
        raise metal.MetalError("Metal CLI did not finish: TimeoutExpired")
    sim.metal = metal.Metal(down, sim.metal.dir)
    sim._tick("harbour")
    r = sim.run("metal_topup")
    assert r["ok"] and r["fell_back"] and r["summary"].startswith(copy.METAL_FALLBACK) and "[SIMULATED]" in r["summary"]
    assert not L.entries(kind="METAL_PULL")
    o.advance(rid(), "harbour")  # the deposit is real: the funding request closes
    assert L.entries(kind="FUNDING_MATCHED", tenant="harbour")
    assert not sim.run("metal_topup")["ok"]  # and funding cannot arrive twice


def test_not_set_up_is_a_fallback_too(world, L, tmp_path):
    _, sim, _, calls = world
    sim.metal = metal.Metal(sim.metal.runner, tmp_path / "missing")
    sim._tick("harbour")
    r = sim.run("metal_topup")
    assert r["summary"].startswith(copy.METAL_FALLBACK) and not calls


def test_double_funding_is_refused_whichever_way_the_first_came(world, L):
    o, sim, rid, calls = world
    sim._tick("harbour")
    assert sim.run("harbour_topup")["ok"]
    for card in ("harbour_topup", "metal_topup"):
        r = sim.run(card)
        assert not r["ok"] and "already sent" in r["summary"]
    assert not calls and not L.entries(kind="METAL_PULL")  # the refused card never reached the chain
    o.advance(rid(), "harbour")
    r = sim.run("harbour_topup")
    assert not r["ok"] and "not waiting for funds" in r["summary"]


def test_a_failed_recycle_leaves_an_alert_row(world, L):
    _, sim, _, _ = world
    sim._tick("harbour")

    def go(pay, alert=None):
        alert("could not send the coins back")
    sim.metal.recycle_later = go
    assert sim.run("metal_topup")["ok"]
    row = L.entries(kind="ALERT")[-1]
    assert row["payload"]["kind"] == "metal_recycle_failed"
    assert "crypto wallet" in copy.timeline_row(row)["text"]


def test_an_expired_mandate_is_signed_again_before_the_refusal(world, L, monkeypatch):
    _, sim, _, calls = world
    sim._tick("harbour")
    assert sim.run("metal_topup")["ok"]
    n = sum("create" in a for a in calls)
    monkeypatch.setattr(metal.time, "time", lambda: 9e12)  # past the one-hour life
    assert sim.run("metal_overpull")["ok"]
    assert sum("create" in a for a in calls) == n + 1  # one new credential


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
    back = [a for a in calls if "credential" in a and SETTLE in a and a[a.index("--principal") + 1] == SETTLE]
    assert back and back[0][back[0].index("--payee") + 1] == "0xPRINCIPAL"
    pull = L.entries(kind="METAL_PULL")[0]["payload"]
    assert back[0][back[0].index("--cap") + 1] == pull["usdz"]
    assert not L.entries(kind="METAL_RETURNED")  # plumbing: no ledger row


def test_lookalike_wallet_is_flagged_then_refused_on_chain(world, L):
    sim = world[1]
    fake = metal.lookalike(SETTLE)
    assert metal.looks_like(fake, SETTLE) and fake[:6] == SETTLE[:6] and fake[-4:] == SETTLE[-4:]
    assert not metal.looks_like(SETTLE, SETTLE.lower()) and not metal.looks_like("0x1234" + SETTLE[6:], SETTLE)
    sim._tick("harbour")
    assert sim.run("metal_poison")["ok"] is False  # needs the mandate first
    assert sim.run("metal_topup")["ok"]
    r = sim.run("metal_poison")
    assert r["ok"] and fake[:10] in r["summary"], r["summary"]
    row = L.entries(kind="METAL_REFUSED")[-1]["payload"]
    assert row["code"] == "mandate_payee_not_listed" and row["to"] == fake and row["flag"] == "address_poisoning"
    assert "lookalike wallet" in str(copy.timeline_row(L.entries(kind="METAL_REFUSED")[-1]))
