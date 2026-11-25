"""The approver's device and the release preflight, against the fake chain. Each test is an attack on one of the two."""
from datetime import timedelta
from decimal import Decimal as D

import pytest
from fake_chain import FakeChain
from helpers import RUN, new_run

from ringfence import alta_release, alta_setup, fees, store
from ringfence.alta import AltaAwx, Chain
from ringfence.alta_device import Device, DeviceRefused
from ringfence.config import clock
from ringfence.executor import Executor
from ringfence.mandate import make_request_id

NOAH, ZOE, MULE = "0x" + "1" * 40, "0x" + "2" * 40, "0x" + "e" * 40
PRINCIPAL = "0x" + "a" * 40


@pytest.fixture
def chain(tmp_path):
    return FakeChain(tmp_path / "server_creds", PRINCIPAL, funds=D(10000))


def approve(L):
    """A fresh human approval of the batch as it now stands (the executor needs one again after every reopen)."""
    from ringfence.executor import current_batch_hash
    from ringfence.mandate import Approval, sign_approval
    run = store.get_run(L, RUN, "kestrel")
    now = clock.utc_now()
    a = Approval(RUN, "kestrel", run["round"], current_batch_hash(L, RUN, "kestrel", run["round"]), "approver",
                 store.latest_mandate(L, "kestrel").mandate.approver_role, now, now + timedelta(hours=2))
    with L.tx() as tx:
        store.save_approval(tx, sign_approval(a))
        tx.append("APPROVED", {"approver": "approver", "round": run["round"]}, RUN, "kestrel")


@pytest.fixture
def world(awx, fake, L, chain):
    new_run(awx, L, "kestrel", approve=True)
    alta_setup.overlay("kestrel", {"noah": NOAH, "zoe": ZOE}, PRINCIPAL)
    with L.tx() as tx:
        for cid in ("noah", "zoe"):
            ln = store.get_line(tx, RUN, "kestrel", cid)
            store.set_line(tx, RUN, "kestrel", cid, ln["state"], beneficiary_id=f"alta-kestrel-{cid}")
    approve(L)
    return AltaAwx(awx, Chain(chain, chain.creds), L)


@pytest.fixture
def device(chain, tmp_path):
    return Device(chain, tmp_path / "device" / "owner.json", tmp_path / "device" / "out", {"noah": NOAH, "zoe": ZOE}, PRINCIPAL)


def rid(cid, attempt=1):
    return make_request_id(RUN, "kestrel", cid, attempt)


def exp(L):
    return alta_release.export(L, RUN, "kestrel")


def executor(a, L):
    return Executor(a, L, sleep=lambda s: None, on_done=lambda r, t: fees.charge(a, L, r, t))


def test_device_signs_one_credential_per_line_then_the_run_releases_and_pays_once(world, device, chain, L):
    done = device.sign(exp(L), chain.creds)
    assert {d["payee"] for d in done} == {NOAH, ZOE}
    st = chain.state[rid("noah")]
    assert st["bound"] and st["occ"] == 1 and st["cap"] == st["budget"] == D(55)
    assert st["desc"] == f"rf:{exp(L)['batch_hash']}:{rid('noah')}"
    assert sorted(p.name for p in (chain.creds / rid("noah")).iterdir()) == ["m.json", "m.key.json"]  # never the owner key
    assert alta_release.problems(L, world.chain, RUN, "kestrel") == []
    orch = type("O", (), {"L": L, "advance": lambda self, r, t: executor(world, L).release(r, t)})()
    assert alta_release.release(orch, world.chain, RUN, "kestrel")["released"]
    alta_release.release(orch, world.chain, RUN, "kestrel")  # the second advance settles what the first released
    assert sorted(p["usdz"] for p in chain.paid()) == [D(50), D(55)]


def test_server_side_never_signs_binds_or_revokes(world, device, chain, L):
    device.sign(exp(L), chain.creds)
    chain.cmds.clear()
    executor(world, L).release(RUN, "kestrel")
    assert set(chain.cmds) <= {("mandate", "status"), ("mandate", "pull")}


def test_device_rejects_a_batch_that_does_not_hash_to_the_approval(device, chain, world, L):
    e = exp(L)
    e["lines"][0]["amount"] = "9999.00"  # the server inflates a line after the human approved
    with pytest.raises(DeviceRefused, match="do not hash"):
        device.sign(e, chain.creds)
    assert chain.state == {}


def test_device_rejects_a_wallet_the_server_supplies(device, chain, world, L):
    e = exp(L)
    e["lines"][0]["wallet"] = MULE
    with pytest.raises(DeviceRefused, match="different wallet"):
        device.sign(e, chain.creds)
    assert chain.state == {}


