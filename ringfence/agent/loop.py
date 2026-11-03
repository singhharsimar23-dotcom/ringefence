"""One agent tick for ONE tenant: the harness binds the tenant and run, the model only calls tools.

Mode: RF_AGENT=scripted | claude | auto (default). auto = Claude when ANTHROPIC_API_KEY (or a test LLM) is available,
else the scripted agent. A refusal, max_tokens, or two API errors fall back to the scripted agent for that tick.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date

from .. import inbox, seed, store
from ..config import env
from ..orchestrator import Orchestrator
from . import prompts, scripted
from .tools import ToolBox

MAX_MODEL_CALLS, MAX_TOOLS_PER_TURN = 8, 6


@dataclass
class TickResult:
    tenant: str
    run_id: str | None
    mode: str  # "claude" | "offline agent"
    headline: str = ""
    explanation: str = ""
    next_step: str = "HOLD"
    calls: list[dict] = field(default_factory=list)
    flagged: list[str] = field(default_factory=list)
    note: str = ""


class ClaudeLLM:
    """Thin wrapper so tests can swap in a FakeLLM with the same `create(system, tools, messages)`."""

    def __init__(self):
        import anthropic
        self.client = anthropic.Anthropic()
        self.model = env("RF_MODEL", "claude-opus-5-5")
        self.errors = (anthropic.RateLimitError, anthropic.APIStatusError, anthropic.APIConnectionError)

    def create(self, system: str, tools: list[dict], messages: list[dict]):
        return self.client.messages.create(
            model=self.model, max_tokens=16000, tools=tools, messages=messages,
            system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
            extra_body={"output_config": {"effort": "medium"}})  # no temperature/top_p/budget_tokens on these models


def default_llm():
    """A ClaudeLLM when configured, else None (the scripted agent)."""
    if env("RF_AGENT", "auto") == "scripted":
        return None
    try:
        env("ANTHROPIC_API_KEY")
    except KeyError:
        return None
    return ClaudeLLM()


def pay_date() -> date:
    return date.fromisoformat(seed.load()["pay_date"])


def _observation(tb: ToolBox) -> str:
    return json.dumps({"employer": tb.tenant, "run": tb._get_run(), "new_documents": len(
        [d for d in inbox.all_docs(tb.tenant) if d.id not in inbox.seen_ids(tb.o.L, tb.tenant)])}, default=str)


def _claude(tb: ToolBox, llm, res: TickResult) -> bool:
    """True when the model ran to the end (finish_tick or not). False = use the scripted agent instead."""
    msgs: list[dict] = [{"role": "user", "content": _observation(tb) + "\nHandle this employer's payroll run now."}]
    errors = 0
    for _ in range(MAX_MODEL_CALLS):
        try:
            r = llm.create(prompts.SYSTEM, prompts.TOOLS, msgs)
        except getattr(llm, "errors", ()) as e:
            errors += 1
            res.note = f"api error: {type(e).__name__}"
            if errors >= 2:
                return False
            continue
        if r.stop_reason == "refusal":
            res.note = "model refused"
            return False
        if r.stop_reason == "max_tokens":
            res.note = "max_tokens: no partial tools run"
            return False
        msgs.append({"role": "assistant", "content": r.content})  # append-only, thinking blocks included
        uses = [b for b in r.content if b.type == "tool_use"]
        if r.stop_reason == "pause_turn" or not uses:
            if r.stop_reason == "pause_turn":
                continue
            return True  # no finish_tick: run_tick writes the generic note
        results = []
        for i, b in enumerate(uses):
            text, err = ("TOO_MANY_CALLS: at most 6 tool calls per turn", True) if i >= MAX_TOOLS_PER_TURN \
                else tb.dispatch(b.name, b.input)
            res.calls.append({"tool": b.name, "ok": not err, "result": text[:160]})
            results.append({"type": "tool_result", "tool_use_id": b.id, "content": text, **({"is_error": True} if err else {})})
        msgs.append({"role": "user", "content": results})
        if tb.finished:
            return True
    return True


def run_tick(orch: Orchestrator, tenant: str, llm=None, mode: str | None = None) -> TickResult:
    """Harness first (create the run from the code-parsed timesheet), then the agent."""
    llm = llm if llm is not None else (None if mode == "scripted" else default_llm())
    rid = orch.run_id(pay_date())
    if store.get_run(orch.L, rid, tenant) is None:
        try:
            orch.create_run(tenant, pay_date())
        except (inbox.TimesheetError, KeyError, OSError) as e:
            orch.L.append("ALERT", {"kind": "timesheet_rejected", "detail": str(e)[:200]}, None, tenant)
            return TickResult(tenant, None, "offline agent", f"{tenant.title()}: timesheet rejected",
                              "The timesheet did not pass the strict check, so no run was created.", "HOLD")
    tb = ToolBox(orch, tenant, rid)
    res = TickResult(tenant, rid, "claude" if llm else "offline agent")
    if llm is None or not _claude(tb, llm, res):
        if llm is not None:  # fell back mid-tick: restart the tick with the rules; tools are idempotent
            res.mode, tb.finished = "offline agent", None
        scripted.run(tb)
    if tb.finished is None:  # a tick without finish_tick still leaves a trace
        tb.finished = {"headline": f"{tenant.title()}: tick ended", "explanation": "The agent did not finish its note.",
                       "next_step": "HOLD"}
        tb._note(kind="finish_tick", generic=True, **tb.finished)
    res.headline, res.explanation, res.next_step = tb.finished.values()
    res.flagged = sorted(tb.flagged)
    orch.L.append("AGENT_NOTE", {"kind": "tick", "mode": res.mode, "tool_calls": len(res.calls), "note": res.note},
                  rid, tenant)
    return res
