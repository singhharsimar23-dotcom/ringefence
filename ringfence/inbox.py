"""Timesheet intake. Documents are UNTRUSTED: code parses them, the model never sees a number it could change.

Only a strict `contractor_id,hours` table is accepted. Unknown contractors, bad numbers, duplicates and anything
outside 0 < hours <= 80 (2 dp) are rejected and reported; text outside the table is ignored.
"""
from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path

from . import seed
from .config import demo_dir, var_dir
from .money import MoneyError, parse_amount

INBOX = demo_dir() / "inbox"  # constants so tests can monkeypatch them; a world sets RF_DEMO before start
HISTORY = demo_dir() / "history"


class TimesheetError(ValueError):
    pass


def parse_timesheet(tenant: str, text: str) -> dict[str, Decimal]:
    known = seed.contractors(tenant)
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or [h.strip().lower() for h in rows[0]] != ["contractor_id", "hours"]:
        raise TimesheetError("header must be exactly: contractor_id,hours")
    out: dict[str, Decimal] = {}
    for n, row in enumerate(rows[1:], start=2):
        if not row:
            continue
        if len(row) != 2:
            raise TimesheetError(f"line {n}: expected 2 columns")
        cid, raw = row[0].strip(), row[1].strip()
        if cid not in known:
            raise TimesheetError(f"line {n}: {cid!r} is not a contractor of {tenant}")
        if cid in out:
            raise TimesheetError(f"line {n}: duplicate {cid}")
        try:
            h = parse_amount(raw)
        except (MoneyError, TypeError):
            raise TimesheetError(f"line {n}: bad hours {raw!r}") from None
        if not 0 < h <= 80 or h != h.quantize(Decimal("0.01")):
            raise TimesheetError(f"line {n}: hours must be 0 < h <= 80 with at most 2 dp")
        out[cid] = h
    if not out:
        raise TimesheetError("no timesheet rows")
    return out


def load_timesheet(tenant: str) -> dict[str, Decimal]:
    return parse_timesheet(tenant, (INBOX / f"{tenant}_timesheet.csv").read_text(encoding="utf-8"))


def history(tenant: str) -> dict[str, Decimal]:
    """Last run's amount per contractor, for the approval diff and the auto-release rule."""
    p = HISTORY / f"{tenant}.json"
    return {k: Decimal(v) for k, v in json.loads(p.read_text(encoding="utf-8")).items()} if p.exists() else {}


def diff_flags(tenant: str, amounts: dict[str, Decimal]) -> tuple[bool, bool]:
    """(diff_empty, any_new_or_changed): identical to last run / a contractor not seen before."""
    last = history(tenant)
    return amounts == last, any(c not in last for c in amounts)


# -- documents the agent reads (all UNTRUSTED text) ---------------------------------------------------
@dataclass(frozen=True)
class Doc:
    id: str
    source: str
    text: str


def drop_dir(tenant: str) -> Path:
    p = var_dir() / "inbox" / tenant
    p.mkdir(parents=True, exist_ok=True)
    return p


def all_docs(tenant: str) -> list[Doc]:
    """The baseline timesheet plus anything dropped at runtime (a scenario, or a real mail bridge)."""
    docs = [Doc(f"ts-{tenant}", "timesheet", (INBOX / f"{tenant}_timesheet.csv").read_text(encoding="utf-8"))]
    docs += [Doc(f.stem, "email", f.read_text(encoding="utf-8")[:4000]) for f in sorted(drop_dir(tenant).glob("*.txt"))]
    return docs


def seen_ids(L, tenant: str) -> set[str]:
    return {e["payload"]["read_doc"] for e in L.entries(tenant=tenant, kind="AGENT_NOTE") if "read_doc" in e["payload"]}