def test_device_rejects_a_contractor_not_in_its_own_book(chain, world, L, tmp_path):
    d = Device(chain, tmp_path / "o" / "owner.json", tmp_path / "o" / "out", {"noah": NOAH}, PRINCIPAL)
    with pytest.raises(DeviceRefused, match="payee book"):
        d.sign(exp(L), chain.creds)
    assert chain.state == {}  # all or nothing: noah was fine, zoe was not, so noah is not signed either


def test_device_rejects_an_expired_approval(device, chain, world, L):
    e = exp(L)
    e["approval_expires_at"] = (clock.utc_now() - timedelta(minutes=1)).isoformat()
    with pytest.raises(DeviceRefused, match="expired"):
        device.sign(e, chain.creds)


def test_device_refuses_when_the_approver_declines(device, chain, world, L):
    with pytest.raises(DeviceRefused, match="not confirmed"):
        device.sign(exp(L), chain.creds, confirm=lambda terms: False)
    assert chain.state == {}


def test_a_credential_that_outlives_the_approval_blocks_release(world, device, chain, L):
    device.sign(exp(L), chain.creds)
    chain.state[rid("noah")]["expiry"] += 86400
    assert [p["code"] for p in alta_release.problems(L, world.chain, RUN, "kestrel")] == ["outlives_approval"]


def test_a_credential_signed_for_another_batch_blocks_release(world, device, chain, L):
    device.sign(exp(L), chain.creds)
    chain.state[rid("zoe")]["desc"] = f"rf:{'0' * 64}:{rid('zoe')}"
    assert [p["code"] for p in alta_release.problems(L, world.chain, RUN, "kestrel")] == ["not_signed_for_this_batch"]


def test_a_credential_for_a_different_wallet_or_amount_blocks_release(world, device, chain, L):
    device.sign(exp(L), chain.creds)
    chain.state[rid("noah")]["payee"] = MULE
    chain.state[rid("zoe")]["cap"] = D(500)
    assert sorted(p["code"] for p in alta_release.problems(L, world.chain, RUN, "kestrel")) == ["payee_not_the_pinned_wallet", "terms_differ"]
    executor(world, L).release(RUN, "kestrel")
    assert chain.paid() == [] and chain.pulls == []


def reopen(L, cid="noah"):
    """What the executor does when attempt 1 comes back FAILED/CANCELLED: attempt 2, a new request_id, a new approval."""
    with L.tx() as tx:
        store.set_line(tx, RUN, "kestrel", cid, "PLANNED", attempt=2, request_id=rid(cid, 2))


def test_the_stale_attempt_credential_is_a_double_pay_and_preflight_blocks_it(world, device, chain, L):
    """FINDING: a reopened line leaves attempt 1's credential bound and unspent. Whoever holds its pull key can still pay it,
    so attempt 1 AND attempt 2 would both pay the same person. Preflight refuses to release while attempt 1 is payable."""
    device.sign(exp(L), chain.creds)
    reopen(L)
    approve(L)
    chain.mint(rid("noah", 2), NOAH, 55, desc=f"rf:{exp(L)['batch_hash']}:{rid('noah', 2)}")  # a device that forgets to revoke
    found = [p for p in alta_release.problems(L, world.chain, RUN, "kestrel") if p["contractor_id"] == "noah"]
    assert [p["code"] for p in found] == ["earlier_attempt_still_payable"]
    assert world.for_tenant("kestrel")._chain.pull(rid("noah"), NOAH, D(55), rid("noah"))[0] == 0  # the attack works on the chain


def test_device_revokes_the_earlier_attempt_before_it_signs_the_next(world, device, chain, L):
    device.sign(exp(L), chain.creds)
    reopen(L)
    approve(L)
    device.sign(exp(L), chain.creds)
    assert chain.state[rid("noah")]["revoked"] and chain.state[rid("noah", 2)]["bound"]
    assert alta_release.problems(L, world.chain, RUN, "kestrel") == []
    code, f, _ = world.for_tenant("kestrel")._chain.pull(rid("noah"), NOAH, D(55), rid("noah"))
    assert code == 1 and f["reason"] == "mandate_revoked"  # attempt 1 can no longer pay anyone


def test_device_never_signs_again_for_a_line_whose_earlier_attempt_paid(world, device, chain, L):
    device.sign(exp(L), chain.creds)
    chain._commit(rid("noah"), D(55))  # attempt 1 paid after all (the 'failure' was a lost reply)
    reopen(L)
    approve(L)
    with pytest.raises(DeviceRefused, match="already paid"):
        device.sign(exp(L), chain.creds)
    assert rid("noah", 2) not in chain.state


