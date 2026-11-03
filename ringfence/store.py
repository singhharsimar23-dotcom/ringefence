"""Thin accessors over the mutable state tables (runs, lines, mandates, approvals).

Reads take a Ledger or a Tx; writes take a Tx so every state change shares a transaction with its ledger append.
`data` columns hold JSON; a few hot fields (attempt, round, request_id) are real columns.
"""
from __future__ import annotations

import json
from typing import Any

from .mandate import Approval, SignedMandate

LINE_COLS = {"attempt", "round", "request_id"}


def _rows(db, sql: str, args: tuple | list = ()) -> list:
    return db.query(sql, args) if hasattr(db, "query") else db.execute(sql, args).fetchall()


# -- runs --------------------------------------------------------------------------------------
def _run(r) -> dict:
    return {**json.loads(r["data"]), "run_id": r["run_id"], "tenant": r["tenant"], "state": r["state"],
            "round": r["round"]}


def get_run(db, run_id: str, tenant: str) -> dict | None:
    r = _rows(db, "SELECT * FROM runs WHERE run_id=? AND tenant=?", (run_id, tenant))
    return _run(r[0]) if r else None


def runs_in(db, states: tuple[str, ...]) -> list[dict]:
    q = ",".join("?" * len(states))
    return [_run(r) for r in _rows(db, f"SELECT * FROM runs WHERE state IN ({q}) ORDER BY run_id, tenant", states)]


def put_run(tx, run_id: str, tenant: str, state: str, round: int = 1, **data: Any) -> None:
    tx.execute("INSERT OR REPLACE INTO runs(run_id, tenant, state, round, data) VALUES(?,?,?,?,?)",
               (run_id, tenant, state, round, json.dumps(data, default=str)))


def set_run(tx, run_id: str, tenant: str, state: str | None = None, round: int | None = None, **data: Any) -> dict:
    cur = get_run(tx, run_id, tenant)
    if cur is None:
        raise KeyError(f"no run {run_id}/{tenant}")
    for k in ("run_id", "tenant", "state", "round"):
        cur.pop(k)
    cur.update(data)
    tx.execute("UPDATE runs SET state=COALESCE(?, state), round=COALESCE(?, round), data=? WHERE run_id=? AND tenant=?",
               (state, round, json.dumps(cur, default=str), run_id, tenant))
    return get_run(tx, run_id, tenant)  # type: ignore[return-value]


# -- lines -------------------------------------------------------------------------------------
def _line(r) -> dict:
    return {**json.loads(r["data"]), "run_id": r["run_id"], "tenant": r["tenant"],
            "contractor_id": r["contractor_id"], "attempt": r["attempt"], "round": r["round"],
            "state": r["state"], "request_id": r["request_id"]}


def get_lines(db, run_id: str, tenant: str, round: int | None = None,
              states: tuple[str, ...] | None = None) -> list[dict]:
    sql, args = "SELECT * FROM lines WHERE run_id=? AND tenant=?", [run_id, tenant]
    if round is not None:
        sql, args = sql + " AND round=?", args + [round]
    if states:
        sql, args = sql + f" AND state IN ({','.join('?' * len(states))})", args + list(states)
    return [_line(r) for r in _rows(db, sql + " ORDER BY contractor_id", args)]


def get_line(db, run_id: str, tenant: str, cid: str) -> dict | None:
    r = _rows(db, "SELECT * FROM lines WHERE run_id=? AND tenant=? AND contractor_id=?", (run_id, tenant, cid))
    return _line(r[0]) if r else None


def lines_in_states(db, states: tuple[str, ...]) -> list[dict]:
    q = ",".join("?" * len(states))
    return [_line(r) for r in _rows(db, f"SELECT * FROM lines WHERE state IN ({q}) ORDER BY run_id, tenant, contractor_id", states)]


def put_line(tx, run_id: str, tenant: str, cid: str, state: str, attempt: int = 1, round: int = 1,
             request_id: str | None = None, **data: Any) -> None:
    tx.execute("INSERT OR REPLACE INTO lines(run_id, tenant, contractor_id, attempt, round, state, request_id, data)"
               " VALUES(?,?,?,?,?,?,?,?)",
               (run_id, tenant, cid, attempt, round, state, request_id, json.dumps(data, default=str)))


def set_line(tx, run_id: str, tenant: str, cid: str, state: str | None = None, **fields: Any) -> None:
    cur = get_line(tx, run_id, tenant, cid)
    if cur is None:
        raise KeyError(f"no line {run_id}/{tenant}/{cid}")
    cols = {k: fields.pop(k) for k in list(fields) if k in LINE_COLS}
    for k in ("run_id", "tenant", "contractor_id", "state", *LINE_COLS):
        cur.pop(k)
    cur.update(fields)
    tx.execute("UPDATE lines SET state=COALESCE(?, state), attempt=COALESCE(?, attempt), round=COALESCE(?, round),"
               " request_id=COALESCE(?, request_id), data=? WHERE run_id=? AND tenant=? AND contractor_id=?",
               (state, cols.get("attempt"), cols.get("round"), cols.get("request_id"),
                json.dumps(cur, default=str), run_id, tenant, cid))


# -- mandates and approvals ----------------------------------------------------------------------
def save_mandate(tx, sm: SignedMandate) -> None:
    tx.execute("INSERT OR REPLACE INTO mandates(tenant, version, data) VALUES(?,?,?)",
               (sm.mandate.tenant, sm.mandate.version, json.dumps(sm.to_dict())))


def latest_mandate(db, tenant: str) -> SignedMandate | None:
    r = _rows(db, "SELECT data FROM mandates WHERE tenant=? ORDER BY version DESC LIMIT 1", (tenant,))
    return SignedMandate.from_dict(json.loads(r[0]["data"])) if r else None


def save_approval(tx, a: Approval) -> None:
    tx.execute("INSERT OR REPLACE INTO approvals(run_id, tenant, round, batch_hash, data) VALUES(?,?,?,?,?)",
               (a.run_id, a.tenant, a.round, a.batch_hash, json.dumps(a.to_dict())))


def get_approval(db, run_id: str, tenant: str, round: int) -> Approval | None:
    r = _rows(db, "SELECT data FROM approvals WHERE run_id=? AND tenant=? AND round=?", (run_id, tenant, round))
    return Approval.from_dict(json.loads(r[0]["data"])) if r else None
