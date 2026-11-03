"""Tier 3: webhooks, track page, MCP tool surface."""
import hashlib
import hmac
import json
import time

import pytest
from helpers import RUN, acct, new_run, sim
from invariants import assert_invariants

from ringfence import mcp_server, store, track, webhooks
from ringfence.executor import Executor
from ringfence.orchestrator import Orchestrator, Refused
from ringfence.setup_demo import setup

SECRET = "whsec_fake"


@pytest.fixture(autouse=True)
def _invariants(L, fake):
    yield
    assert_invariants(L, fake)


@pytest.fixture
def sent(awx, fake, L):
    new_run(awx, L, "kestrel")
    L.append("APPROVED", {"auto_release": True, "rule": "x"}, RUN, "kestrel")
    ex = Executor(awx, L, sleep=lambda s: None)
    ex.release(RUN, "kestrel")
    return ex, next(iter(fake.accounts[acct("kestrel")].transfers))


def event(tid, name="payout.transfer.paid", eid="evt_1"):
    return {"id": eid, "name": name, "account_id": acct("kestrel"), "data": {"id": tid}}


def post(fake, ex, L, ev, **kw):
    out = []
    fake.webhook(ev, lambda h, raw: out.append(webhooks.handle(L, ex, fake.webhook_secret, h, raw)), **kw)
    return out


def line_states(L):
    return sorted(ln["state"] for ln in store.get_lines(L, RUN, "kestrel"))


def test_a_signed_event_is_a_hint_that_triggers_a_get_and_the_state_follows_airwallex(awx, fake, L, sent):
    ex, tid = sent
    sim(awx, "kestrel", tid, "SENT")
    sim(awx, "kestrel", tid, "PAID")
    assert post(fake, ex, L, event(tid)) == [(200, "applied")]
    assert "PAID" in line_states(L)


def test_a_bad_signature_is_rejected_and_nothing_happens(awx, fake, L, sent):
    ex, tid = sent
    sim(awx, "kestrel", tid, "SENT")
    sim(awx, "kestrel", tid, "PAID")
    assert post(fake, ex, L, event(tid), bad_signature=True)[0][0] == 401
    assert "PAID" not in line_states(L) and not L.entries(kind="WEBHOOK")


def test_a_stale_timestamp_is_rejected(L, sent):
    ex, tid = sent
    raw = json.dumps(event(tid)).encode()
    ts = str(int((time.time() - 3600) * 1000))
    sig = hmac.new(SECRET.encode(), ts.encode() + raw, hashlib.sha256).hexdigest()
    assert webhooks.handle(L, ex, SECRET, {"x-timestamp": ts, "x-signature": sig}, raw) == (401, "stale timestamp")


def test_a_duplicate_event_is_processed_once(awx, fake, L, sent):
    ex, tid = sent
    sim(awx, "kestrel", tid, "SENT")
    assert post(fake, ex, L, event(tid, "payout.transfer.sent"), duplicate=True) == [(200, "applied"), (200, "duplicate")]
    assert len(L.entries(kind="WEBHOOK")) == 1


def test_an_event_for_a_transfer_we_never_sent_is_ignored_and_logged(awx, fake, L, sent):
    ex, _ = sent
    assert post(fake, ex, L, event("trf_not_ours")) == [(200, "unknown transfer")]


def test_the_track_link_shows_one_contractors_own_payment_and_nothing_else(awx, fake, L, sent):
    tok = track.token("kestrel", RUN, "noah")
    got = track.lookup(L, tok)
    assert set(got) == {"employer", "name", "amount", "currency", "pay_date", "status", "state"}
    assert got["employer"] == "Kestrel"
    assert track.token("kestrel", RUN, "zoe") != tok
    assert track.lookup(L, "0" * 24) is None and track.lookup(L, "short") is None


@pytest.fixture
def rf(awx, L, tmp_path, monkeypatch):
    monkeypatch.setattr("ringfence.orchestrator.ROOT", tmp_path)
    setup(awx)
    o = Orchestrator(awx, L)
    o.ex._sleep = lambda s: None
    return mcp_server.Ringfence(o)


def test_mcp_has_no_approve_tool_and_release_needs_an_existing_approval(rf, fake):
    assert not [n for n in dir(rf) if "approve" in n.lower()]
    rf.propose_run("northwind")
    assert rf.get_status()[0]["state"] == "AWAITING_APPROVAL"
    with pytest.raises(Refused):
        rf.request_release("northwind")
    assert not fake.all_transfers(acct("northwind"))


def test_mcp_prices_without_moving_money_and_a_mandated_run_releases(rf, fake):
    assert rf.price_run("kestrel")["totals"]
    assert not fake.all_transfers(acct("kestrel"))
    assert rf.propose_run("kestrel")["state"] == "READY"  # kestrel's mandate auto-releases a no-change run
    assert rf.request_release("kestrel")["state"] in ("RELEASED", "DONE")
    assert len(fake.all_transfers(acct("kestrel"))) == 2
    with pytest.raises(ValueError):
        rf.price_run("someone-else")


def test_any_of_several_webhook_secrets_verifies_and_others_do_not(L, sent):
    ex, tid = sent
    raw = json.dumps(event(tid, "payout.transfer.sent", "evt_multi")).encode()
    ts = str(int(time.time() * 1000))
    sig = lambda k: hmac.new(k.encode(), ts.encode() + raw, hashlib.sha256).hexdigest()
    many = "whsec_platform, whsec_kestrel ,whsec_harbour"
    assert webhooks.handle(L, ex, many, {"x-timestamp": ts, "x-signature": sig("whsec_kestrel")}, raw)[0] == 200
    assert webhooks.handle(L, ex, many, {"x-timestamp": ts, "x-signature": sig("whsec_other")}, raw) == (401, "bad signature")
    assert webhooks.handle(L, ex, " , ", {"x-timestamp": ts, "x-signature": sig("")}, raw) == (401, "missing signature")
