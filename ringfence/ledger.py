"""SQLite append-only hash-chained ledger plus the mutable state tables.

Rules (BUILD_SPEC 4.4):
- every state change happens in the same transaction as its ledger append (use Ledger.tx());
- never hold a tx open across an HTTP call;
- each thread gets its own connection (WAL, busy_timeout, BEGIN IMMEDIATE for writes);
- UPDATE/DELETE on `ledger` are blocked by triggers; verify() recomputes the whole chain.
"""
from __future__ import annotations

import hashlib
import json
import secrets
import sqlite3
import string
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import clock, var_dir
from .money import canonical_json

GENESIS = "0" * 64

KINDS = {
    "RUN_CREATED", "PRICED", "PROPOSAL", "GATE_DENY", "GATE_ALLOW", "APPROVED", "RUN_FROZEN",
    "INTENT", "SUBMITTED", "STATUS", "UNKNOWN", "RECONCILED", "REOPENED",
    "FX_QUOTE", "FX_CONVERTED", "FUNDING_REQUESTED", "FUNDING_MATCHED",
    "FEE_CHARGED", "FEE_CREDIT", "BENEFICIARY_QUARANTINED", "CALLBACK_CONFIRMED",
    "SIMULATED", "AGENT_NOTE",
    # additions beyond the spec's list (spec 4.4 is not exhaustive for these)
    "KILL_SWITCH", "MANDATE_SIGNED", "RESET", "HOLD", "ALERT", "WEBHOOK",
}

# a payload carrying any of these keys is a bug: secrets must never reach the ledger
_SECRET_KEYS = {"token", "api_key", "x-api-key", "authorization", "password", "secret"}

SCHEMA = """
CREATE TABLE IF NOT EXISTS ledger(
  seq INTEGER PRIMARY KEY, ts TEXT NOT NULL, run_id TEXT, tenant TEXT, kind TEXT NOT NULL,
  payload_json TEXT NOT NULL, prev_hash TEXT NOT NULL, hash TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS ledger_no_update BEFORE UPDATE ON ledger
  BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
CREATE TRIGGER IF NOT EXISTS ledger_no_delete BEFORE DELETE ON ledger
  BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END;
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS runs(
  run_id TEXT NOT NULL, tenant TEXT NOT NULL, state TEXT NOT NULL, round INTEGER NOT NULL DEFAULT 1,
  data TEXT NOT NULL DEFAULT '{}', PRIMARY KEY(run_id, tenant));
CREATE TABLE IF NOT EXISTS lines(
  run_id TEXT NOT NULL, tenant TEXT NOT NULL, contractor_id TEXT NOT NULL,
  attempt INTEGER NOT NULL DEFAULT 1, round INTEGER NOT NULL DEFAULT 1, state TEXT NOT NULL,
  request_id TEXT, data TEXT NOT NULL DEFAULT '{}', PRIMARY KEY(run_id, tenant, contractor_id));
CREATE INDEX IF NOT EXISTS lines_req ON lines(request_id);
CREATE TABLE IF NOT EXISTS approvals(
  run_id TEXT NOT NULL, tenant TEXT NOT NULL, round INTEGER NOT NULL, batch_hash TEXT NOT NULL,
  data TEXT NOT NULL, PRIMARY KEY(run_id, tenant, round));
CREATE TABLE IF NOT EXISTS mandates(
  tenant TEXT NOT NULL, version INTEGER NOT NULL, data TEXT NOT NULL, PRIMARY KEY(tenant, version));
CREATE TABLE IF NOT EXISTS beneficiaries(
  tenant TEXT NOT NULL, contractor_id TEXT NOT NULL, beneficiary_id TEXT NOT NULL,
  data TEXT NOT NULL DEFAULT '{}', PRIMARY KEY(tenant, contractor_id));
CREATE TABLE IF NOT EXISTS quarantine(
  id INTEGER PRIMARY KEY AUTOINCREMENT, tenant TEXT NOT NULL, contractor_id TEXT NOT NULL,
  status TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS funding_requests(
  id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, tenant TEXT NOT NULL,
  reference TEXT NOT NULL UNIQUE, status TEXT NOT NULL, data TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS events_seen(event_id TEXT PRIMARY KEY, ts TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS kill_switch(
  id INTEGER PRIMARY KEY CHECK(id = 1), on_ INTEGER NOT NULL, by TEXT, ts TEXT);
INSERT OR IGNORE INTO kill_switch(id, on_) VALUES(1, 0);
"""


