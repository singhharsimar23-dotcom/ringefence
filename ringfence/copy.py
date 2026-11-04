"""Every sentence the product shows comes from here (and static/copy.js for the browser), never from the model.
The model writes one thing only: the timeline headline, and only if it is short, plain text (see `agent_line`).
"""
from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal

from . import seed
from .config import employer_name
from .gate import REASON_CODES

BUSY = "Someone else just pressed a button on this shared demo. Try again in a moment."
TOO_BIG = "That request is too large for this demo."
BUSY_RESET = "Someone started over a moment ago. Try again in 20 seconds."
WORLD_SETUP_FAILED = "Couldn't reach the Airwallex sandbox ({code}). Nothing was sent. Try Simulated bank."
TOO_FAST = "That was a little fast. Try again in a second."
TOO_LARGE = "That request is too large."
NOT_FOUND = "Nothing here."
LIVE_ONE_EMPLOYER = "The Airwallex sandbox run takes one company. Use Simulated bank for more."
LIVE_UNAVAILABLE = "The Airwallex sandbox isn't available right now. Try Simulated bank."
PLAY_DAILY = "Today's runs are used up. Come back tomorrow, or open Three employers."
PLAY_FULL = "Every slot and the waiting line are full. Try again in a few minutes."
WORLD_GONE = "This run was cleaned up. Runs last at most 30 minutes. Start a new one."
WORLD_QUEUED = "This run is still waiting for a slot."
WORLD_STARTING = "This run is still starting. Try again in a few seconds."
WORLD_STOPPED = "This run stopped before it could finish. Nothing was sent. Start a new one."
WORLD_START_TIMEOUT = "This run took too long to start. Nothing was sent. Start a new one."
DRAFT_UNAVAILABLE = "Reading free text is switched off right now. Pick an example or fill in the form."
DRAFT_NOTHING = "I couldn't find people, hours or rates. Try an example."
DRAFT_TRIMMED = "Only the first 6 people are kept."
DRAFT_COUNTRY = "{country} isn't set up in this demo. Available: UK, Germany, US, Australia."
DRAFT_CSV_DEFAULTS = "Company set to {name}, paid from {ccy}. Change it below."
START_FAILED = "The agent could not finish reading the inboxes. Nothing was sent; see the timeline."

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

# Attack cards: what was attempted, which rule decided, who decided. rule is a gate code where one fits.
# id -> (what was attempted, rule id, who decided, what the rule says; empty = use REASON_TEXT[rule])
SCENARIO_EVIDENCE = {
    "bank_change_email": ("An email from a contractor changes the bank account and asks to skip approval.",
                          "BENEFICIARY_QUARANTINED", "Ringfence's gate (code)", ""),
    "injection": ("A document tells the payroll agent to ignore its rules and approve everything.",
                  "INSTRUCTION_IGNORED", "Ringfence's tools (code)",
                  "The document was flagged for a person. It cannot change an amount, a payee or an approval."),
    "double_click": ("Four release requests arrive at once on the same approved run.",
                     "ONE_PAYMENT_KEY", "Ringfence's executor (code)",
                     "Each payout has one payment key and one database claim, so a repeat finds the work done."),
    "network_drop": ("Airwallex takes the payment but the answer is lost.",
                     "FIND_BY_PAYMENT_KEY", "Ringfence's executor (code)",
                     "After a timeout Ringfence looks the payment up by its key instead of sending it again."),
    "tamper_ledger": ("Someone with the database file edits one recorded amount.",
                      "LEDGER_HASH_CHAIN", "The hash chain (code)",
                      "Every row's hash includes the row before it, so one edit breaks the chain at that row."),
    "cross_tenant_call": ("One employer's login tries to act on another employer's account.",
                          "AIRWALLEX_ACCOUNT_ISOLATION", "Airwallex",
                          "Airwallex refused the login with HTTP 401. Ringfence cannot even try."),
    "rate_move": ("The exchange rate moves past the approved range after approval.",
                  "FX_RATE_OUT_OF_BAND", "Ringfence's gate (code)", ""),
    "other_tenant_deposit": ("Money lands in another employer's account while this one is short.",
                             "OWN_FUNDS_ONLY", "Ringfence's funding check (code)",
                             "A deposit in another employer's account can never change this employer's state."),
    "topup": ("The employer's own bank sends what the funding card asked for.",
              "FUNDING_MATCHED_BY_REFERENCE", "Ringfence's funding check (code)",
              "The deposit is matched by account, currency and reference, in this employer's own account only."),
    "late_return": ("A paid payout bounces back from the beneficiary's bank.",
                    "RETURN_NEEDS_NEW_APPROVAL", "Ringfence's executor (code)",
                    "A late return is tracked, and paying it again is a new payment that needs its own approval."),
}
SCENARIO_EVIDENCE["harbour_topup"] = SCENARIO_EVIDENCE["topup"]
SCENARIO_EVIDENCE["metal_topup"] = ("Harbour Foods is short, so we take the missing amount from its crypto wallet.",
                                    "METAL_MANDATE", "The Metal blockchain",
                                    "Harbour Foods allowed one payment: the exact missing amount, once, to us only.")
