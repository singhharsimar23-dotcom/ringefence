from dataclasses import replace
from datetime import UTC, datetime, timedelta
from decimal import Decimal as D

import pytest

from ringfence.gate import (
    REASON_CODES,
    Allow,
    Deny,
    FeeFacts,
    LineFact,
    ReleaseFacts,
    check_fee,
    check_propose,
    check_release,
)
from ringfence.mandate import (
    Approval,
    LineSpec,
    Mandate,
    batch_hash,
    make_request_id,
    sign_approval,
    sign_mandate,
)

NOW = datetime(2026, 11, 13, 12, 0, tzinfo=UTC)
LATER = NOW + timedelta(hours=2)


def mandate(**kw):
    base = dict(tenant="northwind", currencies=("GBP", "EUR"), funding_currencies=("GBP", "EUR"),
                per_line_cap={"GBP": D(5000), "EUR": D(5000)}, per_run_cap={"GBP": D(9000), "EUR": D(9000)},
                allowed_contractor_ids=("ada", "lukas"), expires_at=NOW + timedelta(days=30),
                fx="within_band", approver_role="northwind_finance")
    return sign_mandate(Mandate(**{**base, **kw}))


def lf(cid="ada", amt="100.00", ccy="GBP", **kw):
    base = dict(contractor_id=cid, tenant="northwind", beneficiary_id=f"b-{cid}", amount=D(amt),
                currency=ccy, state="READY", resolved_beneficiary_id=f"b-{cid}", expected_amount=D(amt),
                bank_key=f"acct-{cid}")
    return LineFact(**{**base, **kw})


def specs(lines):
    return [LineSpec(ln.contractor_id, ln.beneficiary_id, ln.amount, ln.currency, "LOCAL", ln.currency, 1,
                     make_request_id("run1", "northwind", ln.contractor_id, 1)) for ln in lines]


def facts(**kw):
    lines = kw.pop("lines", (lf(), lf("lukas", "200.00", "EUR")))
    bh = batch_hash("run1", "northwind", 1, specs(lines))
    ap = sign_approval(Approval("run1", "northwind", 1, bh, "priya", "northwind_finance", NOW, LATER))
    base = dict(run_id="run1", run_tenant="northwind", token_tenant="northwind", round=1,
                kill_switch=False, holds_lock=True, now=NOW, mandate=mandate(), lines=tuple(lines),
                tenant_ga_keys=frozenset({"ga-1"}), avail={"GBP": D(10000), "EUR": D(10000)},
                approval=ap, expected_batch_hash=bh)
    return ReleaseFacts(**{**base, **kw})


def code(f):
    d = check_release(f)
    return d.code if isinstance(d, Deny) else "ALLOW"


def test_allow_path():
    assert isinstance(check_release(facts()), Allow)


def test_every_reason_code_has_a_case_or_is_listed():
    covered = {c for c, _ in CASES} | {"INVALID_INPUT"}
    assert covered == set(REASON_CODES)


