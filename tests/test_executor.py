from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal as D

import pytest
from helpers import RUN, acct, new_run, sim

from ringfence import fees, fx, store
from ringfence.executor import Executor
from ringfence.mandate import make_request_id


def lines(L, tenant):
    return {ln["contractor_id"]: ln for ln in store.get_lines(L, RUN, tenant)}


def run_state(L, tenant):
    return store.get_run(L, RUN, tenant)["state"]


def kinds(L, kind, tenant=None):
    return L.entries(kind=kind, tenant=tenant)


def n_transfers(fake, tenant):
    return len(fake.all_transfers(acct(tenant)))


# -- the happy path and exactly-once ---------------------------------------------------------------
def test_auto_release_pays_each_line_once_and_a_second_release_is_a_noop(awx, fake, L, ex):
    new_run(awx, L, "kestrel")
    assert ex.release(RUN, "kestrel") == "RELEASED"
    assert ex.release(RUN, "kestrel") == "RELEASED"  # double click: nothing happens
    assert n_transfers(fake, "kestrel") == 2
    for ln in lines(L, "kestrel").values():
        assert ln["state"] == "SCHEDULED"
        assert ln["request_id"] == make_request_id(RUN, "kestrel", ln["contractor_id"], 1)
    assert fake.balance(acct("kestrel"), "USD") == D("10000000.00") - D("550.00") - D("500.00")
    assert len(kinds(L, "INTENT")) == 2
    assert L.verify().ok


def test_two_threads_releasing_the_same_run_send_one_set(awx, fake, L):
    new_run(awx, L, "kestrel")
    exs = [Executor(awx, L, sleep=lambda s: None) for _ in range(2)]
    with ThreadPoolExecutor(2) as p:
        list(p.map(lambda e: e.release(RUN, "kestrel"), exs))
    assert n_transfers(fake, "kestrel") == 2


def test_timeout_after_commit_still_exactly_one_transfer(awx, fake, L, ex):
    new_run(awx, L, "kestrel")
    fake.inject("timeout_after_commit", n=1)
    assert ex.release(RUN, "kestrel") == "RELEASED"
    assert n_transfers(fake, "kestrel") == 2  # the timed-out create was found by request_id, not re-sent
    assert {ln["state"] for ln in lines(L, "kestrel").values()} == {"SCHEDULED"}
    assert len(kinds(L, "UNKNOWN")) == 1 and len(kinds(L, "RECONCILED")) == 1


def test_error_before_commit_recreates_with_the_same_stored_request_id(awx, fake, L, ex):
    new_run(awx, L, "kestrel")
    fake.inject("error_before_commit", status=500, n=1)
    ex.release(RUN, "kestrel")
    assert n_transfers(fake, "kestrel") == 2
    rids = {t["request_id"] for t in fake.all_transfers(acct("kestrel"))}
    assert rids == {make_request_id(RUN, "kestrel", c, 1) for c in ("noah", "zoe")}


def test_unreachable_after_backoff_goes_to_hold_unknown(awx, fake, L, ex):
    new_run(awx, L, "kestrel", {"noah": D(10)})
    fake.inject("error_before_commit", status=500, n=2)  # the create and the one re-create both fail
    ex.release(RUN, "kestrel")
    assert lines(L, "kestrel")["noah"]["state"] == "HOLD_UNKNOWN"
    assert n_transfers(fake, "kestrel") == 0 and kinds(L, "ALERT")


def test_duplicate_request_id_is_adopted_only_if_it_matches(awx, fake, L, ex):
    new_run(awx, L, "kestrel")
    c = awx.for_tenant("kestrel")
    ln = lines(L, "kestrel")
    c.post_money("/transfers/create", ex._body(ln["noah"]))  # an earlier attempt already created it
    c.post_money("/transfers/create", {**ex._body(ln["zoe"]), "transfer_amount": D("1.00")})  # a mismatching one
    ex.release(RUN, "kestrel")
    ln = lines(L, "kestrel")
    assert ln["noah"]["state"] == "SCHEDULED" and ln["zoe"]["state"] == "HOLD"
    assert ln["zoe"]["hold_reason"] == "DUPLICATE_MISMATCH" and kinds(L, "ALERT")
    assert n_transfers(fake, "kestrel") == 2  # nothing extra was created


