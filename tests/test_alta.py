"""Alta settlement, offline. The executor under test is the unchanged one; only the client underneath is the chain adapter."""
import itertools
from decimal import Decimal as D

import pytest
from fake_chain import ChainView, FakeChain
from helpers import RUN, acct, new_run
from invariants import assert_invariants

from ringfence import alta, alta_setup, fees, store
from ringfence import beneficiaries as ben
from ringfence.alta import AltaAwx, Chain
from ringfence.awx import AwxError
from ringfence.executor import Executor
from ringfence.mandate import make_request_id

NOAH, ZOE, MULE = "0x" + "1" * 40, "0x" + "2" * 40, "0x" + "e" * 40
PRINCIPAL = "0x" + "a" * 40
TENANTS = ("kestrel", "northwind", "harbour")


@pytest.fixture
def chain(tmp_path):
    return FakeChain(tmp_path / "creds", PRINCIPAL, funds=D(10000))


@pytest.fixture
def world(awx, fake, L, chain):
    """kestrel's two contractors are wallets; the executor sends through AltaAwx."""
    new_run(awx, L, "kestrel")  # the normal demo world first, then the wallet overlay
    alta_setup.overlay("kestrel", {"noah": NOAH, "zoe": ZOE}, PRINCIPAL)
    with L.tx() as tx:
        for cid in ("noah", "zoe"):
            ln = store.get_line(tx, RUN, "kestrel", cid)
            store.set_line(tx, RUN, "kestrel", cid, ln["state"], beneficiary_id=f"alta-kestrel-{cid}")
    L.append("APPROVED", {"auto_release": True, "rule": "test"}, RUN, "kestrel")  # the orchestrator writes this before a release
    return AltaAwx(awx, Chain(chain, chain.creds), L)


def rid(cid, attempt=1):
    return make_request_id(RUN, "kestrel", cid, attempt)


def sign_lines(chain):  # what the approver's device does: one credential per line
    chain.mint(rid("noah"), NOAH, 55)
    chain.mint(rid("zoe"), ZOE, 50)


def executor(a, L):
    return Executor(a, L, sleep=lambda s: None, on_done=lambda r, t: fees.charge(a, L, r, t))


def lines(L):
    return {ln["contractor_id"]: ln for ln in store.get_lines(L, RUN, "kestrel")}


def view(fake, chain):
    return ChainView(fake, chain, {t: acct(t) for t in TENANTS})


def test_pays_each_line_once_on_chain_and_the_fee_stays_on_airwallex(world, awx, fake, L, chain):
    sign_lines(chain)
    ex = executor(world, L)
    assert ex.release(RUN, "kestrel") in ("RELEASED", "DONE")
    ex.release(RUN, "kestrel")
    assert {p["payee"]: p["usdz"] for p in chain.paid()} == {NOAH: D(55), ZOE: D(50)}
    assert {ln["state"] for ln in lines(L).values()} == {"PAID"}
    assert [e["payload"]["amount"] for e in L.entries(kind="FEE_CHARGED")] == ["3.00"]  # the GBP fee ran on the inner client
    assert {t["transfer_currency"] for t in fake.all_transfers(acct("kestrel"))} == {"GBP"}
    assert_invariants(L, view(fake, chain))


def test_no_credential_means_no_funds_and_nothing_is_pulled(world, L, chain):
    """The balance IS the signed budget: with no credential the gate refuses before any send."""
    executor(world, L).release(RUN, "kestrel")
    assert chain.pulls == [] and chain.paid() == []
    assert {ln["state"] for ln in lines(L).values()} == {"PLANNED"}
    assert [e["payload"]["code"] for e in L.entries(kind="GATE_DENY")] == ["INSUFFICIENT_OWN_FUNDS"]


def test_a_line_without_its_own_credential_is_never_pulled_even_when_the_budget_exists(world, L, chain):
    chain.mint(rid("zoe"), ZOE, 50)
    chain.mint("rf-spare", MULE, 100)  # budget exists, but it is not noah's credential
    executor(world, L).release(RUN, "kestrel")
    assert [p["rid"] for p in chain.paid()] == [rid("zoe")] and all(p["rid"] != "rf-spare" for p in chain.pulls)
    assert lines(L)["noah"]["error"] == "alta_no_credential"