CASES = [
    ("KILL_SWITCH", lambda: facts(kill_switch=True)),
    ("RUN_NOT_OPEN", lambda: facts(holds_lock=False)),
    ("RUN_NOT_OPEN", lambda: facts(lines=(lf(state="INTENT"),))),
    ("NO_MANDATE", lambda: facts(mandate=None)),
    ("MANDATE_SIG_INVALID", lambda: facts(mandate=replace(
        mandate(), mandate=replace(mandate().mandate, per_run_cap={"GBP": D(10**9)})))),
    ("MANDATE_EXPIRED", lambda: facts(mandate=mandate(expires_at=NOW))),
    ("TENANT_MISMATCH", lambda: facts(lines=(lf(tenant="kestrel"),))),
    ("TENANT_MISMATCH", lambda: facts(token_tenant="kestrel")),
    ("CURRENCY_NOT_ALLOWED", lambda: facts(lines=(lf(ccy="USD"),))),
    ("PAYEE_NOT_ALLOWED", lambda: facts(lines=(lf("mallory"),))),
    ("BENEFICIARY_NOT_IN_TENANT", lambda: facts(lines=(lf(beneficiary_id="b-other"),))),
    ("BENEFICIARY_NOT_IN_TENANT", lambda: facts(lines=(lf(resolved_beneficiary_id=None),))),
    ("BENEFICIARY_IS_OTHER_TENANT_ACCOUNT", lambda: facts(lines=(lf(bank_key="ga-1"),))),
    ("BENEFICIARY_QUARANTINED", lambda: facts(lines=(lf(quarantined=True),))),
    ("AMOUNT_MISMATCH", lambda: facts(lines=(lf(expected_amount=D("99.00")),))),
    ("AMOUNT_MISMATCH", lambda: facts(lines=(lf(expected_amount=None),))),
    ("OVER_LINE_CAP", lambda: facts(lines=(lf(amt="5000.01"),))),
    ("OVER_LINE_CAP", lambda: facts(mandate=mandate(per_line_cap={}))),
    ("OVER_RUN_CAP", lambda: facts(lines=(lf(amt="5000"), lf("lukas", "5000", "GBP")))),
    ("OVER_RUN_CAP", lambda: facts(mandate=mandate(per_run_cap={"GBP": D(9000)}))),
    ("DUPLICATE_LINE", lambda: facts(lines=(lf(), lf()))),
    ("INSUFFICIENT_OWN_FUNDS", lambda: facts(avail={"GBP": D("99.99"), "EUR": D(10000)})),
    ("INSUFFICIENT_OWN_FUNDS", lambda: facts(avail={"GBP": D(100), "EUR": D(10000)},
                                             undebited_inflight={"GBP": D(1)})),
    ("INSUFFICIENT_OWN_FUNDS", lambda: facts(fees_need={"EUR": D("12.85")},
                                             avail={"GBP": D(10000), "EUR": D(200)})),
    ("INSUFFICIENT_OWN_FUNDS", lambda: facts(fx_sell={"GBP": D(9950)})),
    ("APPROVAL_MISSING", lambda: facts(approval=None)),
    ("APPROVAL_MISSING", lambda: facts(approval=replace(facts().approval, approver_id="eve"))),
    ("APPROVAL_HASH_MISMATCH", lambda: facts(expected_batch_hash="0" * 64)),
    ("APPROVAL_EXPIRED", lambda: facts(now=LATER + timedelta(seconds=1))),
    ("APPROVER_NOT_AUTHORISED", lambda: facts(mandate=mandate(approver_role="someone_else"))),
    ("SOD_VIOLATION", lambda: facts(beneficiary_editors=frozenset({"priya"}))),
    ("FX_NOT_ALLOWED", lambda: facts(fx_used=True, fx_sell={"GBP": D(1)}, mandate=mandate(fx="never"))),
    ("FUNDING_CURRENCY_NOT_ALLOWED", lambda: facts(
        fx_used=True, fx_sell={"GBP": D(1)}, mandate=mandate(funding_currencies=("EUR",)))),
    ("FUNDING_CURRENCY_NOT_ALLOWED", lambda: facts(fx_used=True, fx_sell={})),
    ("FX_RATE_OUT_OF_BAND", lambda: facts(fx_used=True, fx_sell={"GBP": D(1)}, live_fx_rate=D("1.2"))),
    ("FX_RATE_OUT_OF_BAND", lambda: facts(fx_used=True, fx_sell={"GBP": D(1)})),
]


@pytest.mark.parametrize("want,build", CASES, ids=[f"{c}-{i}" for i, (c, _) in enumerate(CASES)])
def test_each_deny(want, build):
    assert code(build()) == want


def with_fx(approved, live, **kw):
    f = facts(fx_used=True, fx_sell={"GBP": D(1)}, live_fx_rate=D(live), **kw)
    ap = sign_approval(replace(f.approval, fx_quote_rate=D(approved)))
    return replace(f, approval=ap)


def test_fx_band_edges():
    assert code(with_fx("2.0000", "2.0100")) == "ALLOW"  # exactly 50 bps
    assert code(with_fx("2.0000", "1.9900")) == "ALLOW"
    assert code(with_fx("2.0000", "2.0101")) == "FX_RATE_OUT_OF_BAND"
    assert code(with_fx("0", "2.0")) == "FX_RATE_OUT_OF_BAND"


def test_auto_release_only_with_empty_diff():
    m = mandate(auto_release="if_no_diff")
    assert code(facts(mandate=m, approval=None, diff_empty=True, any_new_or_changed=False)) == "ALLOW"
    assert code(facts(mandate=m, approval=None, diff_empty=True, any_new_or_changed=True)) == "APPROVAL_MISSING"
    assert code(facts(mandate=m, approval=None, diff_empty=False, any_new_or_changed=False)) == "APPROVAL_MISSING"
    assert code(facts(approval=None, diff_empty=True, any_new_or_changed=False)) == "APPROVAL_MISSING"


def test_first_failure_wins():
    assert code(facts(kill_switch=True, mandate=None, approval=None)) == "KILL_SWITCH"
    assert code(facts(mandate=None, approval=None)) == "NO_MANDATE"
    assert code(facts(lines=(lf(ccy="USD", quarantined=True),), approval=None)) == "CURRENCY_NOT_ALLOWED"