@dataclass
class VerifyResult:
    ok: bool
    bad_seq: int | None = None
    reason: str = ""
    head_seq: int = 0
    head_hash: str = GENESIS


def entry_hash(prev_hash: str, seq: int, ts: str, run_id: str | None, tenant: str | None,
               kind: str, payload: Any) -> str:
    body = canonical_json({"seq": seq, "ts": ts, "run_id": run_id, "tenant": tenant,
                           "kind": kind, "payload": payload})
    return hashlib.sha256((prev_hash + body).encode()).hexdigest()


def _check_payload(o: Any) -> None:
    if isinstance(o, dict):
        for k, v in o.items():
            if str(k).lower() in _SECRET_KEYS:
                raise ValueError(f"secret-like key in ledger payload: {k}")
            _check_payload(v)
    elif isinstance(o, (list, tuple)):
        for v in o:
            _check_payload(v)


class Tx:
    """Handle inside Ledger.tx(): state-table SQL plus ledger appends, one atomic unit."""

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def execute(self, sql: str, params: tuple | list = ()) -> sqlite3.Cursor:
        return self.conn.execute(sql, params)

    def append(self, kind: str, payload: dict | None = None, run_id: str | None = None,
               tenant: str | None = None) -> int:
        if kind not in KINDS:
            raise ValueError(f"unknown ledger kind {kind}")
        payload = payload or {}
        _check_payload(payload)
        row = self.conn.execute("SELECT seq, hash FROM ledger ORDER BY seq DESC LIMIT 1").fetchone()
        seq, prev = (row["seq"] + 1, row["hash"]) if row else (1, GENESIS)
        ts = clock.utc_now().isoformat()
        pj = canonical_json(payload)
        h = entry_hash(prev, seq, ts, run_id, tenant, kind, json.loads(pj))
        self.conn.execute(
            "INSERT INTO ledger(seq, ts, run_id, tenant, kind, payload_json, prev_hash, hash)"
            " VALUES(?,?,?,?,?,?,?,?)", (seq, ts, run_id, tenant, kind, pj, prev, h))
        return seq


