"""python -m ringfence [--backend fake|live] <command>

setup | run <tenant> | approve <tenant> <approver> <role> | release <tenant> | poll | reconcile | status [tenant] | demo | reset
`demo` is the whole story in one process, so it also works on the in-memory fake.
Stepwise commands need the live sandbox (the fake lives and dies with one process).
"""
from __future__ import annotations

import argparse
import os
import sys
import tempfile
import time
from datetime import date

from . import scenarios, setup_demo, store
from .awx import build_backend
from .config import EMPLOYERS
from .ledger import Ledger
from .orchestrator import Orchestrator, Refused

PAY_DATE = date(2026, 11, 14)  # demo/employers.json pay date


def _rid(o: Orchestrator) -> str:
    return o.run_id(PAY_DATE)


def reconcile(o: Orchestrator) -> None:
    """Lines left UNKNOWN (a call that may or may not have landed) are looked up by their stored request_id, then everything is polled."""
    for ln in store.lines_in_states(o.L, ("UNKNOWN", "HOLD_UNKNOWN")):
        print(f"{ln['tenant']} {ln['contractor_id']}: {o.ex.reconcile_line(ln['run_id'], ln['tenant'], ln['contractor_id'])}")
    o.poll()


def status(o: Orchestrator, tenant: str | None = None) -> None:
    for r in o.runs():
        if tenant and r["tenant"] != tenant:
            continue
        lines = store.get_lines(o.L, r["run_id"], r["tenant"], round=r["round"])
        print(f"{r['tenant']:<10} {r['run_id']}  {r['state']:<18} " +
              " ".join(f"{ln['contractor_id']}:{ln['state']}" for ln in lines))
    v = o.L.verify()
    print(f"ledger: {'OK' if v.ok else 'BROKEN'}")


def demo(o: Orchestrator, sleep=time.sleep) -> None:
    """Kestrel auto-releases; Northwind waits for approval; Harbour is short, is funded, then approved.
    State-driven and resumable: re-running continues each run from wherever it stopped."""
    rid = _rid(o)
    for t in EMPLOYERS:
        if store.get_run(o.L, rid, t) is None:
            print(f"{t}: {o.submit(o.create_run(t, PAY_DATE), t)}")
    for _ in range(30):
        states = {t: store.get_run(o.L, rid, t)["state"] for t in EMPLOYERS}
        if all(s in ("RELEASED", "DONE") for s in states.values()):
            break
        for t, s in states.items():
            if s == "AWAITING_FUNDS":
                req = next(e["payload"] for e in o.L.entries(run_id=rid, kind="FUNDING_REQUESTED", tenant=t))
                if not any(e["payload"].get("reference") == req["reference"]
                           for e in o.L.entries(run_id=rid, kind="SIMULATED", tenant=t)):
                    scenarios.top_up(o.awx, o.L, rid, t, req)
                    print(f"{t}: [SIMULATED] top-up {req['amount']} {req['currency']} ref {req['reference']}")
            elif s == "AWAITING_APPROVAL":
                role = store.latest_mandate(o.L, t).mandate.approver_role
                print(f"{t}: approve -> {o.approve(rid, t, f'{t}-approver', role)}")
                continue
            new = o.advance(rid, t)
            if new != s:
                print(f"{t}: {s} -> {new}")
        sleep(2)
    else:
        sys.exit("demo did not settle in 30 ticks; rerun to resume")
    for t in EMPLOYERS:
        scenarios.pay_out(o.awx, o.L, rid, t)
    o.poll()
    status(o)


def main() -> int:
    ap = argparse.ArgumentParser(prog="ringfence")
    ap.add_argument("--backend", choices=["fake", "live"])
    ap.add_argument("cmd", choices=["setup", "run", "approve", "release", "poll", "reconcile", "status", "demo", "reset"])
    ap.add_argument("args", nargs="*")
    a = ap.parse_args()
    if a.backend == "fake":  # a throwaway world: never touch the live ledger or registry
        os.environ["RF_VAR"] = tempfile.mkdtemp(prefix="rf-fake-")
    awx, _ = build_backend(a.backend)
    if a.cmd == "reset":  # archives the ledger first; the old take stays verifiable in var/archive
        if input("archive this take and reset runs, ledger and AUD balances? type yes: ") == "yes":
            Orchestrator(awx, Ledger()).reset("cli")
        return 0
    if a.cmd == "setup":
        setup_demo.setup(awx)
        return 0
    if a.backend == "fake" and a.cmd != "demo":
        sys.exit("the fake backend is in-process: use `demo` with --backend fake")
    if a.cmd == "demo" and a.backend == "fake":
        setup_demo.setup(awx)
    o = Orchestrator(awx, Ledger())
    try:
        match a.cmd:
            case "demo":
                demo(o, sleep=(lambda _: None) if a.backend == "fake" else time.sleep)
            case "run":
                rid = o.create_run(a.args[0], PAY_DATE)
                print(f"{rid}: {o.submit(rid, a.args[0])}")
            case "approve":
                print(o.approve(_rid(o), a.args[0], a.args[1], a.args[2]))
            case "release":
                print(o.advance(_rid(o), a.args[0]))
            case "poll":
                o.poll()
                status(o)
            case "reconcile":
                reconcile(o)
                status(o)
            case "status":
                status(o, a.args[0] if a.args else None)
    except (Refused, IndexError) as e:
        sys.exit(f"refused: {e}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
