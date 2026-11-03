"""Every sentence the product shows comes from here (and static/copy.js for the browser), never from the model.
The model writes one thing only: the timeline headline, and only if it is short, plain text (see `agent_line`).
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from . import seed
from .gate import REASON_CODES

BUSY = "Someone else just pressed a button on this shared demo. Try again in a moment."

# Gate reason codes. {t} = employer name. One table, shown wherever a deny appears.
REASON_TEXT = {
    "KILL_SWITCH": "All payouts are paused. Payments already sent are still tracked.",
    "RUN_NOT_OPEN": "This run is not open for release, so nothing was sent.",
    "NO_MANDATE": "{t} has no signed mandate, so nothing can be paid.",
    "MANDATE_SIG_INVALID": "{t}'s mandate signature does not verify, so nothing was paid.",
    "MANDATE_EXPIRED": "{t}'s mandate has expired and needs to be signed again.",
    "TENANT_MISMATCH": "A payout did not belong to {t}'s own account, so the run was stopped.",
    "CURRENCY_NOT_ALLOWED": "{t}'s mandate does not allow paying in that currency.",
    "PAYEE_NOT_ALLOWED": "That contractor is not on {t}'s approved list.",
    "BENEFICIARY_NOT_IN_TENANT": "The bank details are not ones {t} registered, so the payout was stopped.",
    "BENEFICIARY_IS_OTHER_TENANT_ACCOUNT": "The destination is another employer's account. It was blocked.",
    "BENEFICIARY_QUARANTINED": "New bank details are on hold until someone confirms them by phone.",
    "AMOUNT_MISMATCH": "The amount does not equal hours times the registered rate, so it was not paid.",
    "OVER_LINE_CAP": "A payout is above {t}'s per-payment limit.",
    "OVER_RUN_CAP": "The run total is above {t}'s limit for that currency.",
    "DUPLICATE_LINE": "The same contractor appeared twice in one run, so nothing was sent.",
    "INSUFFICIENT_OWN_FUNDS": "{t}'s own wallet is short. Other employers' money is never used.",
    "APPROVAL_MISSING": "This run needs an approval before anything is paid.",
    "APPROVAL_HASH_MISMATCH": "The batch changed after it was approved, so it needs a fresh approval.",
    "APPROVAL_EXPIRED": "The approval ran out of time, so it needs to be given again.",
    "APPROVER_NOT_AUTHORISED": "That person is not the approver named in {t}'s mandate.",
    "SOD_VIOLATION": "The person who changed bank details cannot also approve the payment.",
    "FX_NOT_ALLOWED": "{t}'s mandate does not allow currency conversion.",
    "FUNDING_CURRENCY_NOT_ALLOWED": "{t}'s mandate does not allow converting from that currency.",
    "FX_RATE_OUT_OF_BAND": "The exchange rate moved past the approved range, so it needs a fresh approval.",
    "INVALID_INPUT": "That proposal did not pass the checks and was ignored.",
}
assert set(REASON_TEXT) == set(REASON_CODES), "every gate reason code needs a sentence"

# Codes raised by the executor and the agent tools outside the gate.
EXTRA_TEXT = {
    "FACTS_UNAVAILABLE": "Airwallex did not answer when balances were read, so nothing was sent.",
    "FX_FAILED": "The currency conversion did not go through, so the run was stopped.",
    "DUPLICATE_MISMATCH": "A payment with this key already exists with different details. A person needs to look.",
    "UNKNOWN_STATUS": "Airwallex reported a status Ringfence does not know, so the payout was held.",
    "UNKNOWN_AFTER_RETRY": "The payout's outcome is still unknown after checking. A person needs to look.",
    "UNKNOWN_TOOL": "The agent asked for something it cannot do.",
    "REFUSED": "That action is not allowed in the run's current state.",
}


def reason(code: str, tenant: str = "") -> str:
    t = tenant.title() if tenant else "This employer"
    return (REASON_TEXT.get(code) or EXTRA_TEXT.get(code) or "That action was blocked.").format(t=t)


def money(ccy: str, amount: str | Decimal) -> str:
    return f"{ccy} {Decimal(str(amount)):,.2f}"


def totals(t: dict[str, str]) -> str:
    return " + ".join(money(c, a) for c, a in sorted(t.items())) or "nothing yet"


def plural(n: int, one: str, many: str | None = None) -> str:
    return f"{n} {one if n == 1 else (many or one + 's')}"


def countdown(then: datetime, now: datetime) -> str:
    s = int((then - now).total_seconds())
    if s <= 0:
        return "now"
    h, m = divmod(s // 60, 60)
    return f"{h}h {m:02d}m" if h else f"{m}m"


LINE_PILL = {
    "PLANNED": "Planned", "READY": "Needs OK", "INTENT": "On its way", "SUBMITTED": "On its way",
    "UNKNOWN": "On its way", "IN_APPROVAL": "On its way", "SCHEDULED": "On its way", "PROCESSING": "On its way",
    "SENT": "On its way", "OVERDUE": "On its way", "PAID": "Paid", "RETURNED": "Returned", "FAILED": "Held",
    "FAILED_TO_SUBMIT": "Held", "HOLD": "Held", "HOLD_UNKNOWN": "Held",
}


def pill(line_state: str, run_state: str) -> str:
    if line_state in ("PLANNED", "READY") and run_state in ("AWAITING_APPROVAL", "AWAITING_FUNDS", "DRAFT"):
        return "Needs OK" if run_state == "AWAITING_APPROVAL" else "Planned"
    if run_state in ("READY", "RELEASING") and line_state in ("PLANNED", "READY"):
        return "On its way"  # approved, being sent: not waiting for anyone
    if run_state == "HELD" and line_state in ("PLANNED", "READY"):
        return "Held"
    return LINE_PILL.get(line_state, "Planned")


def lane_text(name: str, run: dict | None, d: dict | None, req: dict | None, now: datetime,
              displayed_ccy_total: str) -> dict:
    """The big status sentence, the 'next' line and the one primary action for a lane.
    d is orchestrator.diff(); req is the latest funding request payload."""
    if run is None:
        return {"status": "No payroll run yet for this week.", "next": "Start Friday payroll to read the timesheet.",
                "action": "start", "tone": "idle"}
    st, tot = run["state"], totals(d["totals"]) if d else ""
    returned = sum(1 for ln in run["lines"] if ln["state"] == "RETURNED")
    if returned:
        return {"status": f"{plural(returned, 'payout')} returned after payment.",
                "next": "A new approval is needed before the returned payout is sent again.",
                "action": "review" if st == "AWAITING_APPROVAL" else "none", "tone": "red"}
    if st == "AWAITING_FUNDS" and req:
        left = countdown(datetime.fromisoformat(req["act_by"]), now)
        return {"status": f"Short {money(req['currency'], req['amount'])}: fund by {datetime.fromisoformat(req['act_by']):%a %H:%M %Z} ({left}).",
                "next": f"Next: pays after {money(req['currency'], req['amount'])} arrives in {name}'s own {req['currency']} account.",
                "action": "copy_funding", "tone": "amber"}
    if st == "AWAITING_APPROVAL":
        n = len(d["changes"]) + len(d["bank_changes"]) if d else 0
        return {"status": (f"Needs your OK: {plural(n, 'change')} since last week." if n else "Needs your OK: nothing changed."),
                "next": f"Next: {name} pays {tot} once {d['approver_role'].split(':')[-1].title()} finance approves." if d else "",
                "action": "approve", "tone": "amber"}
    if st in ("READY", "RELEASING"):
        return {"status": f"Paying {plural(len(run['lines']), 'contractor')} · {tot}", "next": "Next: sending the payments now.",
                "action": "none", "tone": "blue"}
    if st == "RELEASED":
        paid = sum(1 for ln in run["lines"] if ln["state"] == "PAID")
        return {"status": f"{paid} of {len(run['lines'])} paid · {tot}",
                "next": "Next: Ringfence checks each payment with Airwallex until it lands.", "action": "none", "tone": "blue"}
    if st == "DONE":
        return {"status": f"Paid {plural(len(run['lines']), 'contractor')} · {tot}",
                "next": "Done. The proof page shows exactly where the money went.", "action": "proof", "tone": "green"}
    if st == "HELD":
        return {"status": "Held. Nothing was sent.", "next": "Next: a person decides whether to resume.",
                "action": "resume", "tone": "red"}
    return {"status": f"Run created · {tot}", "next": "Next: the agent prepares it.", "action": "none", "tone": "idle"}


def agent_line(headline: str) -> str | None:
    """The model's timeline sentence, only if it is plain and short; otherwise the caller uses the template."""
    h = headline.strip()
    if not h or len(h) > 140 or re.search(r"[*_`#\[\]<>]|!", h) or re.search(r"[^\x00-\x7f£€·—]", h):
        return None
    return h