class Ledger:
    def __init__(self, path: str | Path | None = None):
        self.path = str(path or (var_dir() / "ringfence.db"))
        self._local = threading.local()
        with self.tx():
            pass  # create schema eagerly

    # -- connections -------------------------------------------------------------------------
    def conn(self) -> sqlite3.Connection:
        c = getattr(self._local, "conn", None)
        if c is None:
            c = sqlite3.connect(self.path, isolation_level=None, timeout=5.0)
            c.row_factory = sqlite3.Row
            c.execute("PRAGMA busy_timeout=5000")
            c.execute("PRAGMA journal_mode=WAL")
            c.execute("PRAGMA foreign_keys=ON")
            c.executescript(SCHEMA)
            self._local.conn = c
        return c

    @contextmanager
    def tx(self) -> Iterator[Tx]:
        """BEGIN IMMEDIATE ... COMMIT. Re-entrant on one thread (inner joins the outer tx)."""
        outer = getattr(self._local, "tx", None)
        if outer is not None:
            yield outer
            return
        c = self.conn()
        c.execute("BEGIN IMMEDIATE")
        t = self._local.tx = Tx(c)
        try:
            yield t
        except BaseException:
            c.execute("ROLLBACK")
            raise
        else:
            c.execute("COMMIT")
        finally:
            self._local.tx = None

    def append(self, kind: str, payload: dict | None = None, run_id: str | None = None,
               tenant: str | None = None) -> int:
        with self.tx() as t:
            return t.append(kind, payload, run_id, tenant)

    # -- reads -------------------------------------------------------------------------------
    def query(self, sql: str, params: tuple | list = ()) -> list[sqlite3.Row]:
        return self.conn().execute(sql, params).fetchall()

    def entries(self, run_id: str | None = None, kind: str | None = None,
                tenant: str | None = None, after_seq: int = 0) -> list[dict]:
        sql, args = "SELECT * FROM ledger WHERE seq > ?", [after_seq]
        for col, val in (("run_id", run_id), ("kind", kind), ("tenant", tenant)):
            if val is not None:
                sql += f" AND {col} = ?"
                args.append(val)
        out = []
        for r in self.query(sql + " ORDER BY seq", args):
            d = dict(r)
            d["payload"] = json.loads(d.pop("payload_json"))
            out.append(d)
        return out

    def head(self) -> tuple[int, str]:
        r = self.query("SELECT seq, hash FROM ledger ORDER BY seq DESC LIMIT 1")
        return (r[0]["seq"], r[0]["hash"]) if r else (0, GENESIS)

    # -- meta / epoch / kill switch ----------------------------------------------------------
    def epoch(self) -> str:
        """6 random [a-z0-9] chars in run_id and request_ids; regenerated by reset so a second
        demo take never collides with Airwallex's 7-day request_id memory."""
        r = self.query("SELECT value FROM meta WHERE key='epoch'")
        if r:
            return r[0]["value"]
        with self.tx() as t:
            e = "".join(secrets.choice(string.ascii_lowercase + string.digits) for _ in range(6))
            t.execute("INSERT OR IGNORE INTO meta(key, value) VALUES('epoch', ?)", (e,))
            return t.execute("SELECT value FROM meta WHERE key='epoch'").fetchone()["value"]

    def kill_switch_on(self) -> bool:
        return bool(self.query("SELECT on_ FROM kill_switch WHERE id=1")[0]["on_"])

    def set_kill_switch(self, on: bool, by: str) -> None:
        with self.tx() as t:
            t.execute("UPDATE kill_switch SET on_=?, by=?, ts=? WHERE id=1",
                      (int(on), by, clock.utc_now().isoformat()))
            t.append("KILL_SWITCH", {"on": on, "by": by})

    def reset(self, by: str, archive_dir: str | Path | None = None) -> Path:
        """New take: copy the whole DB to var/archive, then start an empty chain whose first row (RESET) records the
        archived head. Needs a trigger drop, so it is an operator action, never reachable from the agent or the API
        beyond the reset button. Returns the archive path."""
        arch = Path(archive_dir or var_dir() / "archive")
        arch.mkdir(parents=True, exist_ok=True)
        dest = arch / f"{clock.utc_now():%Y%m%dT%H%M%S%f}.db"
        seq, head = self.head()
        dst = sqlite3.connect(dest)
        self.conn().backup(dst)
        dst.close()
        with self.tx() as t:
            t.execute("DROP TRIGGER IF EXISTS ledger_no_update")
            t.execute("DROP TRIGGER IF EXISTS ledger_no_delete")
            for tbl in ("ledger", "runs", "lines", "approvals", "mandates", "beneficiaries", "quarantine",
                        "funding_requests", "events_seen", "meta"):
                t.execute(f"DELETE FROM {tbl}")
            t.execute("UPDATE kill_switch SET on_=0, by=NULL, ts=NULL WHERE id=1")
            t.execute("CREATE TRIGGER ledger_no_update BEFORE UPDATE ON ledger "
                      "BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END")
            t.execute("CREATE TRIGGER ledger_no_delete BEFORE DELETE ON ledger "
                      "BEGIN SELECT RAISE(ABORT, 'ledger is append-only'); END")
            t.append("RESET", {"by": by, "archived_as": dest.name, "archived_head": {"seq": seq, "hash": head}})
        return dest

    # -- verification ------------------------------------------------------------------------
    def verify(self, anchor_dir: str | Path | None = None) -> VerifyResult:
        """Recompute the whole chain; then check every certificate head anchor in anchor_dir
        (cert file = {"body": {..., "ledger_head": {"seq", "hash"}}, "signature": ...})."""
        prev, last = GENESIS, 0
        hashes: dict[int, str] = {}
        for r in self.conn().execute("SELECT * FROM ledger ORDER BY seq"):
            seq = r["seq"]
            if seq != last + 1:
                return VerifyResult(False, seq, "sequence gap", last, prev)
            if r["prev_hash"] != prev:
                return VerifyResult(False, seq, "prev_hash mismatch", last, prev)
            want = entry_hash(prev, seq, r["ts"], r["run_id"], r["tenant"], r["kind"],
                              json.loads(r["payload_json"]))
            if r["hash"] != want:
                return VerifyResult(False, seq, "hash mismatch", last, prev)
            hashes[seq] = prev = r["hash"]
            last = seq
        if anchor_dir and Path(anchor_dir).is_dir():
            for f in sorted(Path(anchor_dir).glob("*.json")):
                head = json.loads(f.read_text()).get("body", {}).get("ledger_head")
                if head and hashes.get(head["seq"]) != head["hash"]:
                    return VerifyResult(False, head["seq"], f"anchor mismatch in {f.name}", last, prev)
        return VerifyResult(True, None, "", last, prev)
