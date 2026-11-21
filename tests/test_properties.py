"""Property tests (Hypothesis) on the pure core: the gate, mandate and approval signing, batch hashes,
request IDs, money and the destination fingerprint. They state what must hold for every input of a kind,
where test_gate.py, test_money.py and test_stateful.py pin single cases and sequences.

Deterministic: derandomize=True, no example database, a fixed example count per test."""
import os
import string
from dataclasses import replace
from datetime import UTC, timedelta
from decimal import Decimal as D
from unittest import mock

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from test_gate import LATER, NOW, facts, lf, mandate

from ringfence import beneficiaries as ben
from ringfence.gate import (
    REASON_CODES,
    Allow,
    Deny,
    FeeFacts,
    check_fee,
    check_propose,
    check_release,
)
from ringfence.mandate import (
    Approval,
    LineSpec,
    Mandate,
    SignedMandate,
    approval_sig_valid,
    batch_hash,
    make_request_id,
    mandate_sig_valid,
    sign_approval,
    sign_mandate,
)
from ringfence.money import (
    Contractor,
    MoneyError,
    canonical_json,
    dumps_money,
    loads_money,
    parse_amount,
    price_line,
    price_run,
    q,
)

P = settings(derandomize=True, database=None, deadline=None, max_examples=150,
             suppress_health_check=[HealthCheck.too_slow])
CENT = D("0.01")
AMT = st.decimals(min_value=CENT, max_value=4000, places=2)
SLACK = st.one_of(st.just(D(0)), st.just(CENT), st.decimals(min_value=0, max_value=1000, places=2))
CCY = st.sampled_from(["GBP", "EUR"])


# ---------------------------------------------------------------------------------------------
# the gate: a valid release is allowed, and every way of breaking it is refused
# ---------------------------------------------------------------------------------------------

def total(lines, ccy):
    return sum((ln.amount for ln in lines if ln.currency == ccy), D(0))


@st.composite
def valid_release(draw):
    """A release that must be allowed, with every cap and balance exactly at its limit or above it."""
    n = draw(st.integers(1, 4))
    ccys = draw(st.lists(CCY, min_size=n, max_size=n))
    amts = draw(st.lists(AMT, min_size=n, max_size=n))
    lines = tuple(lf(f"c{i}", str(a), c) for i, (a, c) in enumerate(zip(amts, ccys)))
    used = set(ccys)
    return {
        "lines": lines, "allowed": tuple(ln.contractor_id for ln in lines),
        "lcap": {c: max(ln.amount for ln in lines if ln.currency == c) + draw(SLACK) for c in used},
        "rcap": {c: total(lines, c) + draw(SLACK) for c in used},
        "avail": {c: total(lines, c) + draw(SLACK) for c in used},
        "mkw": {}, "fkw": {}, "post": []}


def build(a):
    kw = {"lines": a["lines"], "avail": a["avail"],
          "mandate": mandate(per_line_cap=a["lcap"], per_run_cap=a["rcap"], allowed_contractor_ids=a["allowed"],
                             **a["mkw"]), **a["fkw"]}
    f = facts(**kw)
    for post in a["post"]:
        f = post(f)
    return f


def clone(a):
    return {**a, "lcap": dict(a["lcap"]), "rcap": dict(a["rcap"]), "avail": dict(a["avail"]),
            "mkw": dict(a["mkw"]), "fkw": dict(a["fkw"]), "post": list(a["post"])}


def set_line(a, i, **kw):
    a["lines"] = tuple(replace(ln, **kw) if k == i else ln for k, ln in enumerate(a["lines"]))


def bad_mandate_sig(f):
    if f.mandate is None:
        return f
    m = f.mandate.mandate
    return replace(f, mandate=replace(f.mandate, mandate=replace(m, version=m.version + 1)))


def bad_approval_sig(f):
    return f if f.approval is None else replace(f, approval=replace(f.approval, approver_id="eve"))


def _ccy_total(a, i):
    ln = a["lines"][i]
    return ln.currency, total(a["lines"], ln.currency)


def _short_funds(a, i):
    c, t = _ccy_total(a, i)
    a["avail"][c] = t - CENT


