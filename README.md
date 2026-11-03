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
is unchanged. The Claude path is also tested live: `claude-sonnet-5-5` (the default; `RF_MODEL` overrides; `claude-haiku-5-5` was no faster live and once held a run on its own, `claude-opus-5-5` is slower).

## Live deployment (Azure)
One Ubuntu VM, Caddy for automatic HTTPS (public, no login), uvicorn on 127.0.0.1 under systemd, SQLite on the VM disk. Files are in `deploy/`.
1. `az vm create` with `--custom-data deploy/cloud-init.yaml` in a region your subscription allows. Anthropic blocks some regions (Hong Kong returned 403), so test the key from the VM.
2. `python deploy/push_env.py <ssh-alias>` copies the `AWX_*` and `ANTHROPIC_API_KEY` values from your environment into `/etc/ringfence/env` (root, mode 600). Nothing is printed.
3. `bash deploy/deploy.sh <ssh-alias> --first` ships the code, then installs the unit and starts it. `deploy.sh` does not render the Caddyfile. Install it with:
   `sed 's/__HOST__/<host>/' deploy/Caddyfile.tmpl | ssh <ssh-alias> 'sudo tee /etc/caddy/Caddyfile >/dev/null && sudo caddy validate --config /etc/caddy/Caddyfile && sudo systemctl reload caddy'`
4. `uv run python scripts/register_webhooks.py https://<host>/webhooks/airwallex` registers one webhook per employer and prints `AWX_WEBHOOK_SECRET=...` for the env file.
The demo is public. `RF_PUBLIC=1` (set by the unit) throttles `POST /api/*` to one per second (Start over: one per 20 s) and shows a "shared sandbox" banner. Claude ticks are capped per UTC day by `RF_LLM_DAILY_CAP` (default 300); past the cap the offline rules take over. Use `--backend fake` locally so only the VM drives the live sandbox accounts.

## Other entry points

- CLI: `uv run python -m ringfence [--backend fake] demo | run | approve | release | poll | reconcile | status [tenant] | reset`
- Offline certificate check: `uv run python -m ringfence.verify cert <file>`
- MCP server (Claude Code / Desktop): `claude mcp add ringfence -- uv run python -m ringfence.mcp_server --backend fake`
  (drop `--backend fake` for live). Tools: `get_status`, `price_run`, `propose_run`, `request_release`, `certificate`.
  There is no approve tool: a person approves in the UI.
- Plain-English rules: the **Rules** tab. Preview shows last week's payments under the new rule; the employer's own
  finance approver signs it. Rules can only change caps, auto-release and the FX band.
- Contractor link: "Contractor link" under each payee (Show details) opens `/track/<token>`: their own payment only.
- Webhooks: `POST /webhooks/airwallex`, verified with `AWX_WEBHOOK_SECRET`. A webhook only triggers a re-fetch; the poller stays the truth. Proven live on the Azure deploy (signed events from all three employers reach the ledger).

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
