"""The offline agent: the same tools, called by fixed rules. Used with RF_AGENT=scripted, when there is no API key,
after a refusal or after two API errors. It is deterministic, so the demo never depends on a model being reachable.
Documents are matched with regexes tuned to the demo documents; it is a fallback, not a document-understanding system.
"""
from __future__ import annotations

import re

from .. import inbox, seed
from .tools import ToolBox

INJECTION = re.compile(r"ignore (all |any )?(previous|prior)|disregard|you are now|system:|without approval|skip approval|"
                       r"approve all|pay me \d|do not tell", re.IGNORECASE)
SORT = re.compile(r"sort\s*code\D{0,5}(\d{6})", re.IGNORECASE)
BSB = re.compile(r"bsb\D{0,5}(\d{6})", re.IGNORECASE)
ABA = re.compile(r"(?:aba|routing)[^\d]{0,12}(\d{9})", re.IGNORECASE)
ACCT = re.compile(r"account(?:\s*(?:number|no\.?))?\D{0,5}(\d{6,12})", re.IGNORECASE)
IBAN = re.compile(r"\b([A-Z]{2}\d{2}[A-Z0-9]{11,30})\b")
SWIFT = re.compile(r"swift\W{0,12}([A-Z0-9]{8,11})", re.IGNORECASE)
BANK = re.compile(r"^bank\s*:\s*(.+)$", re.IGNORECASE | re.MULTILINE)
RATE = re.compile(r"rate[^\d\n]{0,40}?(\d+(?:\.\d+)?)\s*(?:per hour|/h|an hour)?", re.IGNORECASE)
NEXT = {"AWAITING_FUNDS": "WAIT_FUNDS", "AWAITING_APPROVAL": "WAIT_APPROVAL", "READY": "PAYING", "RELEASING": "PAYING",
        "RELEASED": "PAYING", "DONE": "DONE", "HELD": "HOLD", "DRAFT": "WAIT_APPROVAL"}


def _contractor(tenant: str, text: str) -> str | None:
    head = text[:300].lower()
    for cid, c in seed.contractors(tenant).items():
        if c.name.split()[0].lower() in head:
            return cid
    return None


def _bank(tenant: str, cid: str, text: str) -> dict | None:
    cur = next(c for c in seed.contractor_seeds(tenant) if c["id"] == cid)["bank"]
    keys = dict.fromkeys(("country", "bank_name", "routing_type", "routing_value", "account_number", "iban",
                          "swift_code", "category"), "")
    keys["country"] = cur["country"]
    keys["category"] = cur.get("category", "")
    if m := BANK.search(text):
        keys["bank_name"] = m.group(1).strip()
    if m := IBAN.search(text):
        keys["iban"], keys["bank_name"] = m.group(1), keys["bank_name"] or cur["bank_name"]
        if s := SWIFT.search(text):
            keys["swift_code"] = s.group(1).upper()
        return keys if keys["swift_code"] else None
    for rt, rx in (("sort_code", SORT), ("bsb", BSB), ("aba", ABA)):
        if (m := rx.search(text)) and (a := ACCT.search(text)):
            keys.update(routing_type=rt, routing_value=m.group(1), account_number=a.group(1))
            return keys
    return None


def run(tb: ToolBox) -> None:
    t = tb.tenant
    tb.dispatch("read_inbox", {})
    for d in tb.tick_docs:
        if d.source == "timesheet":
            try:
                rows = inbox.parse_timesheet(t, d.text)
            except inbox.TimesheetError:
                continue
            for cid, h in rows.items():
                tb.dispatch("propose_timesheet", {"doc_id": d.id, "contractor_id": cid, "hours": str(h)})
            continue
        if INJECTION.search(d.text):
            tb.dispatch("flag_suspicious", {"doc_id": d.id, "reason": "contains instructions aimed at the payroll system"})
        cid = _contractor(t, d.text)
        if cid is None:
            continue
        if bank := _bank(t, cid, d.text):
            tb.dispatch("propose_bank_change", {"doc_id": d.id, "contractor_id": cid, "bank_details": bank})
        elif (m := RATE.search(d.text)) and not INJECTION.search(d.text):
            tb.dispatch("propose_rate_change", {"doc_id": d.id, "contractor_id": cid, "new_rate": m.group(1),
                                                "note": "requested by email"})
    run_json = tb.o.diff(tb.run_id, t)
    state = run_json["state"]
    if state == "DRAFT":
        if run_json["shortfall"]:
            tb.dispatch("request_funding", {})
        else:
            tb.dispatch("submit_for_approval", {"summary": "priced from the registry rates and the parsed timesheet"})
        state = tb.o.diff(tb.run_id, t)["state"]
    n_q = sum(1 for b in run_json["bank_changes"] if b["status"] == "ACTIVE")
    bits = [f"{len(run_json['changes']) + run_json['unchanged']['count']} lines priced"]
    if n_q:
        bits.append(f"{n_q} bank change{'s' if n_q > 1 else ''} quarantined, old details still in force")
    if tb.flagged:
        bits.append(f"{len(tb.flagged)} document{'s' if len(tb.flagged) > 1 else ''} flagged as suspicious")
    tb.dispatch("finish_tick", {"headline": f"{t.title()}: run is {state.replace('_', ' ').lower()}",
                                "explanation": "; ".join(bits).capitalize() + ".", "next_step": NEXT.get(state, "HOLD")})
