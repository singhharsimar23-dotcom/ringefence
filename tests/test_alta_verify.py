# ruff: noqa: F811, F401
"""The proof compares the ledger and the chain both ways. Each test breaks one side and expects the proof to fail."""
from helpers import RUN
from test_alta_device import MULE, NOAH, ZOE, chain, device, executor, exp, rid, world

from ringfence import alta_verify, store, verify
from ringfence.alta import Chain
from ringfence.alta_verify import report


def paid_world(world, device, chain, L):
    device.sign(exp(L), chain.creds)
    executor(world, L).release(RUN, "kestrel")
    executor(world, L).release(RUN, "kestrel")


def test_a_clean_run_passes_and_the_certificate_verifies(world, device, chain, L, tmp_path):
    paid_world(world, device, chain, L)
    rep = report(L, world.chain, RUN, "kestrel")
    assert rep["ok"], [c for x in rep["lines"] for c in x["checks"] if not c["ok"]]
    doc = alta_verify.certificate(L, rep)
    assert doc["body"]["result"] == "PASS" and verify.check_cert(doc, verify.world_pub_path())
    assert alta_verify.write(doc, tmp_path).exists()


def test_a_tampered_certificate_does_not_verify(world, device, chain, L):
    paid_world(world, device, chain, L)
    doc = alta_verify.certificate(L, report(L, world.chain, RUN, "kestrel"))
    doc["body"]["result"] = "PASS" if doc["body"]["result"] == "FAIL" else "FAIL"
    assert not verify.check_cert(doc, verify.world_pub_path())


def test_a_chain_payment_without_an_intent_fails(world, device, chain, L):
    device.sign(exp(L), chain.creds)
    chain._commit(rid("noah"), chain.state[rid("noah")]["cap"])  # the server paid outside the executor
    rep = report(L, world.chain, RUN, "kestrel")
    noah = next(x for x in rep["lines"] if x["contractor_id"] == "noah")
    bad = {c["name"] for c in noah["checks"] if not c["ok"]}
    assert not rep["ok"] and {"every_payment_has_an_intent", "ledger_state_matches_chain"} <= bad


def test_a_credential_signed_for_another_batch_fails(world, device, chain, L):
    paid_world(world, device, chain, L)
    chain.state[rid("zoe")]["desc"] = "rf:" + "0" * 64 + ":" + rid("zoe")
    rep = report(L, world.chain, RUN, "kestrel")
    assert not rep["ok"]
    assert "signed_for_this_approved_batch" in {c["name"] for x in rep["lines"] for c in x["checks"] if not c["ok"]}


def test_a_line_the_ledger_calls_paid_but_the_chain_never_paid_fails(world, device, chain, L):
    device.sign(exp(L), chain.creds)
    with L.tx() as tx:
        store.set_line(tx, RUN, "kestrel", "noah", "PAID")
    assert not report(L, world.chain, RUN, "kestrel")["ok"]


def test_a_missing_credential_fails(world, chain, L):
    rep = report(L, world.chain, RUN, "kestrel")
    assert not rep["ok"] and all(not x["ok"] for x in rep["lines"])


def test_the_auditor_passes_a_clean_run_and_fails_a_tampered_one(world, device, chain, L):
    import sys
    sys.path.insert(0, "scripts")
    from ringfence.alta_verify import audit
    done = device.sign(exp(L), chain.creds)
    book = {"noah": NOAH, "zoe": ZOE}
    assert all(r["ok"] for r in audit(exp(L), chain.creds, book, chain))
    chain.state[rid("zoe")]["desc"] = "rf:" + "0" * 64 + ":" + rid("zoe")
    bad = [r for r in audit(exp(L), chain.creds, book, chain) if not r["ok"]]
    assert [r["line"] for r in bad] == ["zoe"] and "signed description" in bad[0]["why"]
    assert len(done) == 2


def test_a_payroll_that_has_not_paid_is_incomplete_not_a_pass(world, device, chain, L):
    """Found on the live testnet: preflight refused, nothing was paid, and the certificate still said PASS."""
    device.sign(exp(L), chain.creds)
    rep = report(L, world.chain, RUN, "kestrel")
    assert rep["ok"] and not rep["settled"]
    assert alta_verify.certificate(L, rep)["body"]["result"] == "INCOMPLETE"


def test_the_audit_never_trusts_a_refusal_reason_alta_cannot_prove(world, device, chain, L, monkeypatch):
    """Alta's own `mandate verify` cannot confirm an over-budget or over-occurrences refusal from the chain alone:
    the MandateRefused event carries no spent or occurrences count, unlike MandatePayment, so the running total the
    refusal must have broken never reaches the chain. Ringfence's audit never reads a refusal's stated reason at
    all, only the mandate's own live spent/occurrences/payments from `mandate status`, so a reason Alta cannot
    prove is a reason the audit never needed."""
    paid_world(world, device, chain, L)
    rep_before = report(L, world.chain, RUN, "kestrel")

    real_status = Chain.status

    def lying_status(self, rid):
        s = real_status(self, rid)
        if s is not None:
            s["reason"] = "mandate_budget_spent"  # a claim `mandate status` never carries, and the audit must never need
        return s

    monkeypatch.setattr(Chain, "status", lying_status)
    rep_after = report(L, world.chain, RUN, "kestrel")
    assert rep_before == rep_after
