"""Exactly-once payout executor (BUILD_SPEC 4.5).

Rules that carry the guarantee:
- every line's request_id is minted once (mandate.make_request_id), stored, and reused for every retry;
- INTENT is committed BEFORE the HTTP call, and no transaction is ever open across an HTTP call;
- a timeout / 5xx never retries the POST: it looks the transfer up by request_id (GET only);
- duplicate_request_id means "already created": GET the original, verify it, adopt it;
- recover() and poll_inflight() are GET-only; only release(), behind the gate, can create money.
"""
from __future__ import annotations

import time
from collections.abc import Callable
from decimal import Decimal

from . import beneficiaries as ben
from . import fees, fx, seed, store
from .awx import Awx, AwxError, AwxTimeout, TenantClient
from .config import clock
from .gate import Allow, LineFact, ReleaseFacts, check_release
from .ledger import Ledger
from .mandate import LineSpec, batch_hash, make_request_id
from .money import FEE_PER_PAYOUT, SWIFT_FEE, price_line, q

REASON = "professional_business_services"
BACKOFF = (1, 2, 4, 8)
FUNDS_CODES = ("balance_insufficient", "insufficient_funds")

# line-state rank: a status may only move forward (PAID -> FAILED is the one real regression)
RANK = {"PLANNED": 0, "READY": 1, "INTENT": 2, "SUBMITTED": 3, "UNKNOWN": 3, "IN_APPROVAL": 4,
        "SCHEDULED": 4, "OVERDUE": 4, "PROCESSING": 5, "SENT": 6, "PAID": 7}
FROM_AWX = {s: s for s in ("IN_APPROVAL", "SCHEDULED", "OVERDUE", "PROCESSING", "SENT", "PAID", "FAILED")}
FROM_AWX["CANCELLED"] = "FAILED"  # both mean "did not complete"
INFLIGHT = ("SUBMITTED", "IN_APPROVAL", "SCHEDULED", "OVERDUE", "PROCESSING", "SENT")

# what a gate denial does to the run (the lines go back to PLANNED so nothing half-READY lingers)
DENY_TO = {"INSUFFICIENT_OWN_FUNDS": "AWAITING_FUNDS", "APPROVAL_MISSING": "AWAITING_APPROVAL",
           "APPROVAL_HASH_MISMATCH": "AWAITING_APPROVAL", "APPROVAL_EXPIRED": "AWAITING_APPROVAL",
           "APPROVER_NOT_AUTHORISED": "AWAITING_APPROVAL", "SOD_VIOLATION": "AWAITING_APPROVAL",
           "FX_RATE_OUT_OF_BAND": "AWAITING_APPROVAL"}


def line_specs(lines: list[dict]) -> list[LineSpec]:
    return [LineSpec(ln["contractor_id"], ln["beneficiary_id"], Decimal(ln["amount"]), ln["currency"],
                     ln["method"], ln["currency"], ln["attempt"], ln["request_id"]) for ln in lines]


def current_batch_hash(db, run_id: str, tenant: str, round: int) -> str:
    """What an approval binds: every line of this round, incl. its stored request_id."""
    return batch_hash(run_id, tenant, round, line_specs(store.get_lines(db, run_id, tenant, round=round)))


def reference(run_id: str, tenant: str) -> str:
    return f"RF {tenant[:3].upper()} {run_id[-4:].upper()}"  # <= 18 chars of [A-Z0-9 ]