@pytest.mark.parametrize("what,code", [("payee", "alta_payee_mismatch"), ("amount", "alta_terms_mismatch"),
                                        ("occ", "alta_terms_mismatch")])
def test_a_credential_that_is_not_exactly_this_line_blocks_the_pull(world, L, chain, what, code):
    chain.mint(rid("zoe"), ZOE, 50)
    chain.mint(rid("noah"), MULE if what == "payee" else NOAH, 56 if what == "amount" else 55, occ=2 if what == "occ" else 1)
    executor(world, L).release(RUN, "kestrel")
    assert [p["rid"] for p in chain.paid()] == [rid("zoe")]
    assert all(p["rid"] == rid("zoe") for p in chain.pulls)  # no pull was even attempted for the bad one
    assert lines(L)["noah"]["error"] == code


@pytest.mark.parametrize("what", ["revoked", "unbound", "expired"])
def test_a_dead_credential_removes_the_funds_so_the_gate_stops_the_whole_batch(world, L, chain, what):
    """Revoke is the kill switch: the batch never starts, so a line cannot be the one that slips through."""
    chain.mint(rid("zoe"), ZOE, 50)
    chain.mint(rid("noah"), NOAH, 55, bound=what != "unbound", ttl=-5 if what == "expired" else 3600)
    if what == "revoked":
        chain.revoke(rid("noah"))
    executor(world, L).release(RUN, "kestrel")
    assert chain.pulls == [] and chain.paid() == []
    assert [e["payload"]["code"] for e in L.entries(kind="GATE_DENY")] == ["INSUFFICIENT_OWN_FUNDS"]


FAULTS = [None, "timeout_after_commit", "error_before_commit"]


@pytest.mark.parametrize("schedule", list(itertools.product(range(3), repeat=4)))
def test_every_fault_schedule_of_four_release_attempts_pays_each_line_once(world, fake, L, chain, schedule):
    """Exhaustive: lost reply, failed send or nothing before each of four attempts, then one clean one."""
    sign_lines(chain)
    ex = executor(world, L)
    for c in schedule:
        if FAULTS[c]:
            chain.inject(FAULTS[c])
        ex.release(RUN, "kestrel")
        ex.recover()
    ex.release(RUN, "kestrel")
    ex.recover()
    assert sorted(p["usdz"] for p in chain.paid()) == [D(50), D(55)]
    assert all(len(p["tx"]) == 1 for p in chain.paid())  # one on-chain payment per line, ever
    assert_invariants(L, view(fake, chain))


def test_pending_is_in_flight_never_resent_and_lands_on_poll(world, L, chain):
    sign_lines(chain)
    chain.inject("pending")
    ex = executor(world, L)
    ex.release(RUN, "kestrel")
    assert lines(L)["noah"]["state"] == "IN_APPROVAL"
    ex.poll_inflight()
    assert [p["rid"] for p in chain.paid()] == [rid("zoe")]  # a poll is a read, never a pull
    assert len(chain.pulls) == 2
    chain.land(rid("noah"))
    ex.poll_inflight()
    assert lines(L)["noah"]["state"] == "PAID" and len(chain.pulls) == 2


def test_pending_window_end_cancels_and_reopens_the_line(world, L, chain, monkeypatch):
    sign_lines(chain)
    chain.inject("pending", window=1)
    ex = executor(world, L)
    ex.release(RUN, "kestrel")
    monkeypatch.setattr(alta.time, "time", lambda: 4_000_000_000)  # the credential expired before the pull landed
    ex.poll_inflight()
    ln = lines(L)["noah"]
    assert ln["attempt"] == 2 and ln["state"] == "PLANNED"  # reopened: a new request_id, a new approval and credential
    assert ln["request_id"] == rid("noah", 2) and [p["rid"] for p in chain.paid()] == [rid("zoe")]


def test_held_alerts_and_is_never_paid_again(world, L, chain):
    sign_lines(chain)
    chain.inject("held")
    ex = executor(world, L)
    ex.release(RUN, "kestrel")
    assert any(e["payload"]["what"] == "alta_held" for e in L.entries(kind="ALERT"))
    assert lines(L)["noah"]["state"] == "SENT"
    ex.recover()
    ex.poll_inflight()
    assert len(chain.state[rid("noah")]["tx"]) == 1