def _inflight(a, i):
    c, t = _ccy_total(a, i)
    a["avail"][c] = t
    a["fkw"]["undebited_inflight"] = {c: CENT}


def _over_line(a, i):
    a["lcap"][a["lines"][i].currency] = a["lines"][i].amount - CENT


def _over_run(a, i):
    c, t = _ccy_total(a, i)
    a["rcap"][c] = t - CENT


def _no_payee(a, i):
    a["allowed"] = tuple(x for k, x in enumerate(a["allowed"]) if k != i % len(a["lines"]))


# (name, the codes it may produce, how to break a valid release). One fault each, so the code is exact
# except a duplicated line, which may trip the run cap first.
FAULTS = [
    ("kill", ("KILL_SWITCH",), lambda a, i: a["fkw"].update(kill_switch=True)),
    ("no lock", ("RUN_NOT_OPEN",), lambda a, i: a["fkw"].update(holds_lock=False)),
    ("line not ready", ("RUN_NOT_OPEN",), lambda a, i: set_line(a, i, state="INTENT")),
    ("no mandate", ("NO_MANDATE",), lambda a, i: a["fkw"].update(mandate=None)),
    ("mandate sig", ("MANDATE_SIG_INVALID",), lambda a, i: a["post"].append(bad_mandate_sig)),
    ("mandate expired", ("MANDATE_EXPIRED",), lambda a, i: a["fkw"].update(now=NOW + timedelta(days=30))),
    ("line tenant", ("TENANT_MISMATCH",), lambda a, i: set_line(a, i, tenant="kestrel")),
    ("token tenant", ("TENANT_MISMATCH",), lambda a, i: a["fkw"].update(token_tenant="kestrel")),
    ("run tenant", ("TENANT_MISMATCH",), lambda a, i: a["fkw"].update(run_tenant="kestrel")),
    ("currency", ("CURRENCY_NOT_ALLOWED",), lambda a, i: set_line(a, i, currency="USD")),
    ("payee", ("PAYEE_NOT_ALLOWED",), _no_payee),
    ("beneficiary id", ("BENEFICIARY_NOT_IN_TENANT",), lambda a, i: set_line(a, i, beneficiary_id="x")),
    ("unresolved", ("BENEFICIARY_NOT_IN_TENANT",), lambda a, i: set_line(a, i, resolved_beneficiary_id=None)),
    ("other tenant account", ("BENEFICIARY_IS_OTHER_TENANT_ACCOUNT",), lambda a, i: set_line(a, i, bank_key="ga-1")),
    ("quarantined", ("BENEFICIARY_QUARANTINED",), lambda a, i: set_line(a, i, quarantined=True)),
    ("amount", ("AMOUNT_MISMATCH",), lambda a, i: set_line(a, i, expected_amount=a["lines"][i].amount + CENT)),
    ("no expected", ("AMOUNT_MISMATCH",), lambda a, i: set_line(a, i, expected_amount=None)),
    ("line cap", ("OVER_LINE_CAP",), _over_line),
    ("no line cap", ("OVER_LINE_CAP",), lambda a, i: a["lcap"].pop(a["lines"][i].currency)),
    ("run cap", ("OVER_RUN_CAP",), _over_run),
    ("no run cap", ("OVER_RUN_CAP",), lambda a, i: a["rcap"].pop(a["lines"][i].currency)),
    ("duplicate", ("OVER_RUN_CAP", "DUPLICATE_LINE"), lambda a, i: a.update(lines=a["lines"] + (a["lines"][i],))),
    ("funds", ("INSUFFICIENT_OWN_FUNDS",), _short_funds),
    ("in flight", ("INSUFFICIENT_OWN_FUNDS",), _inflight),
    ("no approval", ("APPROVAL_MISSING",), lambda a, i: a["fkw"].update(approval=None)),
    ("approval sig", ("APPROVAL_MISSING",), lambda a, i: a["post"].append(bad_approval_sig)),
    ("hash", ("APPROVAL_HASH_MISMATCH",),
     lambda a, i: a["post"].append(lambda f: replace(f, expected_batch_hash="0" * 64))),
    ("round", ("APPROVAL_HASH_MISMATCH",), lambda a, i: a["fkw"].update(round=2)),
    ("approval expired", ("APPROVAL_EXPIRED",), lambda a, i: a["fkw"].update(now=LATER)),
    ("approver role", ("APPROVER_NOT_AUTHORISED",), lambda a, i: a["mkw"].update(approver_role="other")),
    ("separation of duties", ("SOD_VIOLATION",), lambda a, i: a["fkw"].update(beneficiary_editors=frozenset({"priya"}))),
]
FAULT = st.sampled_from(FAULTS)
INDEX = st.integers(0, 3)


