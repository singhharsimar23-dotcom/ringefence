# Ringfence

A payroll agent that can move every employer's money, but only its own. Each employer is bound to its own Airwallex
account token by the harness, never by the model. The model proposes; code decides amounts, limits, approvals and
request_ids. Every money-moving call lands in an append-only, hash-chained ledger, and a signed certificate proves,
from Airwallex's own records, that no employer's funds touched another's.

![Ringfence](artifacts/shots/02_started.png)

## See it in 30 seconds (no keys)

```
make sync
make fake-demo        # then open http://127.0.0.1:8000
```

Click **Run Friday payroll**. Kestrel pays itself, Northwind waits for its approver, Harbour is short and gets a
funding card. The "Try to break it" cards run the attacks. Add `?present=1` for presenter mode.

## Live Airwallex sandbox

1. A scoped sandbox API key linked to the platform account and three employer accounts.
2. Windows user env vars (set with `setx`, never commit values): `AWX_CLIENT_ID`, `AWX_API_KEY`, `AWX_BASE_URL`,
   `AWX_PLATFORM_ACCOUNT`, `AWX_EMPLOYER_A`, `AWX_EMPLOYER_B`, `AWX_EMPLOYER_C`. Optional: `AWX_WEBHOOK_SECRET`.
3. `make sync`, `uv run python -m ringfence.setup_demo`, `make demo`.

Anthropic key: set `ANTHROPIC_API_KEY` for the Claude agent. Without it the offline scripted agent runs and the demo
is unchanged. The Claude path is covered by FakeLLM tests only; it has not been run against the real API.

## Other entry points

- CLI: `uv run python -m ringfence [--backend fake] demo | run | approve | release | poll | reconcile | status [tenant] | reset`
- Offline certificate check: `uv run python -m ringfence.verify cert <file>`
- MCP server (Claude Code / Desktop): `claude mcp add ringfence -- uv run python -m ringfence.mcp_server --backend fake`
  (drop `--backend fake` for live). Tools: `get_status`, `price_run`, `propose_run`, `request_release`, `certificate`.
  There is no approve tool: a person approves in the UI.
- Plain-English rules: the **Rules** tab. Preview shows last week's payments under the new rule; the employer's own
  finance approver signs it. Rules can only change caps, auto-release and the FX band.
- Contractor link: "Contractor link" under each payee (Show details) opens `/track/<token>`: their own payment only.
- Webhooks: `POST /webhooks/airwallex`, verified with `AWX_WEBHOOK_SECRET`. A webhook only triggers a re-fetch; the poller stays the truth. Needs a public URL, so untested live.

## Tests

`make check` runs ruff and the offline suite (fake Airwallex, invariants I1 to I9 after every scenario).
Live checks: `scripts/recon_flow.py`, `scripts/recon_isolation.py`. There is no `make live` pytest contract suite yet.

## Architecture

```
lanes (one token per employer) -> gate (pure rules) -> executor (exactly-once) -> Airwallex
                 ledger (hash chain, SQLite) <- every step      verify.py -> Ed25519 certificates
```

Deviations from the plan are in `docs/BUILD_SPEC.md` and `docs/PROBES.md`.

## Security notes

No secrets are in the repo. Rotate the sandbox key before making the repo public. Fee credits and deposits marked
`[SIMULATED]` exist only because the sandbox cannot do them.
