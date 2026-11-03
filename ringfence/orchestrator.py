"""Run lifecycle (BUILD_SPEC 4.5a). The ONLY caller of executor.release.

DRAFT -> AWAITING_FUNDS | AWAITING_APPROVAL | READY -> RELEASING -> RELEASED -> DONE.
Code computes every number; the agent (later) can only ask for a run to be created or submitted.
"""
from __future__ import annotations

import threading
from datetime import date, timedelta
from decimal import Decimal

from . import beneficiaries as ben
from . import fees, funding, fx, inbox, seed, store
from .awx import Awx
from .config import clock
from .executor import Executor, current_batch_hash
from .ledger import Ledger
from .mandate import Approval, make_request_id, sign_approval
from .money import price_line, price_run

APPROVAL_TTL = timedelta(hours=2)


class Refused(Exception):
    """An operator action the state machine or a mandate does not allow."""


class Orchestrator:
    def __init__(self, awx: Awx, ledger: Ledger, executor: Executor | None = None):
        self.awx, self.L = awx, ledger
        self.ex = executor or Executor(awx, ledger, on_done=lambda r, t: fees.charge(awx, ledger, r, t))
        self._money = threading.Lock()  # one release at a time; the executor's CAS makes a repeat a no-op anyway

    # -- create ------------------------------------------------------------------------------------
    def run_id(self, pay_date: date) -> str:
        return f"{pay_date:%Y%m%d}-{self.L.epoch()}"

    def ensure_mandates(self) -> None:
        with self.L.tx() as tx:
            for m in seed.default_mandates().values():
                if store.latest_mandate(tx, m.mandate.tenant) is None:
                    store.save_mandate(tx, m)
                    tx.append("MANDATE_SIGNED", {"tenant": m.mandate.tenant, "version": m.mandate.version},
                              None, m.mandate.tenant)

    def create_run(self, tenant: str, pay_date: date, hours: dict[str, Decimal] | None = None) -> str:
        """DRAFT with PLANNED lines. Hours default to this tenant's parsed timesheet; rates come from the registry."""
        self.ensure_mandates()
        hours = hours or inbox.load_timesheet(tenant)
        reg, cs, run_id = ben.load_registry(), seed.contractors(tenant), self.run_id(pay_date)
        priced = {cid: price_line(cs[cid], h) for cid, h in hours.items()}  # KeyError = not this tenant's contractor
        diff_empty, new = inbox.diff_flags(tenant, {k: v.amount for k, v in priced.items()})
        with self.L.tx() as tx:
            if store.get_run(tx, run_id, tenant):
                raise Refused(f"run {run_id} already exists for {tenant}")
            store.put_run(tx, run_id, tenant, "DRAFT", 1, pay_date=pay_date.isoformat(), diff_empty=diff_empty,
                          any_new_or_changed=new)
            for cid, ln in priced.items():
                bid = ben.resolve(reg, tenant, cid)
                if bid is None:
                    raise Refused(f"no beneficiary for {cid} in {tenant}; run setup")
                store.put_line(tx, run_id, tenant, cid, "PLANNED", 1, 1, make_request_id(run_id, tenant, cid, 1),
                               beneficiary_id=bid, amount=str(ln.amount), currency=ln.currency, method=ln.method,
                               hours=str(ln.hours))
            tx.append("RUN_CREATED", {"pay_date": pay_date.isoformat(), "contractors": sorted(priced)}, run_id, tenant)
            tx.append("PRICED", {"lines": {k: {"hours": str(v.hours), "rate": str(v.rate), "amount": str(v.amount),
                                               "currency": v.currency} for k, v in priced.items()}}, run_id, tenant)
        return run_id

    # -- pricing against the tenant's OWN funds -----------------------------------------------------
    def _plan(self, run_id: str, tenant: str):
        """(need, avail, legs, shortfall-after-fx), all from this tenant's own balances."""
        run = store.get_run(self.L, run_id, tenant)
        cs = seed.contractors(tenant)
        batch = store.get_lines(self.L, run_id, tenant, round=run["round"])
        lines = [price_line(cs[ln["contractor_id"]], Decimal(ln["hours"])) for ln in batch]
        c = self.awx.for_tenant(tenant)
        avail = c.balances()
        p = price_run(lines, avail)
        sm = store.latest_mandate(self.L, tenant)
        legs = fx.plan(c, sm.mandate, p.need, avail) if sm else []
        covered = {g.buy: g.quote.buy_amount for g in legs}
        short = {k: v - covered.get(k, Decimal(0)) for k, v in p.shortfall.items()}
        return p, legs, {k: v for k, v in short.items() if v > 0}

    # -- state moves -------------------------------------------------------------------------------
    def submit(self, run_id: str, tenant: str) -> str:
        """DRAFT -> AWAITING_FUNDS (own shortfall) | READY (auto-release eligible) | AWAITING_APPROVAL."""
        run = store.get_run(self.L, run_id, tenant)
        if run is None or run["state"] != "DRAFT":
            raise Refused(f"{run_id}/{tenant} is {run['state'] if run else 'missing'}, not DRAFT")
        return self._after_pricing(run_id, tenant)

    def _after_pricing(self, run_id: str, tenant: str) -> str:
        run = store.get_run(self.L, run_id, tenant)
        _, _, short = self._plan(run_id, tenant)
        if short:
            for ccy, amt in short.items():
                funding.request_funding(self.awx, self.L, run_id, tenant, ccy, amt,
                                        date.fromisoformat(run["pay_date"]))
            with self.L.tx() as tx:
                store.set_run(tx, run_id, tenant, state="AWAITING_FUNDS", shortfall={k: str(v) for k, v in short.items()})
            return "AWAITING_FUNDS"
        sm = store.latest_mandate(self.L, tenant)
        if sm and sm.mandate.auto_release == "if_no_diff" and run["diff_empty"] and not run["any_new_or_changed"]:
            with self.L.tx() as tx:
                tx.append("APPROVED", {"auto_release": True, "rule": "mandate auto_release if_no_diff, no changes"},
                          run_id, tenant)
                self._mark_ready(tx, run_id, tenant)
            return "READY"
        with self.L.tx() as tx:
            store.set_run(tx, run_id, tenant, state="AWAITING_APPROVAL", shortfall={})
        return "AWAITING_APPROVAL"

    def _mark_ready(self, tx, run_id: str, tenant: str) -> None:
        run = store.get_run(tx, run_id, tenant)
        for ln in store.get_lines(tx, run_id, tenant, round=run["round"], states=("PLANNED",)):
            store.set_line(tx, run_id, tenant, ln["contractor_id"], "READY")
        store.set_run(tx, run_id, tenant, state="READY")

    def approve(self, run_id: str, tenant: str, approver_id: str, role: str) -> str:
        """Binds the approval to this exact batch (every line + request_id) and, if FX is needed, to its rate."""
        run = store.get_run(self.L, run_id, tenant)
        if run is None or run["state"] != "AWAITING_APPROVAL":
            raise Refused(f"{run_id}/{tenant} is {run['state'] if run else 'missing'}, not AWAITING_APPROVAL")
        sm = store.latest_mandate(self.L, tenant)
        if role != sm.mandate.approver_role:
            raise Refused(f"{approver_id} ({role}) may not approve {tenant}; needs {sm.mandate.approver_role}")
        _, legs, _ = self._plan(run_id, tenant)
        now = clock.utc_now()
        a = sign_approval(Approval(run_id, tenant, run["round"], current_batch_hash(self.L, run_id, tenant, run["round"]),
                                   approver_id, role, now, now + APPROVAL_TTL,
                                   legs[0].quote.rate if legs else None, sm.mandate.rate_band_bps))
        with self.L.tx() as tx:
            store.save_approval(tx, a)
            tx.append("APPROVED", {"approver": approver_id, "role": role, "round": run["round"],
                                   "batch_hash": a.batch_hash, "fx_quote_rate": None if not legs else str(a.fx_quote_rate),
                                   "expires_at": a.expires_at.isoformat()}, run_id, tenant)
            self._mark_ready(tx, run_id, tenant)
        return "READY"

    def advance(self, run_id: str, tenant: str) -> str:
        """One tick: collect funding, release when READY. Safe to call repeatedly."""
        run = store.get_run(self.L, run_id, tenant)
        if run is None:
            raise Refused(f"no run {run_id}/{tenant}")
        if run["state"] == "AWAITING_FUNDS":
            if funding.match_deposits(self.awx, self.L, run_id, tenant):
                _, _, short = self._plan(run_id, tenant)
                if not short:
                    return self._after_pricing(run_id, tenant)
        elif run["state"] == "READY":
            with self._money:
                return self.ex.release(run_id, tenant)
        return store.get_run(self.L, run_id, tenant)["state"]

    def poll(self) -> None:
        self.ex.poll_inflight()

    def runs(self) -> list[dict]:
        return [store.get_run(self.L, r["run_id"], r["tenant"]) for r in
                self.L.query("SELECT run_id, tenant FROM runs ORDER BY run_id, tenant")]