def code_of(f):
    d = check_release(f)
    return d.code if isinstance(d, Deny) else "ALLOW"


@P
@given(valid_release())
def test_a_valid_release_is_allowed_at_every_limit(a):
    assert check_release(build(a)) == Allow()


@P
@given(valid_release(), FAULT, INDEX)
def test_each_single_fault_is_refused_with_its_own_code(a, fault, i):
    name, codes, apply = fault
    b = clone(a)
    apply(b, i % len(b["lines"]))
    assert code_of(build(b)) in codes, name


@P
@given(valid_release(), FAULT, INDEX, FAULT, INDEX)
def test_two_faults_are_refused_at_or_before_the_earlier_check(a, f1, i, f2, j):
    b = clone(a)
    f1[2](b, i % len(b["lines"]))
    f2[2](b, j % len(b["lines"]))
    code = code_of(build(b))
    assert code != "ALLOW"
    assert REASON_CODES.index(code) <= min(REASON_CODES.index(c) for c in f1[1] + f2[1])


@P
@given(valid_release(), FAULT, INDEX)
def test_the_gate_is_deterministic_and_only_uses_listed_codes(a, fault, i):
    b = clone(a)
    fault[2](b, i % len(b["lines"]))
    f = build(b)
    assert check_release(f) == check_release(f)
    assert code_of(f) in REASON_CODES


@P
@given(st.decimals(min_value="0.1", max_value=5, places=4), st.integers(0, 500), st.sampled_from([1, -1]),
       st.sampled_from([0, 1]))
def test_the_fx_band_is_exact(approved, bps, side, over):
    band = approved * bps / 10000
    live = approved + side * band + (side * approved * D("1e-9") if over else 0)
    f = facts(fx_used=True, fx_sell={"GBP": D(1)}, live_fx_rate=live, mandate=mandate(rate_band_bps=bps))
    f = replace(f, approval=sign_approval(replace(f.approval, fx_quote_rate=approved)))
    assert code_of(f) == ("FX_RATE_OUT_OF_BAND" if over else "ALLOW")


@P
@given(st.sampled_from(["a", "b"]), st.sampled_from(["a", "b"]), st.booleans(),
       st.one_of(st.none(), st.sampled_from(["f1", "f2"])), st.sampled_from(["f1", "f2"]),
       st.sampled_from(["k1", "k2"]), st.sampled_from(["GBP", "USD"]), AMT, AMT)
def test_check_fee_allows_exactly_the_one_fee_payment(run, token, kill, own, bid, key, ccy, amount, expected):
    f = FeeFacts(run, token, kill, bid, own, key, frozenset({"k1"}), amount, expected if amount != expected else amount,
                 ccy)
    ok = (not kill and run == token and own is not None and bid == own and key == "k1" and ccy == "GBP"
          and amount == f.expected_amount)
    assert isinstance(check_fee(f), Allow) == ok


JUNK = st.one_of(st.none(), st.booleans(), st.integers(-5, 100), st.floats(), st.text(max_size=6),
                 st.decimals(allow_nan=True, allow_infinity=True), st.lists(st.integers(), max_size=2))


@P
@given(st.sampled_from(["propose_timesheet", "propose_rate_change", "propose_bank_change", "transfer_money", 7]),
       st.dictionaries(st.sampled_from(["contractor_id", "hours", "new_rate", "x"]), JUNK, max_size=4))
def test_check_propose_never_raises_and_only_refuses_as_invalid_input(action, args):
    d = check_propose(action, "harbour", frozenset({"h1"}), args, {"h1": D("12.50")}, {"h1": D(40)})
    assert isinstance(d, Allow) or d.code == "INVALID_INPUT"
    if isinstance(d, Allow):
        assert args["contractor_id"] == "h1" and action in ("propose_timesheet", "propose_rate_change",
                                                              "propose_bank_change")


