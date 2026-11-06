"""Run lifecycle (BUILD_SPEC 4.5a). The ONLY caller of executor.release.

DRAFT -> AWAITING_FUNDS | AWAITING_APPROVAL | READY -> RELEASING -> RELEASED -> DONE.
Code computes every number; the agent (later) can only ask for a run to be created or submitted.
"""
from __future__ import annotations

import json
import os
import shutil
import threading
from datetime import date, timedelta
from decimal import Decimal
from pathlib import Path

from . import beneficiaries as ben
from . import copy, fees, funding, fx, inbox, seed, store
from .awx import Awx, AwxError, AwxTimeout
from .config import ROOT, clock, employer_name, var_dir
from .executor import Executor, current_batch_hash
from .ledger import Ledger
from .mandate import Approval, make_request_id, sign_approval
from .money import price_line, price_run

APPROVAL_TTL = timedelta(hours=2)


class Refused(Exception):
    """An operator action the state machine or a mandate does not allow."""


class Orchestrator:
    def __init__(self, awx: Awx, ledger: Ledger, executor: Executor | None = None, cert_dir: Path | None = None):
        self.awx, self.L = awx, ledger
        self.cert_dir = cert_dir  # reset() archives these; None = the repo's artifacts/certs
        self.ex = executor or Executor(awx, ledger, on_done=lambda r, t: fees.charge(awx, ledger, r, t))
        self._money = threading.Lock()  # one release at a time; the executor's CAS makes a repeat a no-op anyway

    # -- create ------------------------------------------------------------------------------------
    def run_id(self, pay_date: date) -> str:
        """The obligation, not our memory: a lost or fresh database derives the same request_ids, so Airwallex refuses the
        second payment. Only a demo that re-runs one pay date after each reset salts it with the ledger epoch."""
        w = os.environ.get("RF_WORLD", "")[:6]  # worlds share one Airwallex account: keep their request_ids apart
        take = f"-{self.L.epoch()}" if os.environ.get("RF_DEMO_TAKES") == "1" else ""
        return f"{pay_date:%Y%m%d}{take}" + (f"-{w}" if w else "")

    def ensure_mandates(self) -> None:
        with self.L.tx() as tx:
            for m in seed.default_mandates().values():
                if store.latest_mandate(tx, m.mandate.tenant) is None:
                    store.save_mandate(tx, m)
                    tx.append("MANDATE_SIGNED", {"tenant": m.mandate.tenant, "version": m.mandate.version},
                              None, m.mandate.tenant)

    def create_run(self, tenant: str, pay_date: date, hours: dict[str, Decimal] | None = None, run_id: str | None = None) -> str:
        """DRAFT with PLANNED lines. Hours default to this tenant's parsed timesheet; rates come from the registry."""
        self.ensure_mandates()
        hours = hours or inbox.load_timesheet(tenant)
        reg, cs, run_id = ben.load_registry(), seed.contractors(tenant), run_id or self.run_id(pay_date)
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
            try:
                for ccy, amt in short.items():
                    funding.request_funding(self.awx, self.L, run_id, tenant, ccy, amt,
                                            date.fromisoformat(run["pay_date"]))
            except LookupError:  # a signed rule leaves a shortfall in a currency this employer has no account for
                self.hold(run_id, tenant, copy.HELD_NO_ACCOUNT.format(t=employer_name(tenant, plain=True), ccy=ccy))
                return "HELD"
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
            matched = funding.match_deposits(self.awx, self.L, run_id, tenant)
            # re-price after a match, or when nothing is open (a deposit was reversed): ask again for what is still short
            if matched or not funding._requests(self.L, run_id, tenant, "OPEN"):
                return self._after_pricing(run_id, tenant)
        elif run["state"] == "READY":
            with self._money:
                lines, c = store.get_lines(self.L, run_id, tenant, states=("READY",)), self.awx.for_tenant(tenant)
                # a READY line has no transfer yet (INTENT is written before the create): one on Airwallex means an earlier
                # copy of us paid it and this ledger forgot (fresh disk, old backup past Airwallex's 7-day request_id memory)
                paid = [ln["contractor_id"] for ln in lines if (t := c.transfer_by_request(ln["request_id"]))
                        and t.get("status") not in ("FAILED", "CANCELLED")]
                if paid:
                    self.L.append("ALERT", {"what": "ALREADY_PAID_ON_AIRWALLEX", "contractors": paid}, run_id, tenant)
                    self.hold(run_id, tenant, "already_paid_on_airwallex",
                              "Airwallex already holds a payment for this obligation that this ledger does not know about")
                    return "HELD"
                if bad := ben.drifted(c, tenant, lines):
                    self.L.append("ALERT", {"what": "BENEFICIARY_CHANGED_OUTSIDE_RINGFENCE", "lines": bad}, run_id, tenant)
                    self.hold(run_id, tenant, "beneficiary_changed_outside_ringfence",
                              "a payee's bank account changed on Airwallex, not through Ringfence: re-approve it as a bank change")
                    return "HELD"
                st = self.ex.release(run_id, tenant)
                self._recall_redirected(c, run_id, tenant)
                return st
        return store.get_run(self.L, run_id, tenant)["state"]

    def _recall_redirected(self, c, run_id: str, tenant: str) -> None:
        """drifted() and the create are two calls: a repoint landing between them is visible only in the transfer's own
        snapshot of where it goes. Cancel that transfer while Airwallex still allows it (until SENT)."""
        pins = ben.load_registry().get("tenants", {}).get(tenant, {}).get("pins", {})
        for ln in store.get_lines(self.L, run_id, tenant):
            if not ln.get("transfer_id"):
                continue
            try:
                t = c.get(f"/transfers/{ln['transfer_id']}")
            except (AwxError, AwxTimeout):
                continue  # Proof re-checks every snapshot
            bd = (t.get("beneficiary") or {}).get("bank_details")
            if not bd or t.get("status") in ("CANCELLED", "FAILED") or ben.fingerprint(bd) == pins.get(ln["beneficiary_id"]):
                continue
            cancelled = False
            for i in range(5):  # live: a transfer refuses updates for a few seconds right after create
                try:
                    c.post(f"/transfers/{t['id']}/cancel", {})
                    cancelled = c.get(f"/transfers/{t['id']}").get("status") == "CANCELLED"
                    break
                except (AwxError, AwxTimeout):
                    self.awx._sleep(2 * (i + 1))
            self.L.append("ALERT", {"what": "PAID_TO_UNAPPROVED_ACCOUNT", "contractor_id": ln["contractor_id"],
                                    "transfer_id": t["id"], "cancelled": cancelled}, run_id, tenant)

    def poll(self) -> None:
        self.ex.poll_inflight()

    def runs(self) -> list[dict]:
        return [store.get_run(self.L, r["run_id"], r["tenant"]) for r in
                self.L.query("SELECT run_id, tenant FROM runs ORDER BY run_id, tenant")]

    # -- untrusted proposals: quarantined or flagged, never applied ----------------------------------
    def propose_bank_change(self, run_id: str, tenant: str, cid: str, bank: dict, doc_id: str, by: str) -> dict:
        rec = ben.propose_bank_change(self.awx, self.L, tenant, cid, bank, doc_id, by)
        with self.L.tx() as tx:
            run = store.get_run(tx, run_id, tenant)
            if run:
                store.set_run(tx, run_id, tenant, beneficiary_editors=sorted({*run.get("beneficiary_editors", []), by}))
        return rec

    def note_rate_request(self, run_id: str, tenant: str, cid: str, new_rate: Decimal, doc_id: str, note: str) -> dict:
        """Shown in the approval diff as 'requested by email'. The registry rate, and so the amount, never changes."""
        old = seed.contractors(tenant)[cid].rate
        req = {"contractor_id": cid, "old_rate": str(old), "new_rate": str(new_rate), "doc_id": doc_id,
               "note": note[:200], "over_25pct": abs(new_rate - old) / old > Decimal("0.25")}
        with self.L.tx() as tx:
            run = store.get_run(tx, run_id, tenant)
            old_reqs = run.get("rate_requests", [])
            if any((r["doc_id"], r["contractor_id"]) == (doc_id, cid) for r in old_reqs):
                return req  # the same email again
            store.set_run(tx, run_id, tenant, rate_requests=[*old_reqs, req])
            tx.append("PROPOSAL", {"kind": "rate_change", **req}, run_id, tenant)
        return req

    def confirm_bank_change(self, tenant: str, qid: int, approver_id: str, role: str, ref: str) -> str:
        """After a callback: the new beneficiary replaces the old one in this tenant's unreleased runs, and any
        approval over the old batch goes stale through its hash."""
        new_id = ben.confirm_callback(self.awx, self.L, tenant, qid, approver_id, role, ref)
        cid = self.L.query("SELECT contractor_id FROM quarantine WHERE id=?", (qid,))[0]["contractor_id"]
        with self.L.tx() as tx:
            for run in store.runs_in(tx, ("DRAFT", "AWAITING_FUNDS", "AWAITING_APPROVAL", "READY")):
                if run["tenant"] != tenant:
                    continue
                ln = store.get_line(tx, run["run_id"], tenant, cid)
                if ln and ln["state"] in ("PLANNED", "READY"):
                    store.set_line(tx, run["run_id"], tenant, cid, "PLANNED", beneficiary_id=new_id)
                    if run["state"] == "READY":
                        for other in store.get_lines(tx, run["run_id"], tenant, states=("READY",)):
                            store.set_line(tx, run["run_id"], tenant, other["contractor_id"], "PLANNED")
                        store.set_run(tx, run["run_id"], tenant, state="AWAITING_APPROVAL")
        return new_id

    # -- operator controls ---------------------------------------------------------------------------
    def hold(self, run_id: str, tenant: str, reason: str, note: str = "") -> None:
        with self.L.tx() as tx:
            run = store.get_run(tx, run_id, tenant)
            if run is None or run["state"] in ("RELEASING", "RELEASED", "DONE"):
                raise Refused(f"cannot hold a run in state {run['state'] if run else 'missing'}")
            for ln in store.get_lines(tx, run_id, tenant, states=("READY",)):
                store.set_line(tx, run_id, tenant, ln["contractor_id"], "PLANNED")
            store.set_run(tx, run_id, tenant, state="HELD", hold_reason=reason)
            tx.append("HOLD", {"reason": reason, "note": note[:200]}, run_id, tenant)

    def resume(self, run_id: str, tenant: str) -> str:
        run = store.get_run(self.L, run_id, tenant)
        if run is None or run["state"] != "HELD":
            raise Refused("only a HELD run can be resumed")
        with self.L.tx() as tx:
            store.set_run(tx, run_id, tenant, state="DRAFT")
        return self.submit(run_id, tenant)

    def set_kill_switch(self, on: bool, by: str) -> None:
        self.L.set_kill_switch(on, by)

    def reset(self, by: str) -> None:
        """Archive this take and start a clean one. Never deletes anything on Airwallex; each tenant's AUD is sold back
        inside its own account so Harbour is short again."""
        from . import setup_demo
        certs = self.cert_dir or ROOT / "artifacts" / "certs"
        dest = self.L.reset(by)
        if certs.is_dir():
            shutil.move(str(certs), str(dest.parent / f"{dest.stem}_certs"))
        shutil.rmtree(var_dir() / "inbox", ignore_errors=True)  # emails dropped during the last take
        self.ensure_mandates()
        setup_demo.setup(self.awx, drain=True)

    # -- the approval, as a diff against last run ------------------------------------------------------
    def diff(self, run_id: str, tenant: str) -> dict:
        run = store.get_run(self.L, run_id, tenant)
        names = {k: c.name for k, c in seed.contractors(tenant).items()}
        last = inbox.history(tenant)
        lines = store.get_lines(self.L, run_id, tenant, round=run["round"])
        changes, same, totals = [], [], {}
        for ln in lines:
            cid, amt, ccy = ln["contractor_id"], Decimal(ln["amount"]), ln["currency"]
            totals[ccy] = totals.get(ccy, Decimal(0)) + amt
            prev = last.get(cid)
            row = {"contractor_id": cid, "name": names[cid], "amount": str(amt), "currency": ccy, "state": ln["state"]}
            if prev is None:
                changes.append({**row, "kind": "new"})
            elif prev != amt:
                pct = ((amt - prev) / prev * 100).quantize(Decimal("0.1"))
                changes.append({**row, "kind": "amount", "previous": str(prev), "pct": str(pct)})
            else:
                same.append(row)
        bank = []
        for r in self.L.query("SELECT * FROM quarantine WHERE tenant=? ORDER BY id", (tenant,)):
            d = json.loads(r["data"])
            b = d.pop("bank")
            bank.append({"id": r["id"], "contractor_id": r["contractor_id"], "name": names.get(r["contractor_id"]),
                         "status": r["status"], "last4": (b.get("account_number") or b.get("iban") or "")[-4:], **d})
        open_ = run["state"] in ("DRAFT", "AWAITING_APPROVAL", "AWAITING_FUNDS")
        legs, short = self._plan(run_id, tenant)[1:] if open_ else ([], {})
        sm = store.latest_mandate(self.L, tenant)
        return {"run_id": run_id, "tenant": tenant, "round": run["round"], "state": run["state"],
                "changes": changes, "unchanged": {"count": len(same), "totals": _sum(same)},
                "removed": [c for c in last if c not in {ln["contractor_id"] for ln in lines}],
                "rate_requests": run.get("rate_requests", []), "bank_changes": bank,
                "fx": [{"sell": g.sell, "buy": g.buy, "rate": str(g.quote.rate), "sell_amount": str(g.quote.sell_amount),
                        "buy_amount": str(g.quote.buy_amount), "band_bps": sm.mandate.rate_band_bps if sm else None}
                       for g in legs],
                "shortfall": {k: str(v) for k, v in short.items()},
                "totals": {k: str(v) for k, v in sorted(totals.items())},
                "approver_role": sm.mandate.approver_role if sm else None}


def _sum(rows: list[dict]) -> dict[str, str]:
    out: dict[str, Decimal] = {}
    for r in rows:
        out[r["currency"]] = out.get(r["currency"], Decimal(0)) + Decimal(r["amount"])
    return {k: str(v) for k, v in sorted(out.items())}