def test_revoke_all_is_a_kill_switch_the_chain_enforces(world, device, chain, L):
    device.sign(exp(L), chain.creds)
    assert sorted(device.revoke_all(RUN)) == sorted([rid("noah"), rid("zoe")])
    executor(world, L).release(RUN, "kestrel")  # even a server that ignores the preflight cannot pay
    assert chain.paid() == []
    assert world.for_tenant("kestrel")._chain.pull(rid("zoe"), ZOE, D(50), "x")[0] != 0


def test_a_pull_key_cannot_revoke_or_bind(world, device, chain, L):
    device.sign(exp(L), chain.creds)
    d = chain.creds / rid("noah")
    for cmd in (["mandate", "revoke", "--credential", "m.json", "--key", "m.key.json"],
                ["mandate", "bind", "--credential", "m.json", "--key", "m.key.json"]):
        rc, _ = chain(cmd, d)
        assert rc == 1
    assert not chain.state[rid("noah")]["revoked"]


def test_device_can_be_run_twice_without_minting_a_second_credential(world, device, chain, L):
    device.sign(exp(L), chain.creds)
    n = sum(1 for c in chain.cmds if c == ("mandate", "credential", "create"))
    device.sign(exp(L), chain.creds)
    assert sum(1 for c in chain.cmds if c == ("mandate", "credential", "create")) == n == 2


def test_a_non_cent_amount_is_refused_by_the_device(world, device, chain, L):
    e = exp(L)
    from ringfence.mandate import batch_hash
    e["lines"][0]["amount"] = "12.55"
    from ringfence.executor import line_specs  # noqa: F401
    e["batch_hash"] = batch_hash(RUN, "kestrel", 1, [alta_release_spec(x) for x in e["lines"]])
    with pytest.raises(DeviceRefused, match="whole number"):
        device.sign(e, chain.creds)


def alta_release_spec(d):
    from ringfence.alta_device import _spec
    return _spec(d)


def test_a_renewed_approval_retires_the_old_credential_of_an_unchanged_line(world, device, chain, L):
    """FINDING: re-approving a batch changes its hash, so every line's old credential describes a batch nobody approves any
    more but is still unspent and payable by the server. The device revokes it and signs the line again; preflight blocks
    release until it has."""
    device.sign(exp(L), chain.creds)
    old_hash = exp(L)["batch_hash"]
    reopen(L)  # noah goes to attempt 2; zoe is unchanged but the batch hash moves with the new approval
    approve(L)
    assert exp(L)["batch_hash"] != old_hash
    assert {p["contractor_id"] for p in alta_release.problems(L, world.chain, RUN, "kestrel")} >= {"zoe"}
    device.sign(exp(L), chain.creds)
    assert chain.state[rid("zoe")]["desc"] == f"rf:{exp(L)['batch_hash']}:{rid('zoe')}"
    assert alta_release.problems(L, world.chain, RUN, "kestrel") == []
    assert (device.out / f"{rid('zoe')}.old1").exists()


def test_every_credential_expires_before_the_approval_even_when_signing_is_slow(world, chain, L, tmp_path):
    """Found on the live testnet: each create and bind took about a minute, and a lifetime worked out once made the later
    credentials outlive the approval, so preflight refused the whole payroll."""
    import time as _t
    clk = {"drift": 0}

    def slow_now():
        clk["drift"] += 90  # every look at the clock is 90 s later than the last
        return _t.time() + clk["drift"]

    d = Device(chain, tmp_path / "s" / "owner.json", tmp_path / "s" / "out", {"noah": NOAH, "zoe": ZOE}, PRINCIPAL, now=slow_now)
    e = exp(L)
    d.sign(e, chain.creds)
    from datetime import datetime
    deadline = datetime.fromisoformat(e["approval_expires_at"]).timestamp()
    assert all(s["expiry"] <= deadline for s in chain.state.values())


def test_device_refuses_a_line_when_the_approval_runs_out_while_signing(world, chain, L, tmp_path):
    import time as _t
    from datetime import datetime
    e = exp(L)
    deadline = datetime.fromisoformat(e["approval_expires_at"]).timestamp()
    calls = {"n": 0}

    def now():
        calls["n"] += 1
        return _t.time() if calls["n"] == 1 else deadline + 1  # fine at the start, over by the time a credential is made

    d = Device(chain, tmp_path / "x" / "owner.json", tmp_path / "x" / "out", {"noah": NOAH, "zoe": ZOE}, PRINCIPAL, now=now)
    with pytest.raises(DeviceRefused, match="expired while signing"):
        d.sign(e, chain.creds)
    assert chain.state == {}
