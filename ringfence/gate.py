"""Pure policy gate: (action, facts) -> Allow | Deny(code, detail). No I/O, no clock, no globals.

Facts are built by code, never by the model. Checks run in the BUILD_SPEC 4.3 order and the first
failure wins (check-major, line-minor).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from .mandate import Approval, SignedMandate, approval_sig_valid, mandate_sig_valid
from .money import MoneyError, parse_amount

REASON_CODES = (
    "KILL_SWITCH", "RUN_NOT_OPEN", "NO_MANDATE", "MANDATE_SIG_INVALID", "MANDATE_EXPIRED",
    "TENANT_MISMATCH", "CURRENCY_NOT_ALLOWED", "PAYEE_NOT_ALLOWED", "BENEFICIARY_NOT_IN_TENANT",
    "BENEFICIARY_IS_OTHER_TENANT_ACCOUNT", "BENEFICIARY_QUARANTINED", "AMOUNT_MISMATCH",
    "OVER_LINE_CAP", "OVER_RUN_CAP", "DUPLICATE_LINE", "INSUFFICIENT_OWN_FUNDS",
    "APPROVAL_MISSING", "APPROVAL_HASH_MISMATCH", "APPROVAL_EXPIRED", "APPROVER_NOT_AUTHORISED",
    "SOD_VIOLATION", "FX_NOT_ALLOWED", "FUNDING_CURRENCY_NOT_ALLOWED", "FX_RATE_OUT_OF_BAND",
    "INVALID_INPUT",
)


@dataclass(frozen=True)
class Allow:
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class Deny:
    code: str
    detail: str = ""


Decision = Allow | Deny


@dataclass(frozen=True)
class LineFact:
    contractor_id: str
    tenant: str
    beneficiary_id: str
    amount: Decimal
    currency: str
    state: str  # line state; must be READY
    resolved_beneficiary_id: str | None  # from THIS tenant's registry for the contractor
    expected_amount: Decimal | None  # code recompute from registry rate x code-parsed hours
    bank_key: str = ""  # account number / IBAN of the beneficiary
    quarantined: bool = False


@dataclass(frozen=True)
class ReleaseFacts:
    run_id: str
    run_tenant: str
    token_tenant: str
    round: int
    kill_switch: bool
    holds_lock: bool  # caller holds the RELEASING lock for this run
    now: datetime  # real UTC
    mandate: SignedMandate | None
    lines: tuple[LineFact, ...]
    tenant_ga_keys: frozenset[str]  # account numbers / IBANs of every tenant's own GAs
    avail: dict[str, Decimal]  # this tenant's own balances only
    fees_need: dict[str, Decimal] = field(default_factory=dict)  # e.g. SWIFT fee in EUR
    fx_buy: dict[str, Decimal] = field(default_factory=dict)
    fx_sell: dict[str, Decimal] = field(default_factory=dict)
    undebited_inflight: dict[str, Decimal] = field(default_factory=dict)
    approval: Approval | None = None
    expected_batch_hash: str = ""
    beneficiary_editors: frozenset[str] = frozenset()
    diff_empty: bool = False
    any_new_or_changed: bool = True
    fx_used: bool = False
    live_fx_rate: Decimal | None = None


def _sum_by_ccy(lines) -> dict[str, Decimal]:
    out: dict[str, Decimal] = {}
    for ln in lines:
        out[ln.currency] = out.get(ln.currency, Decimal(0)) + ln.amount
    return out


def check_release(f: ReleaseFacts) -> Decision:
    if f.kill_switch:
        return Deny("KILL_SWITCH", "all payouts paused")
    if not f.holds_lock or any(ln.state != "READY" for ln in f.lines):
        return Deny("RUN_NOT_OPEN", "run not held in RELEASING or a line is not READY")

    sm = f.mandate
    if sm is None:
        return Deny("NO_MANDATE")
    if not mandate_sig_valid(sm):
        return Deny("MANDATE_SIG_INVALID")
    m = sm.mandate
    if m.expires_at <= f.now:
        return Deny("MANDATE_EXPIRED", m.expires_at.isoformat())

    for ln in f.lines:
        if not (ln.tenant == f.run_tenant == f.token_tenant == m.tenant):
            return Deny("TENANT_MISMATCH", ln.contractor_id)
    for ln in f.lines:
        if ln.currency not in m.currencies:
            return Deny("CURRENCY_NOT_ALLOWED", f"{ln.contractor_id} {ln.currency}")
    for ln in f.lines:
        if ln.contractor_id not in m.allowed_contractor_ids:
            return Deny("PAYEE_NOT_ALLOWED", ln.contractor_id)
        if ln.resolved_beneficiary_id is None or ln.beneficiary_id != ln.resolved_beneficiary_id:
            return Deny("BENEFICIARY_NOT_IN_TENANT", ln.contractor_id)
    for ln in f.lines:
        if ln.bank_key and ln.bank_key in f.tenant_ga_keys:
            return Deny("BENEFICIARY_IS_OTHER_TENANT_ACCOUNT", ln.contractor_id)
    for ln in f.lines:
        if ln.quarantined:
            return Deny("BENEFICIARY_QUARANTINED", ln.contractor_id)
    for ln in f.lines:
        if ln.expected_amount is None or ln.amount != ln.expected_amount:
            return Deny("AMOUNT_MISMATCH", ln.contractor_id)

    totals = _sum_by_ccy(f.lines)
    for ln in f.lines:
        cap = m.per_line_cap.get(ln.currency)  # a missing cap fails closed
        if cap is None or ln.amount > cap:
            return Deny("OVER_LINE_CAP", f"{ln.contractor_id} {ln.currency}")
    for c, tot in totals.items():
        cap = m.per_run_cap.get(c)
        if cap is None or tot > cap:
            return Deny("OVER_RUN_CAP", c)

    ids = [ln.contractor_id for ln in f.lines]
    if len(ids) != len(set(ids)):
        return Deny("DUPLICATE_LINE")

    need = dict(totals)
    for c, v in f.fees_need.items():
        need[c] = need.get(c, Decimal(0)) + v
    zero = Decimal(0)
    for c, n in need.items():
        have = f.avail.get(c, zero) + f.fx_buy.get(c, zero) - f.undebited_inflight.get(c, zero)
        if have < n:
            return Deny("INSUFFICIENT_OWN_FUNDS", c)
    for s, sold in f.fx_sell.items():
        if f.avail.get(s, zero) - sold - need.get(s, zero) < 0:
            return Deny("INSUFFICIENT_OWN_FUNDS", s)

    d = _check_approval(f, m)
    if d is not None:
        return d

    if f.fx_used:
        if m.fx == "never":
            return Deny("FX_NOT_ALLOWED")
        if not f.fx_sell or any(s not in m.funding_currencies for s in f.fx_sell):
            return Deny("FUNDING_CURRENCY_NOT_ALLOWED", ",".join(f.fx_sell))
        a = f.approval
        approved = a.fx_quote_rate if a else None
        if approved is None or f.live_fx_rate is None or approved <= 0:
            return Deny("FX_RATE_OUT_OF_BAND", "no approved rate to compare against")
        if abs(f.live_fx_rate - approved) / approved * 10000 > m.rate_band_bps:
            return Deny("FX_RATE_OUT_OF_BAND", f"{f.live_fx_rate} vs approved {approved}")
    return Allow()


def _check_approval(f: ReleaseFacts, m) -> Deny | None:
    a = f.approval
    if a is None:
        if m.auto_release == "if_no_diff" and f.diff_empty and not f.any_new_or_changed:
            return None
        return Deny("APPROVAL_MISSING")
    if not approval_sig_valid(a):
        return Deny("APPROVAL_MISSING", "signature invalid")
    if (a.run_id, a.tenant, a.round, a.batch_hash) != (f.run_id, f.run_tenant, f.round,
                                                      f.expected_batch_hash):
        return Deny("APPROVAL_HASH_MISMATCH")
    if a.expires_at <= f.now:
        return Deny("APPROVAL_EXPIRED", a.expires_at.isoformat())
    if a.approver_role != m.approver_role:
        return Deny("APPROVER_NOT_AUTHORISED", a.approver_role)
    if a.approver_id in f.beneficiary_editors:
        return Deny("SOD_VIOLATION", a.approver_id)
    return None


@dataclass(frozen=True)
class FeeFacts:
    """The platform fee is a contractual charge paid from the tenant's own GBP wallet, even when the
    mandate excludes GBP for payroll (Harbour). It is the only place the platform GA is allowed."""
    run_tenant: str
    token_tenant: str
    kill_switch: bool
    beneficiary_id: str
    tenant_fee_beneficiary_id: str | None  # this tenant's own fee beneficiary
    bank_key: str
    fee_ga_keys: frozenset[str]
    amount: Decimal
    expected_amount: Decimal
    currency: str = "GBP"


def check_fee(f: FeeFacts) -> Decision:
    if f.kill_switch:
        return Deny("KILL_SWITCH")
    if f.run_tenant != f.token_tenant:
        return Deny("TENANT_MISMATCH")
    if f.tenant_fee_beneficiary_id is None or f.beneficiary_id != f.tenant_fee_beneficiary_id:
        return Deny("BENEFICIARY_NOT_IN_TENANT")
    if f.bank_key not in f.fee_ga_keys:
        return Deny("BENEFICIARY_IS_OTHER_TENANT_ACCOUNT", "fee beneficiary is not the platform GA")
    if f.currency != "GBP" or f.amount != f.expected_amount:
        return Deny("AMOUNT_MISMATCH")
    return Allow()


def check_propose(action: str, tenant: str, tenant_contractors: frozenset[str], args: dict,
                  parsed_hours: dict[str, Decimal] | None = None,
                  current_rates: dict[str, Decimal] | None = None) -> Decision:
    """Validates one agent proposal. `tenant_contractors` is this tenant's registry; `parsed_hours` is
    what code parsed from the timesheet. Anything off -> INVALID_INPUT, nothing executes."""
    cid = args.get("contractor_id")
    if not isinstance(cid, str) or cid not in tenant_contractors:
        return Deny("INVALID_INPUT", "unknown contractor for this tenant")
    try:
        if action == "propose_timesheet":
            h = parse_amount(args.get("hours"))
            if not (0 < h <= 80) or h != h.quantize(Decimal("0.01")):
                return Deny("INVALID_INPUT", "hours must be 0 < h <= 80 with at most 2 dp")
            if parsed_hours is None or parsed_hours.get(cid) != h:
                return Deny("INVALID_INPUT", "hours differ from the timesheet parsed by code")
        elif action == "propose_rate_change":
            new = parse_amount(args.get("new_rate"))
            old = (current_rates or {}).get(cid)
            if new <= 0 or old is None or old <= 0:
                return Deny("INVALID_INPUT", "bad rate")
            # never applied directly; only flagged for the approval diff
            if abs(new - old) / old > Decimal("0.25"):
                return Allow(("RATE_CHANGE_OVER_25PCT",))
        elif action != "propose_bank_change":
            return Deny("INVALID_INPUT", f"unknown action {action}")
    except (TypeError, MoneyError):
        return Deny("INVALID_INPUT", "unparseable number")
    return Allow()