def test_approval_for_batch_a_cannot_release_batch_b():
    a = facts()
    b_lines = (lf(), lf("lukas", "200.01", "EUR"))
    b = facts(lines=tuple(b_lines))  # fresh hash for B, but A's approval presented
    assert code(replace(b, approval=a.approval)) == "APPROVAL_HASH_MISMATCH"


def test_approval_from_round_1_cannot_release_round_2():
    f = facts()
    assert code(replace(f, round=2)) == "APPROVAL_HASH_MISMATCH"


def fee(**kw):
    base = dict(run_tenant="harbour", token_tenant="harbour", kill_switch=False, beneficiary_id="fee-h",
                tenant_fee_beneficiary_id="fee-h", bank_key="07371376",
                fee_ga_keys=frozenset({"07371376"}), amount=D("4.50"), expected_amount=D("4.50"))
    return FeeFacts(**{**base, **kw})


@pytest.mark.parametrize("kw,want", [
    ({}, "ALLOW"), ({"kill_switch": True}, "KILL_SWITCH"), ({"token_tenant": "kestrel"}, "TENANT_MISMATCH"),
    ({"beneficiary_id": "x"}, "BENEFICIARY_NOT_IN_TENANT"),
    ({"tenant_fee_beneficiary_id": None}, "BENEFICIARY_NOT_IN_TENANT"),
    ({"bank_key": "1"}, "BENEFICIARY_IS_OTHER_TENANT_ACCOUNT"),
    ({"amount": D("9.00")}, "AMOUNT_MISMATCH"), ({"currency": "USD"}, "AMOUNT_MISMATCH"),
])
def test_fee_path(kw, want):
    d = check_fee(fee(**kw))
    assert (d.code if isinstance(d, Deny) else "ALLOW") == want


def prop(action, args, **kw):
    base = dict(tenant="harbour", tenant_contractors=frozenset({"h1"}), parsed_hours={"h1": D("12.50")},
                current_rates={"h1": D("40.00")})
    return check_propose(action, **{**base, "args": args, **kw})


@pytest.mark.parametrize("action,args,want", [
    ("propose_timesheet", {"contractor_id": "h1", "hours": "12.50"}, "ALLOW"),
    ("propose_timesheet", {"contractor_id": "h1", "hours": "12.5"}, "ALLOW"),
    ("propose_timesheet", {"contractor_id": "other-tenant-guy", "hours": "1"}, "INVALID_INPUT"),
    ("propose_timesheet", {"contractor_id": 5, "hours": "1"}, "INVALID_INPUT"),
    ("propose_timesheet", {"contractor_id": "h1", "hours": "80.01"}, "INVALID_INPUT"),
    ("propose_timesheet", {"contractor_id": "h1", "hours": "0"}, "INVALID_INPUT"),
    ("propose_timesheet", {"contractor_id": "h1", "hours": "1.234"}, "INVALID_INPUT"),
    ("propose_timesheet", {"contractor_id": "h1", "hours": "13"}, "INVALID_INPUT"),
    ("propose_timesheet", {"contractor_id": "h1", "hours": 12.5}, "INVALID_INPUT"),
    ("propose_timesheet", {"contractor_id": "h1", "hours": "NaN"}, "INVALID_INPUT"),
    ("propose_rate_change", {"contractor_id": "h1", "new_rate": "41"}, "ALLOW"),
    ("propose_rate_change", {"contractor_id": "h1", "new_rate": "120"}, "ALLOW"),
    ("propose_rate_change", {"contractor_id": "h1", "new_rate": "0"}, "INVALID_INPUT"),
    ("propose_bank_change", {"contractor_id": "h1"}, "ALLOW"),
    ("transfer_money", {"contractor_id": "h1"}, "INVALID_INPUT"),
])
def test_propose(action, args, want):
    d = prop(action, args)
    assert (d.code if isinstance(d, Deny) else "ALLOW") == want


def test_rate_change_flags_and_missing_rate():
    assert prop("propose_rate_change", {"contractor_id": "h1", "new_rate": "120"}).flags == (
        "RATE_CHANGE_OVER_25PCT",)
    assert prop("propose_rate_change", {"contractor_id": "h1", "new_rate": "41"}).flags == ()
    assert isinstance(prop("propose_rate_change", {"contractor_id": "h1", "new_rate": "41"},
                           current_rates={}), Deny)
    assert isinstance(prop("propose_timesheet", {"contractor_id": "h1", "hours": "12.50"},
                           parsed_hours=None), Deny)


def test_request_id_shape_and_determinism():
    r = make_request_id("20261113-abc123", "harbour", "h1", 1)
    assert len(r) == 50 and r.startswith("rf-") and r == r.lower()
    assert r == make_request_id("20261113-abc123", "harbour", "h1", 1)
    assert r != make_request_id("20261113-abc123", "harbour", "h1", 2)