# -- the gate decides ----------------------------------------------------------------------------------
def test_no_approval_means_nothing_moves(awx, fake, L, ex):
    new_run(awx, L, "northwind", approve=False)
    assert ex.release(RUN, "northwind") == "AWAITING_APPROVAL"
    assert n_transfers(fake, "northwind") == 0
    assert {ln["state"] for ln in lines(L, "northwind").values()} == {"PLANNED"}
    assert [e["payload"]["code"] for e in kinds(L, "GATE_DENY")] == ["APPROVAL_MISSING"]


def test_kill_switch_holds_everything(awx, fake, L, ex):
    new_run(awx, L, "kestrel")
    L.set_kill_switch(True, "maya")
    assert ex.release(RUN, "kestrel") == "HELD"
    assert n_transfers(fake, "kestrel") == 0


def test_own_funds_only_harbour_is_short_even_though_others_are_rich(awx, fake, L, ex):
    new_run(awx, L, "harbour")
    assert ex.release(RUN, "harbour") == "AWAITING_FUNDS"  # AUD 0, fx never; Kestrel's millions do not count
    assert n_transfers(fake, "harbour") == 0
    assert kinds(L, "GATE_DENY")[0]["payload"]["code"] == "INSUFFICIENT_OWN_FUNDS"


def test_fx_converts_only_the_shortfall_from_the_tenants_own_gbp(awx, fake, L, ex):
    rate = fx.get_quote(awx.for_tenant("northwind"), "GBP", "AUD", buy_amount=D("300.00")).rate
    new_run(awx, L, "northwind", fx_rate=rate)
    assert ex.release(RUN, "northwind") == "RELEASED"
    assert n_transfers(fake, "northwind") == 3
    a = fake.accounts[acct("northwind")]
    assert list(a.conversions) == [f"fx-{RUN}-northwind-AUD-r1"]
    assert fake.balance(acct("northwind"), "AUD") == 0  # bought exactly mia's 300.00
    assert fake.balance(acct("kestrel"), "GBP") == D("10000000.00")  # nobody else's funds touched


def test_fx_rate_moved_beyond_the_band_is_denied_before_any_money_moves(awx, fake, L, ex):
    rate = fx.get_quote(awx.for_tenant("northwind"), "GBP", "AUD", buy_amount=D("300.00")).rate
    new_run(awx, L, "northwind", fx_rate=rate)
    fake.fx_shift_bps = 100  # 1% > the 50 bps band
    assert ex.release(RUN, "northwind") == "AWAITING_APPROVAL"
    assert n_transfers(fake, "northwind") == 0 and not fake.accounts[acct("northwind")].conversions
    assert kinds(L, "GATE_DENY")[0]["payload"]["code"] == "FX_RATE_OUT_OF_BAND"


def test_a_quarantined_beneficiary_is_never_paid(awx, fake, L, ex):
    new_run(awx, L, "kestrel")
    with L.tx() as tx:
        tx.execute("INSERT INTO quarantine(tenant, contractor_id, status, data)"
                   " VALUES('kestrel', 'noah', 'ACTIVE', '{}')")
    assert ex.release(RUN, "kestrel") == "HELD"
    assert n_transfers(fake, "kestrel") == 0


# -- status handling -----------------------------------------------------------------------------------
def settle(awx, ex, L, tenant):
    for ln in lines(L, tenant).values():
        sim(awx, tenant, ln["transfer_id"], "SENT")
        sim(awx, tenant, ln["transfer_id"], "PAID")
    ex.poll_inflight()


def fee_executor(awx, L):
    return Executor(awx, L, sleep=lambda s: None, on_done=lambda r, t: fees.charge(awx, L, r, t))