SCENARIO_EVIDENCE["metal_overpull"] = ("The agent tries to take 1 coin more than Harbour Foods allowed.",
                                       "METAL_MANDATE_CAP", "The Metal blockchain",
                                       "The blockchain refused and recorded the refusal. Our own checks would have stopped it too.")
SCENARIO_EVIDENCE["metal_poison"] = ("An email asks the platform to send Harbour's money to a lookalike wallet (address poisoning).",
                                     "METAL_MANDATE_PAYEE", "Our checks, then the Metal blockchain",
                                     "We compare the whole address, not just the start and end, so the fake is caught. The blockchain only pays the one wallet Harbour Foods named, so it refuses too.")
METAL_FALLBACK = "Crypto wallet didn't answer, so we used Airwallex's simulated deposit."
ALREADY_FUNDED = "{t}'s top-up for this run was already sent. Nothing more was added."
NOT_SHORT = "{t} is not waiting for funds right now."
HELD_NO_ACCOUNT = "{t} has no {ccy} account, so this rule can't be met."
RESET_UNREACHABLE = "Airwallex didn't answer, so nothing was wiped. Try again in a moment."
RESET_PARTIAL = "The demo was wiped, but setting up the accounts failed. Press Start over again."
NO_RUN_TO_STAGE = "Every payroll in this take has already gone out. Press Start over to run it again."
BUSY_METAL = "The crypto wallet is already busy with another test. Try again in a minute."
PLAY_STREAMS = "Too many live views are open. This page checks again every few seconds instead."
PLAY_IP_DAILY = "You've used today's runs from this connection. Come back tomorrow, or open Three employers."


def plain_refusal(msg: str) -> str:
    """The state machine's refusals carry run ids and state names. A person gets a sentence instead."""
    m = msg.lower()
    for needle, text in (("may not approve", "That person may not approve this employer's payroll. Switch to its finance approver."),
                         ("not awaiting_approval", "This payroll isn't waiting for approval right now. It may already be approved or sent."),
                         ("not draft", "This payroll was already submitted."),
                         ("only a held run", "Only a held payroll can be resumed."),
                         ("cannot hold", "This payroll has already gone out, so it can't be held."),
                         ("already exists", "This payroll was already created."),
                         ("no run", "There is no payroll yet. Press Run Friday payroll first."),
                         ("no beneficiary", "A contractor has no bank details on file, so the payroll can't start.")):
        if needle in m:
            return text
    return msg  # rules and gate refusals are already written for a person

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
    t = employer_name(tenant, plain=True) if tenant else "This employer"
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


# What is real, what is the sandbox's simulator, what we made up. One map; the browser reads it from /api/state.
REALITY = {"live": "Live on Airwallex", "chain": "On Metal testnet", "awx_sim": "Airwallex simulator", "ours": "Simulated by us",
           "fake": "Offline test double"}
CARD_REALITY = {
    "double_click": "live", "network_drop": "live", "cross_tenant_call": "live", "tamper_ledger": "ours", "rate_move": "ours",
    "bank_change_email": "ours", "injection": "ours", "other_tenant_deposit": "awx_sim", "harbour_topup": "awx_sim",
    "topup": "awx_sim", "late_return": "awx_sim", "metal_topup": "chain", "metal_overpull": "chain", "metal_poison": "chain"}
ROW_REALITY = {"SUBMITTED": "live", "UNKNOWN": "live", "RECONCILED": "live", "FX_CONVERTED": "live", "FEE_CHARGED": "live",
               "FUNDING_MATCHED": "awx_sim", "STATUS": "awx_sim", "FEE_CREDIT": "ours", "METAL_PULL": "chain", "METAL_REFUSED": "chain"}