def _name(tenant: str | None, cid: str | None) -> str:
    try:
        return seed.contractors(tenant)[cid].name if tenant and cid else (cid or "a contractor")
    except KeyError:
        return cid or "a contractor"


def timeline_row(e: dict) -> dict | None:
    """(phase, sentence) for one ledger entry, or None for rows that are noise on the main surface."""
    k, p, t = e["kind"], e["payload"], e["tenant"]
    T = (t or "").title()
    who = _name(t, p.get("contractor_id"))
    row = None
    if k == "RUN_CREATED":
        row = ("Observe", f"Read {T}'s timesheet: {plural(len(p.get('contractors', [])), 'contractor')}.")
    elif k == "AGENT_NOTE" and "read_doc" in p and p.get("source") == "email":
        row = ("Observe", f"Read an email in {T}'s inbox.")
    elif k == "AGENT_NOTE" and p.get("kind") == "finish_tick" and not p.get("generic"):
        row = ("Decide", agent_line(p.get("headline", "")) or f"Ringfence agent finished its review of {T}.")
    elif k == "PROPOSAL" and p.get("kind") == "rate_change":
        pct = (Decimal(p["new_rate"]) - Decimal(p["old_rate"])) / Decimal(p["old_rate"]) * 100
        row = ("Decide", (f"{who} asked for {p['new_rate']} an hour ({pct:+.0f}%). Not applied; the approver sees it"
                         f"{' in red' if p.get('over_25pct') else ''}."))
    elif k == "ALERT" and p.get("kind") == "suspicious_document":
        row = ("Decide", f"Flagged an email to {T} as suspicious: it contains instructions. None were followed.")
    elif k == "ALERT" and p.get("kind") == "timesheet_rejected":
        row = ("Observe", f"{T}'s timesheet failed the strict check, so no run was created.")
    elif k == "BENEFICIARY_QUARANTINED":
        row = ("Act", f"New bank details for {who} (ending {p.get('last4', '')}) are on hold until someone else confirms by phone.")
    elif k == "CALLBACK_CONFIRMED":
        row = ("Act", f"{p['confirmed_by']} confirmed {who}'s new bank details by phone.")
    elif k == "FUNDING_REQUESTED":
        row = ("Decide", (f"{T} is short {money(p['currency'], p['amount'])}. Asked {T} to fund its own {p['currency']} "
                         f"account, reference {p['reference']}. Other employers' money is never used."))
    elif k == "FUNDING_MATCHED":
        row = ("Observe", f"Received {money(p['currency'], p['amount'])} in {T}'s own account, reference {p['reference']}.")
    elif k == "APPROVED":
        row = ("Decide", "Auto-approved: nothing changed since last run and it is within the mandate." if p.get("auto_release")
               else f"{p['approver']} approved this exact batch for {T}.")
    elif k == "GATE_DENY":
        label = "The agent's proposal was rejected" if p.get("source") == "agent_tool" else "Blocked"
        row = ("Decide", f"{label}: {reason(p.get('code', ''), t or '')}")
    elif k == "GATE_ALLOW":
        row = ("Decide", f"All checks passed for {plural(p.get('lines', 0), 'payout')}.")
    elif k == "FX_CONVERTED":
        row = ("Act", f"Converted inside {T}'s own account to cover its shortfall.")
    elif k == "SUBMITTED":
        row = ("Act", f"Sent {who}'s payment.")
    elif k == "UNKNOWN":
        row = ("Reconcile", f"No answer from Airwallex for {who}'s payment. Checking whether it went through; nothing will be paid twice.")
    elif k == "RECONCILED":
        row = ("Reconcile", f"Checked with Airwallex: {who}'s payment exists exactly once.")
    elif k == "STATUS" and p.get("contractor_id") and p.get("state") in ("PAID", "RETURNED", "FAILED"):
        row = ("Reconcile", f"{who}: {p['state'].lower()}.")
    elif k == "REOPENED":
        row = ("Reconcile", f"{who}'s payout came back. A new approval is needed before it is sent again.")
    elif k == "FEE_CHARGED":
        row = ("Act", f"Platform fee {money('GBP', p['amount'])} paid from {T}'s own GBP wallet.")
    elif k == "FEE_CREDIT":
        row = ("Reconcile", f"Fee credited back to {T} for the returned payout.")
    elif k == "HOLD":
        row = ("Decide", f"Held {T}'s run: {reason(p.get('reason', ''), t or '') if p.get('reason') in REASON_TEXT else p.get('reason', '')}")
    elif k == "KILL_SWITCH":
        row = ("Decide", "All payouts paused." if p.get("on") else "Payouts resumed.")
    elif k == "SIMULATED":
        row = ("Observe", p.get("what", "[SIMULATED] sandbox action"))
        if not row[1].startswith("[SIMULATED]"):
            row = ("Observe", "[SIMULATED] " + row[1])
    elif k == "RESET":
        row = ("Observe", "New take: the previous one is archived and still verifiable.")
    if row is None:
        return None
    return {"seq": e["seq"], "ts": e["ts"], "tenant": t, "phase": row[0], "text": row[1], "kind": k,
            "blocked": k == "GATE_DENY" or (k == "ALERT"), "simulated": row[1].startswith("[SIMULATED]")}