class Executor:
    def __init__(self, awx: Awx, ledger: Ledger, sleep: Callable[[float], None] = time.sleep,
                 on_done: Callable[[str, str], None] | None = None):
        self.awx, self.L, self._sleep, self.on_done = awx, ledger, sleep, on_done

    # ---------------------------------------------------------------------------------------------
    # release
    # ---------------------------------------------------------------------------------------------
    def release(self, run_id: str, tenant: str) -> str:
        """Returns the run state afterwards. Anything but READY is a no-op (double-click safe)."""
        with self.L.tx() as tx:  # the lock: compare-and-set READY -> RELEASING
            run = store.get_run(tx, run_id, tenant)
            if run is None:
                return "NOT_FOUND"
            if run["state"] != "READY":
                return run["state"]
            run = store.set_run(tx, run_id, tenant, state="RELEASING")
            tx.append("RUN_FROZEN", {"round": run["round"]}, run_id, tenant)
        c = self.awx.for_tenant(tenant)  # the binding is the harness's choice, not the model's
        batch = store.get_lines(self.L, run_id, tenant, round=run["round"])
        ready = [ln for ln in batch if ln["state"] == "READY"]
        try:
            facts, legs = self._facts(c, run, ready)
        except (AwxError, AwxTimeout) as e:
            return self._stop(run_id, tenant, "HELD", "FACTS_UNAVAILABLE", f"could not read balances: {e}")
        d = check_release(facts)
        if not isinstance(d, Allow):
            self.L.append("GATE_DENY", {"code": d.code, "detail": d.detail, "round": run["round"]}, run_id, tenant)
            return self._stop(run_id, tenant, DENY_TO.get(d.code, "HELD"), d.code, d.detail)
        self.L.append("GATE_ALLOW", {"round": run["round"], "lines": len(ready), "flags": list(d.flags)},
                      run_id, tenant)
        for leg in legs:
            if (why := self._convert(c, run, leg)) is not None:
                return self._stop(run_id, tenant, "HELD", "FX_FAILED", why)
        for ln in ready:
            stop = self._guard_and_intend(run_id, tenant, ln["contractor_id"])
            if stop:
                return stop
            self._submit(c, store.get_line(self.L, run_id, tenant, ln["contractor_id"]))
            if store.get_run(self.L, run_id, tenant)["state"] == "AWAITING_FUNDS":  # funds rejected mid-batch
                return self._stop(run_id, tenant, "AWAITING_FUNDS", "INSUFFICIENT_OWN_FUNDS")
        with self.L.tx() as tx:
            cur = store.get_run(tx, run_id, tenant)
            if cur["state"] == "RELEASING":
                store.set_run(tx, run_id, tenant, state="RELEASED")
        self._maybe_done(run_id, tenant)
        return store.get_run(self.L, run_id, tenant)["state"]

    def _stop(self, run_id: str, tenant: str, state: str, code: str, detail: str = "") -> str:
        """Leave RELEASING for `state`; lines that never reached INTENT go back to PLANNED."""
        with self.L.tx() as tx:
            run = store.get_run(tx, run_id, tenant)
            for ln in store.get_lines(tx, run_id, tenant, round=run["round"], states=("READY",)):
                store.set_line(tx, run_id, tenant, ln["contractor_id"], "PLANNED")
            store.set_run(tx, run_id, tenant, state=state, hold_reason=code)
            if state == "HELD":
                tx.append("HOLD", {"code": code, "detail": detail}, run_id, tenant)
        return state

    def _guard_and_intend(self, run_id: str, tenant: str, cid: str) -> str | None:
        """One tx: re-check kill switch and approval expiry, then write INTENT. None = go ahead."""
        with self.L.tx() as tx:
            if self.L.kill_switch_on():
                stop = ("HELD", "KILL_SWITCH")
            else:
                run = store.get_run(tx, run_id, tenant)
                ap = store.get_approval(tx, run_id, tenant, run["round"])
                stop = ("AWAITING_APPROVAL", "APPROVAL_EXPIRED") if ap and ap.expires_at <= clock.utc_now() else None
            if stop is None:
                ln = store.get_line(tx, run_id, tenant, cid)
                tx.append("INTENT", {"contractor_id": cid, "request_id": ln["request_id"], "amount": ln["amount"],
                                     "currency": ln["currency"], "attempt": ln["attempt"]}, run_id, tenant)
                store.set_line(tx, run_id, tenant, cid, "INTENT")
                return None
        return self._stop(run_id, tenant, stop[0], stop[1])

    # -- facts (built by code, from this tenant's own data) ---------------------------------------
    def _facts(self, c: TenantClient, run: dict, ready: list[dict]):
        run_id, tenant = run["run_id"], run["tenant"]
        reg, contractors = ben.load_registry(), seed.contractors(tenant)
        lines = []
        for ln in ready:
            cid, bid = ln["contractor_id"], ln["beneficiary_id"]
            resolved, key = ben.resolve(reg, tenant, cid), ""
            try:  # the REAL destination account, read with this tenant's token
                key = ben.bank_key(c.get(f"/beneficiaries/{bid}")["beneficiary"]["bank_details"])
            except AwxError:
                resolved = None  # not a beneficiary of this tenant: the gate denies
            k = contractors.get(cid)
            expected = price_line(k, Decimal(ln["hours"])).amount if k else None
            quarantined = bool(self.L.query("SELECT 1 FROM quarantine WHERE tenant=? AND contractor_id=?"
                                            " AND status='ACTIVE'", (tenant, cid)))
            lines.append(LineFact(cid, tenant, bid, Decimal(ln["amount"]), ln["currency"], ln["state"], resolved,
                                  expected, key, quarantined))
        mandate = store.latest_mandate(self.L, tenant)
        totals: dict[str, Decimal] = {}
        for ln in lines:
            totals[ln.currency] = totals.get(ln.currency, Decimal(0)) + ln.amount
        fees: dict[str, Decimal] = {}
        for ln in ready:
            if ln["method"] == "SWIFT":
                fees[SWIFT_FEE[0]] = fees.get(SWIFT_FEE[0], Decimal(0)) + SWIFT_FEE[1]
        if ready:
            fees["GBP"] = fees.get("GBP", Decimal(0)) + q(FEE_PER_PAYOUT * len(ready), "GBP")
        need = dict(totals)
        for k2, v in fees.items():
            need[k2] = need.get(k2, Decimal(0)) + v
        avail = c.balances()  # this tenant's own balances; never summed across tenants
        legs = fx.plan(c, mandate.mandate, need, avail) if mandate else []
        undebited: dict[str, Decimal] = {}  # other OVERDUE transfers of this tenant are not debited yet
        for o in store.lines_in_states(self.L, ("OVERDUE",)):
            if o["tenant"] == tenant:
                undebited[o["currency"]] = undebited.get(o["currency"], Decimal(0)) + Decimal(o["amount"])
        facts = ReleaseFacts(
            run_id=run_id, run_tenant=tenant, token_tenant=c.tenant_key, round=run["round"],
            kill_switch=self.L.kill_switch_on(), holds_lock=run["state"] == "RELEASING", now=clock.utc_now(),
            mandate=mandate, lines=tuple(lines), tenant_ga_keys=frozenset(ben.all_ga_keys(reg)), avail=avail,
            fees_need=fees, fx_buy={g.buy: g.quote.buy_amount for g in legs},
            fx_sell={g.sell: g.quote.sell_amount for g in legs}, undebited_inflight=undebited,
            approval=store.get_approval(self.L, run_id, tenant, run["round"]),
            expected_batch_hash=current_batch_hash(self.L, run_id, tenant, run["round"]),
            beneficiary_editors=frozenset(run.get("beneficiary_editors", [])),
            diff_empty=bool(run.get("diff_empty", False)), any_new_or_changed=bool(run.get("any_new_or_changed", True)),
            fx_used=bool(legs),
            live_fx_rate=legs[0].quote.rate if legs else None)  # shortcut: one rate is compared, first leg
        return facts, legs

    def _convert(self, c: TenantClient, run: dict, leg: fx.Leg) -> str | None:
        """None = converted (or already was). A string = why the run must stop."""
        rid = fx.leg_request_id(run["run_id"], run["tenant"], leg, run["round"])
        self.L.append("FX_QUOTE", {"sell": leg.sell, "buy": leg.buy, "rate": str(leg.quote.rate),
                                   "sell_amount": str(leg.quote.sell_amount), "buy_amount": str(leg.quote.buy_amount),
                                   "request_id": rid}, run["run_id"], run["tenant"])
        try:
            r = fx.convert(c, rid, leg.quote, by="buy")
        except AwxError as e:
            if e.code != "duplicate_request_id":
                return f"{e.code}: {e.message}"
            r = {"duplicate": True}  # the same (run, tenant, currency, round) was already converted
        except AwxTimeout:
            return "conversion outcome unknown; release again (same request_id) is safe"
        self.L.append("FX_CONVERTED", {"request_id": rid, "conversion_id": r.get("conversion_id"),
                                       "duplicate": bool(r.get("duplicate"))}, run["run_id"], run["tenant"])
        return None

    # ---------------------------------------------------------------------------------------------
    # one transfer
    # ---------------------------------------------------------------------------------------------
    def _body(self, ln: dict) -> dict:
        return {"request_id": ln["request_id"], "beneficiary_id": ln["beneficiary_id"],
                "transfer_amount": Decimal(ln["amount"]), "transfer_currency": ln["currency"],
                "source_currency": ln["currency"], "transfer_method": ln["method"], "reason": REASON,
                "reference": reference(ln["run_id"], ln["tenant"])}

    def _submit(self, c: TenantClient, ln: dict, again: bool = True) -> None:
        try:
            t = c.post_money("/transfers/create", self._body(ln))
        except AwxTimeout:
            return self._unknown(ln, again)
        except AwxError as e:
            if e.code == "duplicate_request_id":
                return self._adopt(c, ln, e)
            if e.status >= 500:
                return self._unknown(ln, again)
            funds = e.code in FUNDS_CODES
            with self.L.tx() as tx:
                store.set_line(tx, ln["run_id"], ln["tenant"], ln["contractor_id"], "FAILED_TO_SUBMIT", error=e.code)
                tx.append("STATUS", {"contractor_id": ln["contractor_id"], "state": "FAILED_TO_SUBMIT",
                                     "code": e.code, "detail": e.message, "request_id": ln["request_id"]},
                          ln["run_id"], ln["tenant"])
                if funds:
                    store.set_run(tx, ln["run_id"], ln["tenant"], state="AWAITING_FUNDS")
            return None
        return self._apply(ln, t, "SUBMITTED")

    def _unknown(self, ln: dict, again: bool) -> None:
        with self.L.tx() as tx:
            store.set_line(tx, ln["run_id"], ln["tenant"], ln["contractor_id"], "UNKNOWN")
            tx.append("UNKNOWN", {"contractor_id": ln["contractor_id"], "request_id": ln["request_id"]},
                      ln["run_id"], ln["tenant"])
        self.reconcile_line(ln["run_id"], ln["tenant"], ln["contractor_id"], again=again)

    def _adopt(self, c: TenantClient, ln: dict, e: AwxError) -> None:
        """duplicate_request_id: the transfer exists. Adopt it only if it is exactly this line."""
        try:
            tid = (e.details or {}).get("id")
            t = c.get(f"/transfers/{tid}") if tid else c.transfer_by_request(ln["request_id"])
        except (AwxError, AwxTimeout):
            t = None
        ok = (t is not None and t.get("beneficiary_id") == ln["beneficiary_id"]
              and Decimal(t["transfer_amount"]) == Decimal(ln["amount"]) and t["transfer_currency"] == ln["currency"])
        if not ok:
            self._hold(ln, "HOLD", "DUPLICATE_MISMATCH", "an existing transfer holds this request_id but differs")
            self.L.append("ALERT", {"what": "DUPLICATE_MISMATCH", "request_id": ln["request_id"]},
                          ln["run_id"], ln["tenant"])
            return
        self._apply(ln, t, "RECONCILED")

    def _hold(self, ln: dict, state: str, code: str, detail: str = "") -> None:
        with self.L.tx() as tx:
            store.set_line(tx, ln["run_id"], ln["tenant"], ln["contractor_id"], state, hold_reason=code)
            tx.append("HOLD", {"contractor_id": ln["contractor_id"], "code": code, "detail": detail,
                               "request_id": ln["request_id"]}, ln["run_id"], ln["tenant"])

    def reconcile_line(self, run_id: str, tenant: str, cid: str, again: bool = True) -> str:
        """UNKNOWN -> its real status, by request_id. GET-only until a re-create with the SAME stored id
        (duplicate guard makes that safe). Never mints a new id. Returns the line state."""
        c = self.awx.for_tenant(tenant)
        ln = store.get_line(self.L, run_id, tenant, cid)
        for i, delay in enumerate(BACKOFF):
            try:
                t = c.transfer_by_request(ln["request_id"])
            except (AwxError, AwxTimeout):
                t = None
            if t is not None:
                self._apply(ln, t, "RECONCILED")
                return store.get_line(self.L, run_id, tenant, cid)["state"]
            if i < len(BACKOFF) - 1:
                self._sleep(delay)
        if again and not self.L.kill_switch_on():
            self._submit(c, ln, again=False)  # not found anywhere: the create never landed
            return store.get_line(self.L, run_id, tenant, cid)["state"]
        if not again:
            self._hold(ln, "HOLD_UNKNOWN", "UNKNOWN_AFTER_RETRY", "outcome still unknown after backoff and one re-create")
            self.L.append("ALERT", {"what": "HOLD_UNKNOWN", "request_id": ln["request_id"]}, run_id, tenant)
        return "UNKNOWN"  # kill switch on: stay UNKNOWN

    # ---------------------------------------------------------------------------------------------
    # status
    # ---------------------------------------------------------------------------------------------
    def _apply(self, ln: dict, t: dict, kind: str) -> None:
        run_id, tenant, cid = ln["run_id"], ln["tenant"], ln["contractor_id"]
        awx_status = t.get("status")
        new = FROM_AWX.get(awx_status)
        if new is None:
            return self._hold(ln, "HOLD", "UNKNOWN_STATUS", str(awx_status))
        old = ln["state"]
        extra = {"transfer_id": t["id"], "awx_status": awx_status}
        if new == "FAILED":
            state = "RETURNED" if old == "PAID" else "FAILED"
            extra |= {"failure_type": t.get("failure_type"), "failure_reason": t.get("failure_reason")}
        elif old == "PAID" or RANK[new] < RANK.get(old, 0) or (new == old and kind == "STATUS"):
            return None  # never move backwards; PAID never un-pays except via FAILED above
        else:
            state = new
        with self.L.tx() as tx:
            store.set_line(tx, run_id, tenant, cid, state, **extra)
            tx.append(kind,
                      {"contractor_id": cid, "state": state, "awx_status": awx_status, "transfer_id": t["id"],
                       "request_id": ln["request_id"], "failure_type": t.get("failure_type")}, run_id, tenant)
        if state in ("FAILED", "RETURNED"):
            if state == "RETURNED":
                fees.note_return(self.L, run_id, tenant)
            self._reopen(run_id, tenant, cid)
        return None

    def _reopen(self, run_id: str, tenant: str, cid: str) -> None:
        """Only after a fresh GET of attempt N shows FAILED/CANCELLED. attempt+1, new request_id, new approval."""
        c = self.awx.for_tenant(tenant)
        ln = store.get_line(self.L, run_id, tenant, cid)
        try:
            t = c.get(f"/transfers/{ln['transfer_id']}")
        except (AwxError, AwxTimeout):
            return
        if t.get("status") not in ("FAILED", "CANCELLED"):
            return
        with self.L.tx() as tx:
            run = store.get_run(tx, run_id, tenant)
            rnd = run["round"] + 1 if ln["round"] == run["round"] else run["round"]
            attempt = ln["attempt"] + 1
            rid = make_request_id(run_id, tenant, cid, attempt)
            store.set_line(tx, run_id, tenant, cid, "PLANNED", attempt=attempt, round=rnd, request_id=rid,
                           prev_transfer_id=ln["transfer_id"], transfer_id=None, awx_status=None)
            store.set_run(tx, run_id, tenant, state="AWAITING_APPROVAL", round=rnd)
            tx.append("REOPENED", {"contractor_id": cid, "attempt": attempt, "round": rnd, "request_id": rid,
                                   "prev_transfer_id": ln["transfer_id"], "failure_type": t.get("failure_type"),
                                   "failure_reason": t.get("failure_reason")}, run_id, tenant)

    def _maybe_done(self, run_id: str, tenant: str) -> None:
        with self.L.tx() as tx:
            run = store.get_run(tx, run_id, tenant)
            lines = store.get_lines(tx, run_id, tenant)
            if run["state"] != "RELEASED" or not lines or any(ln["state"] != "PAID" for ln in lines):
                return
            store.set_run(tx, run_id, tenant, state="DONE")
            tx.append("STATUS", {"run": "DONE", "round": run["round"]}, run_id, tenant)
        if self.on_done:
            self.on_done(run_id, tenant)

    # ---------------------------------------------------------------------------------------------
    # background
    # ---------------------------------------------------------------------------------------------
    def poll_inflight(self) -> None:
        """GET each in-flight transfer by id (and PAID ones of live runs, for late returns); apply forward moves."""
        paid = [ln for ln in store.lines_in_states(self.L, ("PAID",))
                if (store.get_run(self.L, ln["run_id"], ln["tenant"]) or {}).get("state") in ("RELEASED", "DONE")]
        # shortcut: PAID lines are polled for as long as their run lives; add an age cut-off at volume
        for ln in [*store.lines_in_states(self.L, INFLIGHT), *paid]:
            if not ln.get("transfer_id"):
                continue
            try:
                t = self.awx.for_tenant(ln["tenant"]).get(f"/transfers/{ln['transfer_id']}")
            except (AwxError, AwxTimeout):
                continue
            self._apply(ln, t, "STATUS")
        for run in store.runs_in(self.L, ("RELEASED",)):
            self._maybe_done(run["run_id"], run["tenant"])

    def recover(self) -> None:
        """Startup, GET-only. Look up every INTENT/SUBMITTED/UNKNOWN line by request_id: found -> its status;
        not found -> READY again with the SAME stored request_id (release, behind the gate, may re-send)."""
        for ln in store.lines_in_states(self.L, ("INTENT", "SUBMITTED", "UNKNOWN")):
            try:
                t = self.awx.for_tenant(ln["tenant"]).transfer_by_request(ln["request_id"])
            except (AwxError, AwxTimeout):
                continue
            if t is not None:
                self._apply(ln, t, "RECONCILED")
                continue
            with self.L.tx() as tx:
                store.set_line(tx, ln["run_id"], ln["tenant"], ln["contractor_id"], "READY")
                store.set_run(tx, ln["run_id"], ln["tenant"], state="READY")
                tx.append("STATUS", {"contractor_id": ln["contractor_id"], "state": "READY",
                                     "recovered": "transfer not found; stored request_id kept"},
                          ln["run_id"], ln["tenant"])
        for run in store.runs_in(self.L, ("RELEASING",)):
            with self.L.tx() as tx:
                store.set_run(tx, run["run_id"], run["tenant"], state="READY")