@P
@given(st.decimals(min_value=-1, max_value=100, places=3), st.decimals(min_value=0, max_value=100, places=2))
def test_a_timesheet_proposal_is_valid_only_in_range_at_two_decimals_and_as_parsed(hours, parsed):
    d = check_propose("propose_timesheet", "harbour", frozenset({"h1"}), {"contractor_id": "h1", "hours": str(hours)},
                      {"h1": parsed})
    ok = 0 < hours <= 80 and hours == hours.quantize(CENT) and parsed == hours
    assert isinstance(d, Allow) == ok


@P
@given(st.decimals(min_value=1, max_value=500, places=2), st.integers(-100, 100))
def test_a_rate_change_flags_only_beyond_25_percent(old, pct):
    new = old * (100 + pct) / 100
    d = check_propose("propose_rate_change", "harbour", frozenset({"h1"}), {"contractor_id": "h1", "new_rate": str(new)},
                      current_rates={"h1": old})
    if new <= 0:
        assert isinstance(d, Deny)
    else:
        assert d == (Allow(("RATE_CHANGE_OVER_25PCT",)) if abs(pct) > 25 else Allow())


# ---------------------------------------------------------------------------------------------
# mandate and approval signing
# ---------------------------------------------------------------------------------------------

TXT = st.text(alphabet=string.ascii_lowercase + string.digits + "_-", min_size=1, max_size=8)
CAPS = st.dictionaries(st.sampled_from(["GBP", "EUR", "USD", "AUD"]), st.decimals(min_value=0, max_value=10**7, places=2),
                       max_size=3)
WHEN = st.datetimes(min_value=NOW.replace(tzinfo=None), max_value=NOW.replace(tzinfo=None) + timedelta(days=900),
                    timezones=st.just(UTC))
MANDATES = st.builds(
    Mandate, tenant=TXT, currencies=st.lists(CCY, max_size=3).map(tuple),
    funding_currencies=st.lists(CCY, max_size=3).map(tuple), per_line_cap=CAPS, per_run_cap=CAPS,
    allowed_contractor_ids=st.lists(TXT, max_size=4).map(tuple), expires_at=WHEN,
    fx=st.sampled_from(["never", "within_band"]), rate_band_bps=st.integers(0, 1000),
    auto_release=st.sampled_from(["never", "if_no_diff"]), approver_role=TXT, version=st.integers(1, 9))
RATE = st.one_of(st.none(), st.decimals(min_value="0.0001", max_value=9, places=4))
APPROVALS = st.builds(
    Approval, run_id=TXT, tenant=TXT, round=st.integers(1, 5), batch_hash=st.text("0123456789abcdef", min_size=64, max_size=64),
    approver_id=TXT, approver_role=TXT, approved_at=WHEN, expires_at=WHEN, fx_quote_rate=RATE,
    rate_band_bps=st.integers(0, 1000))

MANDATE_EDITS = [
    lambda m: replace(m, tenant=m.tenant + "x"), lambda m: replace(m, currencies=m.currencies + ("USD",)),
    lambda m: replace(m, funding_currencies=m.funding_currencies + ("USD",)),
    lambda m: replace(m, per_line_cap={**m.per_line_cap, "ZZZ": D(1)}),
    lambda m: replace(m, per_run_cap={**m.per_run_cap, "ZZZ": D(1)}),
    lambda m: replace(m, allowed_contractor_ids=m.allowed_contractor_ids + ("x",)),
    lambda m: replace(m, expires_at=m.expires_at + timedelta(seconds=1)),
    lambda m: replace(m, fx="within_band" if m.fx == "never" else "never"),
    lambda m: replace(m, rate_band_bps=m.rate_band_bps + 1),
    lambda m: replace(m, auto_release="never" if m.auto_release == "if_no_diff" else "if_no_diff"),
    lambda m: replace(m, approver_role=m.approver_role + "x"), lambda m: replace(m, version=m.version + 1)]