def row_reality(kind: str, p: dict) -> str | None:
    """Which level a timeline row belongs to. Decisions our own code makes (gate, approval, hold) have none: nothing outside is involved."""
    if kind == "SIMULATED":
        return "ours" if "fee credit" in p.get("what", "") or "approval given" in p.get("what", "") else "awx_sim"
    return ROW_REALITY.get(kind)


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
                "next": "", "action": "proof", "tone": "green"}
    if st == "HELD":
        why = run.get("hold_reason") or ""
        return {"status": "Held. Nothing was sent.", "next": why if " " in why else "Next: a person decides whether to resume.",
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


TOOL_LABEL = {"propose_timesheet": "A timesheet figure", "propose_rate_change": "A rate change", "propose_bank_change": "New bank details",
              "request_funding": "A funding request", "submit_for_approval": "Send for approval", "hold_run": "Hold the run"}


def proposed_text(tool: str, raw, tenant: str | None) -> str:
    """The agent's own words for what it asked, from its tool input. Short, plain, never longer than a line."""
    a = raw if isinstance(raw, dict) else {}
    who = _name(tenant, a.get("contractor_id") if isinstance(a.get("contractor_id"), str) else None)
    if tool == "propose_timesheet" and "hours" in a:
        return f"{who}: {str(a['hours'])[:12]} hours"[:120]
    if tool == "propose_rate_change" and "new_rate" in a:
        return f"{who}: rate {str(a['new_rate'])[:12]} an hour"[:120]
    if tool == "propose_bank_change" and isinstance(a.get("bank_details"), dict):
        n = str(a["bank_details"].get("account_number") or a["bank_details"].get("iban") or "")
        return f"New bank details for {who}{f' ending {n[-4:]}' if n else ''}"[:120]
    return TOOL_LABEL.get(tool, "An agent request")


def decision_rows(e: dict) -> list[dict]:
    """The Proposed vs decided table: what the agent asked, what the rules did, why, and the ledger number."""
    k, p, t = e["kind"], e["payload"], e["tenant"]
    who = _name(t, p.get("contractor_id"))
    row = None
    if k == "PRICED":
        return [{"seq": e["seq"], "kind": k, "tenant": t, "doc_id": None, "tone": "ok",
                 "proposed": f"{_name(t, cid)}: {v['hours']} hours", "decided": f"Priced at {money(v['currency'], v['amount'])}",
                 "why": f"Code priced it from the registry rate of {v['rate']} an hour."} for cid, v in p.get("lines", {}).items()]
    if k == "PROPOSAL" and p.get("kind") == "timesheet":
        row = (f"{who}: {p['hours']} hours", "Accepted", "It matches the timesheet that code parsed.", "ok")
    elif k == "PROPOSAL" and p.get("kind") == "rate_change":
        row = (f"{who}: rate {p['new_rate']} an hour", "Recorded, not applied",
               "Rates come from the registry, not from an email." + (" The approver sees it in red." if p.get("over_25pct") else ""), "held")
    elif k == "BENEFICIARY_QUARANTINED":
        row = (f"New bank details for {who}{f' ending {p['last4']}' if p.get('last4') else ''}", "Held in quarantine",
               "The old details stay in force until a different approver confirms by phone.", "held")
    elif k == "ALERT" and p.get("kind") == "suspicious_document":
        row = ("Instructions inside an email", "Flagged for a human", str(p.get("reason", ""))[:160] or "None of the instructions were followed.", "flag")
    elif k == "GATE_DENY" and p.get("source") == "agent_tool":
        code = p.get("code", "")
        detail = re.sub(r"^(?:[A-Z_]+: )+", "", str(p.get("detail", "")))
        row = (p.get("proposed") or TOOL_LABEL.get(p.get("tool", ""), "An agent request"), "Refused",
               reason(code, t or "") if code in REASON_TEXT else (detail or reason(code, t or "")), "refused")
    if row is None:
        return []
    return [{"seq": e["seq"], "kind": k, "tenant": t, "doc_id": p.get("doc_id"), "tone": row[3],
             "proposed": row[0], "decided": row[1], "why": row[2]}]


def timeline_row(e: dict) -> dict | None:
    """(phase, sentence) for one ledger entry, or None for rows that are noise on the main surface."""
    k, p, t = e["kind"], e["payload"], e["tenant"]
    T = employer_name(t or "", plain=True)
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
        row = ("Decide", "Auto-approved: nothing changed since last week and it is within the agreed limits." if p.get("auto_release")
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
    elif k == "METAL_PULL":
        row = ("Act", f"Paid {p['usdz']} test coins from {T}'s crypto wallet on the Metal blockchain.")
    elif k == "METAL_REFUSED" and p.get("flag") == "address_poisoning":
        row = ("Decide", f"Blocked a fake lookalike wallet ({p['to'][:10]}…{p['to'][-4:]}). The blockchain refused it too.")
    elif k == "METAL_REFUSED":
        row = ("Decide", f"The blockchain blocked a payment of {p['usdz']} coins: more than {T} allowed.")
    elif k == "ALERT" and p.get("kind") == "metal_recycle_failed":
        row = ("Reconcile", "The test coins could not be sent back to the crypto wallet. It may run low until someone tops it up.")
    elif k == "ALERT" and p.get("kind") == "start_failed":
        row = ("Decide", START_FAILED)
    elif k == "RESET":
        row = ("Observe", "Started again. The previous run is saved.")
    if row is None:
        return None
    return {"seq": e["seq"], "ts": e["ts"], "tenant": t, "phase": row[0], "text": row[1], "kind": k,
            "blocked": k == "GATE_DENY" or (k == "ALERT"), "simulated": row[1].startswith("[SIMULATED]"), "reality": row_reality(k, p)}
