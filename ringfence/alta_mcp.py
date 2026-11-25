"""Ringfence on Alta as an MCP server at /alta/mcp. Every tool is read-only: none binds, signs, pulls, revokes or approves,
and none accepts a wallet address or an amount. An agent can price a payroll, read what was run, and have the chain
re-checked; paying needs a person's approval and the approver's device, which no tool here can reach.

  claude mcp add --transport http ringfence-alta https://<site>/alta/mcp"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings

INSTRUCTIONS = (
    "Ringfence settles payroll on Alta, the on-chain payments network. A person's approval of an exact batch becomes one "
    "single-use on-chain mandate per line, so a compromised Ringfence server can pay only the approved lines, once. These "
    "tools are read-only: price a payroll, read the recorded attack results and findings, read the recorded payroll's "
    "certificate, or re-check that payroll against the chain now. There is no approve tool, and no tool takes a wallet "
    "address or an amount. Report results exactly as returned, including limits.")


def build(recheck) -> MCPServer:
    from . import alta_app
    m = MCPServer("ringfence-alta", instructions=INSTRUCTIONS)

    @m.tool()
    def price_payroll(hours: dict[str, str]) -> dict:
        """Price a payroll on Alta: hours per contractor id (e.g. {"noah": "10", "zoe": "8"}) -> USD and USDZ per line.
        The rates come from Ringfence's registry, never from you. Moves nothing."""
        try:
            return alta_app.price(hours)
        except Exception as e:  # noqa: BLE001 - the agent should see why, not a stack
            raise ToolError(str(e)) from None

    @m.tool()
    def attack_report() -> dict:
        """The recorded live attack results on the Alta testnet: each attack run against a broad mandate and against
        Ringfence's per-line mandates, with the chain's outcome, reason and transaction. Also every bug found and fixed."""
        o = alta_app.overview()
        return {"network": o["network"], "attacks": o["attacks"], "findings": o["findings"], "limits": o["limits"]}

    @m.tool()
    def payroll_proof() -> dict:
        """The signed certificate for the recorded testnet payroll: per line, the mandate, the USDZ paid and the checks."""
        p = alta_app.payroll()
        if p is None or p["cert"] is None:
            raise ToolError("No payroll has been recorded yet.")
        return {"certificate": p["cert"], "batch": p["export"]}

    @m.tool()
    def recheck_on_chain() -> dict:
        """Re-read the recorded payroll's credentials from the chain now and say whether each still matches what was
        approved: the payee, one pull of the exact amount, the approved batch hash in the signed description."""
        try:
            return recheck()
        except HTTPException as e:
            raise ToolError(str(e.detail)) from None

    return m


def register(app: FastAPI, recheck) -> MCPServer:
    m = build(recheck)
    sub = m.streamable_http_app(streamable_http_path="/alta/mcp", stateless_http=True,
                                transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
    app.router.routes.extend(sub.routes)
    app.router.lifespan_context = lambda _app: m.session_manager.run()
    return m