def test_paid_lines_finish_the_run_and_charge_one_fee_once(awx, fake, L):
    ex = fee_executor(awx, L)
    new_run(awx, L, "kestrel")
    ex.release(RUN, "kestrel")
    settle(awx, ex, L, "kestrel")
    assert run_state(L, "kestrel") == "DONE"
    ex.poll_inflight()
    ex.poll_inflight()
    assert [e["payload"]["amount"] for e in kinds(L, "FEE_CHARGED")] == ["3.00"]  # 2 PAID x 1.50, once
    assert [d["amount"] for d in fake.accounts[fake.platform].deposits.values()] == [D("3.00")]
    assert kinds(L, "SIMULATED")
    assert fees.charge(awx, L, RUN, "kestrel") == "NONE"  # nothing more is due


def test_late_return_reopens_that_line_only_with_a_new_request_id(awx, fake, L):
    ex = fee_executor(awx, L)
    new_run(awx, L, "kestrel")
    ex.release(RUN, "kestrel")
    settle(awx, ex, L, "kestrel")
    before = lines(L, "kestrel")
    fake.late_failure(acct("kestrel"), before["noah"]["transfer_id"])
    ex.poll_inflight()
    after = lines(L, "kestrel")
    assert after["noah"]["state"] == "PLANNED" and after["noah"]["attempt"] == 2 and after["noah"]["round"] == 2
    assert after["noah"]["request_id"] == make_request_id(RUN, "kestrel", "noah", 2) != before["noah"]["request_id"]
    assert after["zoe"]["state"] == "PAID" and after["zoe"]["round"] == 1
    r = store.get_run(L, RUN, "kestrel")
    assert (r["state"], r["round"]) == ("AWAITING_APPROVAL", 2)
    assert kinds(L, "FEE_CREDIT") and kinds(L, "REOPENED")
    assert fees.charge(awx, L, RUN, "kestrel") == "NONE"  # 1 PAID line now; the 3.00 already charged covers it
    assert L.verify().ok


def test_cancelled_reopens_but_overdue_never_does(awx, fake, L, ex):
    new_run(awx, L, "kestrel")
    ex.release(RUN, "kestrel")
    ln = lines(L, "kestrel")
    fake.set_status(acct("kestrel"), ln["noah"]["transfer_id"], "OVERDUE")
    fake.set_status(acct("kestrel"), ln["zoe"]["transfer_id"], "CANCELLED")
    ex.poll_inflight()
    ln = lines(L, "kestrel")
    assert ln["noah"]["state"] == "OVERDUE" and ln["noah"]["attempt"] == 1  # not terminal, never reopened
    assert ln["zoe"]["state"] == "PLANNED" and ln["zoe"]["attempt"] == 2
    fake.set_status(acct("kestrel"), ln["noah"]["transfer_id"], "PROCESSING")  # OVERDUE can still recover
    ex.poll_inflight()
    assert lines(L, "kestrel")["noah"]["state"] == "PROCESSING"


def test_status_never_moves_backwards_and_an_unknown_status_holds(awx, fake, L, ex):
    new_run(awx, L, "kestrel")
    ex.release(RUN, "kestrel")
    ln = lines(L, "kestrel")
    sim(awx, "kestrel", ln["noah"]["transfer_id"], "SENT")
    ex.poll_inflight()
    fake.set_status(acct("kestrel"), ln["noah"]["transfer_id"], "SCHEDULED")  # a stale read
    fake.set_status(acct("kestrel"), ln["zoe"]["transfer_id"], "TELEPORTED")
    ex.poll_inflight()
    ln = lines(L, "kestrel")
    assert ln["noah"]["state"] == "SENT"  # SCHEDULED after SENT is a regression and is ignored
    assert ln["zoe"]["state"] == "HOLD" and ln["zoe"]["hold_reason"] == "UNKNOWN_STATUS"
    assert ln["zoe"]["attempt"] == 1


