"""Tool dispatch for ONE tenant. The tenant and run are fixed by the harness when the ToolBox is built: no tool
takes a tenant, and none can move money. Every input is validated again here (pydantic), then by gate.check_propose.
"""
from __future__ import annotations

import json
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, ValidationError

from .. import gate, inbox, seed, store
from ..money import parse_amount
from ..orchestrator import Orchestrator, Refused
from . import prompts

MAX_TOOL_TEXT = 3000


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Empty(_In):
    pass


class Timesheet(_In):
    doc_id: str
    contractor_id: str
    hours: str


class RateChange(_In):
    doc_id: str
    contractor_id: str
    new_rate: str
    note: str


class BankChange(_In):
    doc_id: str
    contractor_id: str
    bank_details: dict[str, str]


class Submit(_In):
    summary: str


class Hold(_In):
    reason_code: str
    note: str


class Flag(_In):
    doc_id: str
    reason: str


class Finish(_In):
    headline: str
    explanation: str
    next_step: str


SCHEMAS = {"read_inbox": Empty, "get_run": Empty, "propose_timesheet": Timesheet, "propose_rate_change": RateChange,
           "propose_bank_change": BankChange, "request_funding": Empty, "submit_for_approval": Submit,
           "hold_run": Hold, "flag_suspicious": Flag, "finish_tick": Finish}
assert set(SCHEMAS) == {t["name"] for t in prompts.TOOLS}


class ToolError(Exception):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