def test_a_line_paid_from_another_machine_mid_release_is_adopted_not_failed(world, L, chain):
    """The mandate says spent at pull time. The executor adopts it only because it is exactly this line (payee, amount, USD)."""
    sign_lines(chain)
    chain.inject("race")
    executor(world, L).release(RUN, "kestrel")
    assert lines(L)["noah"]["state"] == "PAID" and len(chain.state[rid("noah")]["tx"]) == 1
    assert len(chain.state[rid("zoe")]["tx"]) == 1


def test_a_line_already_paid_elsewhere_before_release_is_not_paid_again(world, L, chain):
    sign_lines(chain)
    chain._commit(rid("noah"), D(55))
    executor(world, L).release(RUN, "kestrel")
    assert chain.pulls == [] and len(chain.state[rid("noah")]["tx"]) == 1  # a spent credential is not funds: the gate stops the batch


def test_retry_from_a_fresh_home_cannot_pay_twice(world, L, chain):
    sign_lines(chain)
    chain.inject("timeout_after_commit")
    ex = executor(world, L)
    ex.release(RUN, "kestrel")
    chain.lost_home()  # the retry runs where Alta's local 'already paid' memory is gone
    ex.recover()
    ex.release(RUN, "kestrel")
    assert [len(s["tx"]) for s in chain.state.values()] == [1, 1]


def test_non_cent_usdz_amount_is_refused_not_rounded():
    with pytest.raises(AwxError) as e:
        alta.usd_to_usdz(D("12.55"))
    assert e.value.code == "ALTA_AMOUNT_NOT_EXACT"
    assert alta.usd_to_usdz(D("12.50")) == D("1.25")


def test_other_currencies_and_unsafe_ids_are_refused(world, chain):
    body = {"request_id": rid("noah"), "transfer_amount": D(550), "transfer_currency": "EUR",
            "beneficiary": {"bank_details": {"account_number": NOAH}}}
    with pytest.raises(AwxError) as e:
        world.for_tenant("kestrel").post_money("/transfers/create", body)
    assert e.value.code == "ALTA_CURRENCY"
    with pytest.raises(AwxError) as e:
        world.chain.dir("../../etc")
    assert e.value.code == "ALTA_BAD_REQUEST_ID"


def test_balance_is_the_unspent_budget_of_live_credentials(world, chain):
    sign_lines(chain)
    assert world.for_tenant("kestrel").balances()["USD"] == D(1050)
    chain.revoke(rid("zoe"))
    assert world.for_tenant("kestrel").balances()["USD"] == D(550)


def test_a_repointed_wallet_is_refused_and_nothing_goes_to_the_mule(world, L, chain):
    """The wallet behind the beneficiary changes after approval: the pin no longer matches, so the gate refuses."""
    sign_lines(chain)
    reg = ben.load_registry()
    reg["tenants"]["kestrel"]["payees"]["alta-kestrel-noah"]["bank_details"]["account_number"] = MULE
    ben.save_registry(reg)
    executor(world, L).release(RUN, "kestrel")
    assert all(p["to"] != MULE for p in chain.pulls) and all(p["payee"] != MULE for p in chain.paid())
    assert rid("noah") not in [p["rid"] for p in chain.paid()]


def test_a_pull_never_names_the_pull_key_as_the_key_flag(tmp_path):
    """Found on the live testnet: --key on a pull is a funded key for refusal records. Passing the pull key broke every pull."""
    from decimal import Decimal as _D

    from fake_chain import FakeChain

    from ringfence.alta import Chain
    seen = []
    fc = FakeChain(tmp_path / "c", "0x" + "a" * 40, funds=_D(10))
    chain = Chain(lambda a, cwd, **k: (seen.append(a), fc(a, cwd, **k))[1], tmp_path / "c")
    chain.pull("rf-x", "0x" + "1" * 40, _D("0.1"), "rf-x")
    assert "--key" not in seen[0]
    rc, out = fc(["mandate", "pull", "--credential", "m.json", "--to", "0x" + "1" * 40, "--amount", "0.1", "--payment-id", "p",
                  "--key", "m.key.json"], tmp_path / "c" / "rf-x")
    assert rc == 1 and "32-byte" in out