APPROVAL_EDITS = [
    lambda a: replace(a, run_id=a.run_id + "x"), lambda a: replace(a, tenant=a.tenant + "x"),
    lambda a: replace(a, round=a.round + 1), lambda a: replace(a, batch_hash="f" * 64 if a.batch_hash[0] != "f" else "0" * 64),
    lambda a: replace(a, approver_id=a.approver_id + "x"), lambda a: replace(a, approver_role=a.approver_role + "x"),
    lambda a: replace(a, approved_at=a.approved_at + timedelta(seconds=1)),
    lambda a: replace(a, expires_at=a.expires_at + timedelta(seconds=1)),
    lambda a: replace(a, fx_quote_rate=D(1) if a.fx_quote_rate is None else None),
    lambda a: replace(a, fx_quote_rate=D("1.5") if a.fx_quote_rate is None else a.fx_quote_rate + D("0.0001")),
    lambda a: replace(a, rate_band_bps=a.rate_band_bps + 1)]


@P
@given(MANDATES)
def test_a_signed_mandate_verifies_and_survives_a_dict_round_trip(m):
    sm = sign_mandate(m)
    assert mandate_sig_valid(sm) and sm == sign_mandate(m)
    back = SignedMandate.from_dict(sm.to_dict())
    assert back == sm and mandate_sig_valid(back)


@P
@given(MANDATES, st.integers(0, len(MANDATE_EDITS) - 1))
def test_changing_any_mandate_field_breaks_the_signature(m, k):
    sm = sign_mandate(m)
    assert not mandate_sig_valid(replace(sm, mandate=MANDATE_EDITS[k](m)))


@P
@given(MANDATES, st.text(max_size=70))
def test_a_mandate_signature_needs_the_key_and_the_exact_bytes(m, junk):
    sm = sign_mandate(m)
    with mock.patch.dict(os.environ, {"RF_MANDATE_KEY": "another-key"}):
        assert not mandate_sig_valid(sm)
    assert not mandate_sig_valid(replace(sm, signature=junk if junk != sm.signature else ""))


@P
@given(APPROVALS)
def test_a_signed_approval_verifies_and_survives_a_dict_round_trip(a):
    s = sign_approval(a)
    assert approval_sig_valid(s) and s == a and s.signature == sign_approval(a).signature
    back = Approval.from_dict(s.to_dict())
    assert approval_sig_valid(back) and back.signature == s.signature


@P
@given(APPROVALS, st.integers(0, len(APPROVAL_EDITS) - 1))
def test_changing_any_approval_field_breaks_the_signature(a, k):
    s = sign_approval(a)
    assert not approval_sig_valid(replace(APPROVAL_EDITS[k](s), signature=s.signature))


@P
@given(APPROVALS)
def test_a_mandate_key_cannot_sign_an_approval(a):
    assert not approval_sig_valid(replace(a, signature=sign_mandate(
        Mandate("t", (), (), {}, {}, (), a.expires_at)).signature))


# ---------------------------------------------------------------------------------------------
# batch hash and request IDs
# ---------------------------------------------------------------------------------------------

SPECS = st.lists(
    st.builds(LineSpec, contractor_id=TXT, beneficiary_id=TXT, amount=AMT, currency=CCY,
              method=st.sampled_from(["LOCAL", "SWIFT"]), source_currency=CCY, attempt=st.integers(1, 3),
              request_id=TXT), min_size=1, max_size=4, unique_by=lambda s: s.contractor_id)
SPEC_EDITS = [
    lambda s: replace(s, beneficiary_id=s.beneficiary_id + "x"), lambda s: replace(s, amount=s.amount + CENT),
    lambda s: replace(s, currency="USD"), lambda s: replace(s, method=s.method + "x"),
    lambda s: replace(s, source_currency="USD"), lambda s: replace(s, attempt=s.attempt + 1),
    lambda s: replace(s, request_id=s.request_id + "x"), lambda s: replace(s, contractor_id=s.contractor_id + "x")]


@P
@given(TXT, TXT, st.integers(1, 3), SPECS, st.randoms(use_true_random=False))
def test_a_batch_hash_ignores_line_order(run, tenant, rnd, lines, r):
    shuffled = list(lines)
    r.shuffle(shuffled)
    assert batch_hash(run, tenant, rnd, lines) == batch_hash(run, tenant, rnd, shuffled)