class ToolBox:
    def __init__(self, orch: Orchestrator, tenant: str, run_id: str):
        self.o, self.tenant, self.run_id = orch, tenant, run_id
        self.tick_docs: list[inbox.Doc] = []  # every document read this tick, so a fallback agent sees them too
        self.finished: dict | None = None
        self.flagged: set[str] = set()

    # -- entry point ---------------------------------------------------------------------------------
    def dispatch(self, name: str, raw: object) -> tuple[str, bool]:
        """(text for the model, is_error). Never raises; a bad call is an error result and a ledger line."""
        try:
            if name not in SCHEMAS:
                raise ToolError("UNKNOWN_TOOL", name)
            args = SCHEMAS[name].model_validate(raw).model_dump()
            out = getattr(self, f"_{name}")(**args)
            return (out if isinstance(out, str) else json.dumps(out, default=str))[:MAX_TOOL_TEXT], False
        except ValidationError:
            return self._deny(name, "INVALID_INPUT", "arguments do not match the tool schema")
        except ToolError as e:
            return self._deny(name, e.code, str(e))
        except Refused as e:
            return self._deny(name, "REFUSED", str(e))
        except (KeyError, ValueError, LookupError, PermissionError) as e:
            return self._deny(name, "INVALID_INPUT", str(e)[:200])

    def _deny(self, name: str, code: str, detail: str) -> tuple[str, bool]:
        self.o.L.append("GATE_DENY", {"source": "agent_tool", "tool": name, "code": code, "detail": detail[:200]},
                        self.run_id, self.tenant)
        return f"{code}: {detail}"[:300], True

    def _note(self, **p) -> None:
        self.o.L.append("AGENT_NOTE", p, self.run_id, self.tenant)

    def _check(self, action: str, args: dict) -> gate.Allow:
        d = gate.check_propose(action, self.tenant, frozenset(seed.contractors(self.tenant)), args,
                               parsed_hours=inbox.load_timesheet(self.tenant),
                               current_rates={k: c.rate for k, c in seed.contractors(self.tenant).items()})
        if isinstance(d, gate.Deny):
            raise ToolError(d.code, d.detail)
        return d

    # -- tools -----------------------------------------------------------------------------------------
    def _read_inbox(self) -> str:
        seen = inbox.seen_ids(self.o.L, self.tenant)
        docs = [d for d in inbox.all_docs(self.tenant) if d.id not in seen]
        self.tick_docs += docs
        for d in docs:
            self._note(read_doc=d.id, source=d.source)
        if not docs:
            return "No new documents."
        return "\n".join(f'<untrusted_document id="{d.id}" source="{d.source}">\n{d.text}\n</untrusted_document>'
                         for d in docs)

    def _get_run(self) -> dict:
        d = self.o.diff(self.run_id, self.tenant)
        return {"state": d["state"], "totals": d["totals"], "changes": d["changes"], "unchanged": d["unchanged"],
                "shortfall": d["shortfall"], "bank_changes_pending": [b for b in d["bank_changes"] if b["status"] == "ACTIVE"],
                "rate_requests": d["rate_requests"], "approver_role": d["approver_role"],
                "funding_request": funding_state(self.o, self.run_id, self.tenant), "balances": {k: str(v) for k, v in self.o.awx.for_tenant(self.tenant).balances().items()
                                                          if k in d["totals"]}}

    def _propose_timesheet(self, doc_id: str, contractor_id: str, hours: str) -> str:
        self._check("propose_timesheet", {"contractor_id": contractor_id, "hours": hours})
        self.o.L.append("PROPOSAL", {"kind": "timesheet", "doc_id": doc_id, "contractor_id": contractor_id,
                                     "hours": str(parse_amount(hours))}, self.run_id, self.tenant)
        return f"{contractor_id}: {hours} h matches the parsed timesheet; priced by code from the registry rate."

    def _propose_rate_change(self, doc_id: str, contractor_id: str, new_rate: str, note: str) -> str:
        flags = self._check("propose_rate_change", {"contractor_id": contractor_id, "new_rate": new_rate}).flags
        req = self.o.note_rate_request(self.run_id, self.tenant, contractor_id, Decimal(parse_amount(new_rate)), doc_id, note)
        return f"Recorded for the approver, NOT applied{' (over 25%: flagged red)' if flags else ''}. Amount unchanged: {req['old_rate']}/h."

    def _propose_bank_change(self, doc_id: str, contractor_id: str, bank_details: dict) -> str:
        self._check("propose_bank_change", {"contractor_id": contractor_id})
        bank = {k: v.strip() for k, v in bank_details.items() if v and v.strip()}
        q = self.o.propose_bank_change(self.run_id, self.tenant, contractor_id, bank, doc_id, "agent")
        return (f"Quarantined (item {q['id']}). Existing details stay in force until a different approver confirms "
                f"by phone. Validation: {'ok' if q['valid'] else q['validation']}.")

    def _request_funding(self) -> str:
        run = store.get_run(self.o.L, self.run_id, self.tenant)
        _, _, short = self.o._plan(self.run_id, self.tenant)
        if not short:
            return "No funding needed: this employer's own balance covers the run."
        if run["state"] == "DRAFT":
            self.o.submit(self.run_id, self.tenant)  # issues the funding request(s) and moves to AWAITING_FUNDS
        req = self.o.L.entries(run_id=self.run_id, kind="FUNDING_REQUESTED", tenant=self.tenant)
        if not req:
            raise ToolError("INVALID_INPUT", f"cannot request funding while {run['state']}")
        p = req[-1]["payload"]
        return f"Funding request {p['reference']}: {p['amount']} {p['currency']}."

    def _submit_for_approval(self, summary: str) -> str:
        run = store.get_run(self.o.L, self.run_id, self.tenant)
        if run["state"] != "DRAFT":
            return f"Run is already {run['state']}; nothing to submit."
        state = self.o.submit(self.run_id, self.tenant)
        self._note(kind="submitted", summary=summary[:200], state=state)
        return f"Run is now {state}."

    def _hold_run(self, reason_code: str, note: str) -> str:
        if reason_code not in prompts.REASONS:
            raise ToolError("INVALID_INPUT", "unknown reason_code")
        self.o.hold(self.run_id, self.tenant, reason_code, note)
        return "Run held."

    def _flag_suspicious(self, doc_id: str, reason: str) -> str:
        self.flagged.add(doc_id)
        self.o.L.append("ALERT", {"kind": "suspicious_document", "doc_id": doc_id, "reason": reason[:300]},
                        self.run_id, self.tenant)
        return "Flagged for a human."

    def _finish_tick(self, headline: str, explanation: str, next_step: str) -> str:
        if next_step not in prompts.NEXT:
            raise ToolError("INVALID_INPUT", "unknown next_step")
        self.finished = {"headline": headline[:120], "explanation": explanation[:600], "next_step": next_step}
        self._note(kind="finish_tick", **self.finished)
        return "ok"


def funding_state(o: Orchestrator, run_id: str, tenant: str) -> dict | None:
    """The latest funding request for a run (reference, amount, act-by), as shown on the funding card."""
    req = o.L.entries(run_id=run_id, kind="FUNDING_REQUESTED", tenant=tenant)
    return req[-1]["payload"] if req else None