# -- crash recovery (GET-only) -------------------------------------------------------------------------
def test_recover_finds_a_transfer_that_landed_and_does_not_resend(awx, fake, L, ex):
    new_run(awx, L, "kestrel", {"noah": D(10)})
    ln = lines(L, "kestrel")["noah"]
    awx.for_tenant("kestrel").post_money("/transfers/create", ex._body(ln))  # sent, then the process died
    with L.tx() as tx:
        store.set_line(tx, RUN, "kestrel", "noah", "INTENT")
        store.set_run(tx, RUN, "kestrel", state="RELEASING")
    ex.recover()
    assert lines(L, "kestrel")["noah"]["state"] == "SCHEDULED" and n_transfers(fake, "kestrel") == 1
    assert run_state(L, "kestrel") == "READY"  # RELEASING always goes back to READY; the lines decide


def test_recover_returns_an_unsent_line_to_ready_and_release_sends_it_once(awx, fake, L, ex):
    new_run(awx, L, "kestrel", {"noah": D(10)})
    with L.tx() as tx:
        store.set_line(tx, RUN, "kestrel", "noah", "INTENT")
        store.set_run(tx, RUN, "kestrel", state="RELEASING")
    rid = lines(L, "kestrel")["noah"]["request_id"]
    ex.recover()
    assert lines(L, "kestrel")["noah"]["state"] == "READY" and n_transfers(fake, "kestrel") == 0
    assert ex.release(RUN, "kestrel") == "RELEASED"
    assert [t["request_id"] for t in fake.all_transfers(acct("kestrel"))] == [rid]


# -- invariants under faults ---------------------------------------------------------------------------
@pytest.mark.parametrize("faults", [
    [], [("timeout_after_commit", {"n": 1})], [("timeout_after_commit", {"n": 2})],
    [("error_before_commit", {"status": 500, "n": 1})],
    [("timeout_after_commit", {"n": 1}), ("error_before_commit", {"status": 503, "n": 1})],
    [("slow", {"ms": 1, "n": 3})],
])
def test_money_invariants_hold_under_any_fault_pattern(awx, fake, L, faults):
    new_run(awx, L, "kestrel")
    for kind, kw in faults:
        fake.inject(kind, **kw)
    ex = Executor(awx, L, sleep=lambda s: None)
    for _ in range(3):  # release, retry, retry: re-running must never add money movement
        ex.release(RUN, "kestrel")
        ex.recover()
    ts = fake.all_transfers(acct("kestrel"))
    assert len(ts) == 2 and len({t["request_id"] for t in ts}) == 2  # one transfer per line, ever
    assert sum(t["transfer_amount"] for t in ts) == D("1050.00")
    assert fake.balance(acct("kestrel"), "USD") == D("10000000.00") - D("1050.00")  # debited exactly once
    assert L.verify().ok


def test_a_409_on_create_is_looked_up_by_request_id_not_failed(awx, fake, L, ex):
    new_run(awx, L, "kestrel", {"noah": D(10)})
    fake.inject("error_before_commit", status=409, n=1)  # request_pending: the create may or may not have booked
    ex.release(RUN, "kestrel")
    assert lines(L, "kestrel")["noah"]["state"] == "SCHEDULED" and n_transfers(fake, "kestrel") == 1
    assert len(kinds(L, "UNKNOWN")) == 1 and not [e for e in kinds(L, "STATUS") if e["payload"].get("state") == "FAILED_TO_SUBMIT"]


def test_a_late_return_is_caught_while_the_run_is_reopened_and_waiting_for_approval(awx, fake, L):
    ex = fee_executor(awx, L)
    new_run(awx, L, "kestrel")
    ex.release(RUN, "kestrel")
    settle(awx, ex, L, "kestrel")
    first = lines(L, "kestrel")
    fake.late_failure(acct("kestrel"), first["noah"]["transfer_id"])
    ex.poll_inflight()
    assert store.get_run(L, RUN, "kestrel")["state"] == "AWAITING_APPROVAL"  # reopened by noah's return
    fake.late_failure(acct("kestrel"), first["zoe"]["transfer_id"])  # the other payee bounces while we wait
    ex.poll_inflight()
    after = lines(L, "kestrel")
    assert after["zoe"]["state"] == "PLANNED" and after["zoe"]["attempt"] == 2