@P
@given(TXT, TXT, st.integers(1, 3), SPECS, st.integers(0, 7), st.integers(0, 3))
def test_any_change_to_the_batch_changes_the_hash(run, tenant, rnd, lines, k, i):
    h = batch_hash(run, tenant, rnd, lines)
    i %= len(lines)
    edited = [SPEC_EDITS[k](s) if n == i else s for n, s in enumerate(lines)]
    assert batch_hash(run, tenant, rnd, edited) != h
    assert batch_hash(run + "x", tenant, rnd, lines) != h
    assert batch_hash(run, tenant + "x", rnd, lines) != h
    assert batch_hash(run, tenant, rnd + 1, lines) != h
    assert batch_hash(run, tenant, rnd, lines + [replace(lines[0], contractor_id="zz-extra")]) != h
    assert batch_hash(run, tenant, rnd, lines[1:]) != h


ID_PART = st.text(alphabet=string.ascii_letters + string.digits + "-_", min_size=1, max_size=12)
ID_ARGS = st.tuples(ID_PART, ID_PART, ID_PART, st.integers(1, 9))


@P
@given(ID_ARGS)
def test_a_request_id_has_the_shape_airwallex_accepts(args):
    r = make_request_id(*args)
    assert len(r) == 50 and r.startswith("rf-") and set(r[3:]) <= set(string.ascii_lowercase + "234567")
    assert r == make_request_id(*args)


@P
@given(st.sets(ID_ARGS, min_size=2, max_size=30))
def test_distinct_run_employer_contractor_attempt_give_distinct_request_ids(all_args):
    ids = {make_request_id(*a) for a in all_args}
    assert len(ids) == len(all_args)


@pytest.mark.xfail(strict=True, reason="known limit: the parts are joined with '|', so a part containing '|' can "
                   "collide. Run, employer and contractor IDs come from code and the registry and never contain it.")
def test_a_pipe_inside_a_part_cannot_collide():
    assert make_request_id("a|b", "c", "d", 1) != make_request_id("a", "b|c", "d", 1)


# ---------------------------------------------------------------------------------------------
# money
# ---------------------------------------------------------------------------------------------

RAW = st.decimals(min_value=0, max_value=10**7, places=6)


@P
@given(RAW)
def test_q_gives_two_places_within_half_a_cent(x):
    r = q(x, "GBP")
    assert r.as_tuple().exponent == -2 and abs(r - x) <= D("0.005")


@P
@given(RAW, RAW)
def test_q_never_reorders_amounts(x, y):
    lo, hi = sorted((x, y))
    assert q(lo, "EUR") <= q(hi, "EUR")


@P
@given(st.integers(0, 10**9))
def test_q_rounds_a_half_cent_up(n):
    assert q(D(n) / 100 + D("0.005"), "AUD") == D(n + 1) / 100


@P
@given(st.one_of(st.floats(), st.booleans(), st.none(), st.lists(st.integers(), max_size=2)))
def test_parse_amount_refuses_floats_bools_and_non_numbers(x):
    with pytest.raises(TypeError):
        parse_amount(x)


@P
@given(st.decimals(min_value=0, max_value=10**9, places=6))
def test_parse_amount_accepts_a_non_negative_decimal_as_it_is(x):
    assert parse_amount(x) == x == parse_amount(str(x))
    if x > 0:
        with pytest.raises(MoneyError):
            parse_amount(-x)
        assert parse_amount(-x, allow_negative=True) == -x


@P
@given(st.lists(st.tuples(AMT, CCY, st.sampled_from(["LOCAL", "SWIFT"])), min_size=1, max_size=6),
       st.randoms(use_true_random=False), st.decimals(min_value=0, max_value=20000, places=2))
