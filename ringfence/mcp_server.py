"""Ringfence as an MCP server (stdio). Lets Claude Code or Claude Desktop price a run, read status, propose a
run for approval, ask for release and fetch the isolation certificate.

There is deliberately NO approve tool. Approval is a person's signed act in the Ringfence UI or CLI. request_release
only moves money if an approval already exists for that exact batch; the same gate and executor as the app apply.
The employer is a parameter, but it only chooses a lane: each lane is bound to its own Airwallex token by the harness.
"""
from __future__ import annotations

import argparse
import os
import tempfile
from typing import Literal

from . import setup_demo, store, verify
from .agent.loop import pay_date
from .awx import build_backend
from .config import EMPLOYERS, var_dir
from .ledger import Ledger
from .orchestrator import Orchestrator, Refused

Tenant = Literal["northwind", "kestrel", "harbour"]


class Ringfence:
    def __init__(self, o: Orchestrator):
        self.o = o

    def _run(self, tenant: str, create: bool = False) -> str:
        if tenant not in EMPLOYERS:
            raise ValueError(f"unknown employer {tenant}")
        rid = self.o.run_id(pay_date())
        if store.get_run(self.o.L, rid, tenant) is None:
            if not create:
                raise Refused(f"no run for {tenant} yet: call propose_run first")
            self.o.create_run(tenant, pay_date())
        return rid

    def _state(self, rid: str, tenant: str) -> str:
        return store.get_run(self.o.L, rid, tenant)["state"]

    def get_status(self) -> list[dict]:
        return [{"tenant": r["tenant"], "run_id": r["run_id"], "state": r["state"]} for r in self.o.runs()]

    def price_run(self, tenant: str) -> dict:
        """What the batch would cost and what changed since last time. Creates the draft run if there is none."""
        return self.o.diff(self._run(tenant, create=True), tenant)

    def propose_run(self, tenant: str) -> dict:
        """Submit the priced run: it auto-releases only if the employer's signed mandate allows, otherwise it waits."""
        rid = self._run(tenant, create=True)
        if self._state(rid, tenant) == "DRAFT":
            self.o.submit(rid, tenant)
        return {"run_id": rid, "state": self._state(rid, tenant),
                "next": "A person approves in the Ringfence UI; this server cannot approve."}

    def request_release(self, tenant: str) -> dict:
        rid = self._run(tenant)
        state = self._state(rid, tenant)
        if state != "READY":
            raise Refused(f"{tenant} is {state}: nothing is approved to release")
        return {"state": self.o.advance(rid, tenant)}

    def certificate(self, tenant: str) -> dict:
        rep = verify.report(self.o.awx, self.o.L)
        certs = verify.certificates(rep, verify.current_run_id(self.o.L), "mcp")
        if tenant not in certs:
            raise LookupError(f"no certificate for {tenant}")
        return {"ok": rep["ok"], "certificate": certs[tenant]}


def serve(rf: Ringfence) -> None:
    from mcp.server.mcpserver import MCPServer
    m = MCPServer("ringfence")

    def safe(fn, *a):
        try:
            return fn(*a)
        except (Refused, ValueError, LookupError, PermissionError) as e:
            return {"error": str(e)}

    @m.tool()
    def get_status() -> list[dict]:
        """State of every employer's payroll run for this Friday."""
        return rf.get_status()

    @m.tool()
    def price_run(tenant: Tenant) -> dict:
        """The employer's batch: totals, changes since last week, FX legs, shortfall. Moves no money."""
        return safe(rf.price_run, tenant)

    @m.tool()
    def propose_run(tenant: Tenant) -> dict:
        """Submit the run through the same gate as the app. Waits for a person to approve unless the mandate allows auto-release."""
        return safe(rf.propose_run, tenant)

    @m.tool()
    def request_release(tenant: Tenant) -> dict:
        """Release an already-approved run. Refused unless a person has approved this exact batch."""
        return safe(rf.request_release, tenant)

    @m.tool()
    def certificate(tenant: Tenant) -> dict:
        """Signed segregation certificate for the employer, built from Airwallex's own records."""
        return safe(rf.certificate, tenant)

    m.run()


def main() -> int:
    ap = argparse.ArgumentParser(prog="ringfence.mcp_server")
    ap.add_argument("--backend", choices=["fake", "live"])
    a = ap.parse_args()
    if a.backend == "fake":
        os.environ["RF_VAR"] = tempfile.mkdtemp(prefix="rf-mcp-")
    awx, _ = build_backend(a.backend)
    if a.backend == "fake":
        setup_demo.setup(awx)
    serve(Ringfence(Orchestrator(awx, Ledger(var_dir() / "ringfence.db"))))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