def test_a_transfer_in_approval_is_reserved_against_the_next_run(awx, fake, L, ex):
    new_run(awx, L, "kestrel", {"noah": D(10)})
    ex.release(RUN, "kestrel")
    ln = lines(L, "kestrel")["noah"]
    fake.set_status(acct("kestrel"), ln["transfer_id"], "IN_APPROVAL")  # created, not debited yet
    ex.poll_inflight()
    assert lines(L, "kestrel")["noah"]["state"] == "IN_APPROVAL"
    new_run(awx, L, "kestrel", {"zoe": D(10)}, run_id="run-2")
    run2 = store.get_run(L, "run-2", "kestrel")
    facts, _ = ex._facts(awx.for_tenant("kestrel"), run2, store.get_lines(L, "run-2", "kestrel"))
    assert facts.undebited_inflight == {ln["currency"]: D(ln["amount"])}


def test_a_transfer_found_by_request_id_that_differs_from_the_line_is_held_not_adopted(awx, fake, L, ex):
    from ringfence import beneficiaries as ben
    new_run(awx, L, "kestrel", {"noah": D(10)})
    ln = lines(L, "kestrel")["noah"]
    awx.for_tenant("kestrel").post("/transfers/create", {  # someone with the API key got there first, with another amount
        "request_id": ln["request_id"], "beneficiary_id": ln["beneficiary_id"], "transfer_amount": D("1.00"),
        "transfer_currency": ln["currency"], "source_currency": ln["currency"], "transfer_method": ln["method"], "reason": "x"})
    fake.inject("error_before_commit", status=409, n=1)
    ex.release(RUN, "kestrel")
    after = lines(L, "kestrel")["noah"]
    assert after["state"] == "HOLD" and after["hold_reason"] == "DUPLICATE_MISMATCH" and n_transfers(fake, "kestrel") == 1


def test_an_inline_duplicate_whose_bank_details_differ_from_the_pin_is_held(awx, L, ex):
    from ringfence import beneficiaries as ben
    new_run(awx, L, "kestrel", {"noah": D(10)})
    ln = lines(L, "kestrel")["noah"]
    reg = ben.load_registry()  # pin the approved bank account for this payee
    reg["tenants"]["kestrel"].setdefault("pins", {})[ln["beneficiary_id"]] = ben.dest_fp({"bank_details": {"account_number": "11112222"}})
    ben.save_registry(reg)
    # an inline-sent transfer under this request_id (beneficiary_id null) that points at another account
    t = {"beneficiary_id": None, "beneficiary": {"bank_details": {"account_number": "99999901"}},
         "transfer_amount": ln["amount"], "transfer_currency": ln["currency"]}
    ex._adopt_found(ln, t)
    after = lines(L, "kestrel")["noah"]
    assert after["state"] == "HOLD" and after["hold_reason"] == "DUPLICATE_MISMATCH"


def test_a_late_return_does_not_wash_a_hold_into_awaiting_approval(awx, fake, L):
    ex = fee_executor(awx, L)
    new_run(awx, L, "kestrel")
    ex.release(RUN, "kestrel")
    settle(awx, ex, L, "kestrel")
    with L.tx() as tx:
        store.set_run(tx, RUN, "kestrel", state="HELD", hold_reason="DRIFT")
    fake.late_failure(acct("kestrel"), lines(L, "kestrel")["noah"]["transfer_id"])
    ex.poll_inflight()
    assert store.get_run(L, RUN, "kestrel")["state"] == "HELD" and lines(L, "kestrel")["noah"]["state"] == "PLANNED"