def test_a_run_price_is_exact_order_free_and_its_shortfall_is_what_is_missing(rows, r, have):
    lines = [price_line(Contractor(f"c{i}", "t", "n", c, m, D("1.00")), a) for i, (a, c, m) in enumerate(rows)]
    own = {c: have for c in ("GBP", "EUR")}
    p = price_run(lines, own)
    shuffled = list(lines)
    r.shuffle(shuffled)
    assert price_run(shuffled, own) == p
    for c in {ln.currency for ln in lines}:
        assert p.net[c] == total(lines, c)  # the rounded lines add up with no drift
    assert p.platform_fee == D("1.50") * len(lines)
    swifts = sum(1 for ln in lines if ln.method == "SWIFT")
    assert p.swift_fees.get("EUR", D(0)) == D("12.85") * swifts
    for c in p.need:
        assert p.need[c] == (total(lines, c) + p.swift_fees.get(c, D(0)) + (p.platform_fee if c == "GBP" else 0))
    for c, n in p.need.items():
        assert p.shortfall[c] == max(D(0), n - own[c]) and (p.shortfall[c] == 0) == (own[c] >= n)


@P
@given(st.lists(st.tuples(st.decimals(min_value=0, max_value=80, places=2),
                          st.decimals(min_value=1, max_value=200, places=2)), min_size=1, max_size=20))
def test_pricing_many_lines_drifts_at_most_half_a_cent_a_line(rows):
    paid = sum((price_line(Contractor("c", "t", "n", "GBP", "LOCAL", rate), h).amount for h, rate in rows), D(0))
    exact = sum((h * rate for h, rate in rows), D(0))
    assert abs(paid - exact) <= D("0.005") * len(rows)


@P
@given(st.dictionaries(TXT, st.one_of(st.integers(), TXT, st.decimals(places=2, allow_nan=False, allow_infinity=False)),
                       max_size=5), st.randoms(use_true_random=False))
def test_canonical_json_ignores_key_order(d, r):
    items = list(d.items())
    r.shuffle(items)
    assert canonical_json(d) == canonical_json(dict(items))


MONEY_JSON = st.recursive(
    st.one_of(st.none(), st.booleans(), st.integers(-10**6, 10**6), TXT, st.decimals(places=4, allow_nan=False,
                                                                                    allow_infinity=False,
                                                                                    min_value=-10**9, max_value=10**9)),
    lambda inner: st.one_of(st.lists(inner, max_size=3), st.dictionaries(TXT, inner, max_size=3)), max_leaves=8)


@P
@given(MONEY_JSON)
def test_money_json_round_trips_decimals_exactly_with_no_floats(body):
    wire = dumps_money(body)
    back = loads_money(wire)

    def same(x, y):
        if isinstance(x, D):
            return isinstance(y, (D, int)) and x == y and not isinstance(y, float)
        if isinstance(x, dict):
            return x.keys() == y.keys() and all(same(x[k], y[k]) for k in x)
        if isinstance(x, list):
            return len(x) == len(y) and all(same(a, b) for a, b in zip(x, y))
        return x == y and type(x) is type(y)
    assert same(body, back)


# ---------------------------------------------------------------------------------------------
# destination fingerprint
# ---------------------------------------------------------------------------------------------

BANK = st.dictionaries(st.sampled_from(ben.PIN_KEYS), st.text(alphabet=string.ascii_letters + string.digits, min_size=1,
                                                            max_size=10), min_size=1)


@P
@given(BANK, st.randoms(use_true_random=False), st.dictionaries(st.sampled_from(["account_name", "bank_name"]), TXT))
def test_a_fingerprint_ignores_order_spacing_case_and_fields_that_do_not_pick_the_bank(bd, r, extra):
    items = list(bd.items())
    r.shuffle(items)
    noisy = {k: " ".join(v) for k, v in items}  # spaces inside the value
    noisy = {k: v.lower() for k, v in noisy.items()} | extra
    assert ben.fingerprint(noisy) == ben.fingerprint(bd)
    assert ben.dest_fp({"bank_details": noisy}) == ben.dest_fp({"bank_details": bd})


@P
@given(BANK, st.sampled_from(ben.PIN_KEYS))
def test_changing_any_field_that_picks_the_bank_changes_the_fingerprint(bd, k):
    assert ben.fingerprint({**bd, k: str(bd.get(k) or "") + "Z"}) != ben.fingerprint(bd)


@P
@given(BANK)
def test_a_wallet_a_bank_and_nothing_never_share_a_fingerprint(bd):
    fps = {ben.dest_fp({"bank_details": bd}), ben.dest_fp({"digital_wallet": bd}), ben.dest_fp({})}
    assert len(fps) == 3
