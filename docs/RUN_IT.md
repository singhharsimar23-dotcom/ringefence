# Run it

## Offline, no keys

You need [uv](https://docs.astral.sh/uv/) and Python 3.12 or newer. The offline demo uses an in-process fake Airwallex and a scripted agent.

```
make sync          # install dependencies
make fake-demo     # web app at http://127.0.0.1:8000
make check         # lint, then the offline tests (476)
```

Open `http://127.0.0.1:8000`. **Three employers** then **Run Friday payroll** shows the whole flow: Kestrel pays, Northwind waits for approval and Harbour is short of AUD. Approve Northwind, fund Harbour, approve it, then try **Try to break it** and **Proof**.

| Command | Does |
|---|---|
| `make sync` | `uv sync` |
| `make check` | `ruff check` and the tests that need no network or keys |
| `make fake-demo` | the app on the fake Airwallex with the scripted agent |
| `make demo` | the app on the live sandbox (needs the variables below) |
| `make live` | the tests marked `live`, against your sandbox |

## On the live Airwallex sandbox

You need an Airwallex sandbox organisation with a platform account and three employer accounts, and an API key that can log in as each. Put the values in a `.env` file or your shell. **Never commit them.**

| Variable | Meaning |
|---|---|
| `AWX_BASE_URL` | the sandbox API host |
| `AWX_CLIENT_ID`, `AWX_API_KEY` | your sandbox API credentials |
| `AWX_PLATFORM_ACCOUNT` | the operator account that collects fees |
| `AWX_EMPLOYER_A`, `AWX_EMPLOYER_B`, `AWX_EMPLOYER_C` | Northwind, Kestrel and Harbour account IDs |
| `AWX_WEBHOOK_SECRET` | verifies signed Airwallex webhooks |
| `AWX_PLAYGROUND_ACCOUNT` | one account all Try it and MCP worlds share, so nothing can reach a real employer account |

Then:

```
uv run python -m ringfence.setup_demo     # idempotent sandbox setup, safe to re-run
make demo                                 # http://127.0.0.1:8000
```

Set `ANTHROPIC_API_KEY` to use Claude as the agent. Without it the scripted agent runs.

## Using Claude

| Variable | Default | Meaning |
|---|---|---|
| `ANTHROPIC_API_KEY` | none | required for the Claude agent and for reading files sent over MCP |
| `RF_MODEL` | `claude-sonnet-5-5` | the agent |
| `RF_DRAFT_MODEL` | `claude-haiku-5-5` | reads the files an MCP agent sends |
| `RF_EFFORT` | `medium` | the agent's effort level |
| `RF_AGENT` | `auto` | `scripted` forces the offline agent |
| `RF_LLM_DAILY_CAP` | `300` | cap on agent model calls per day |

## App settings

| Variable | Default | Meaning |
|---|---|---|
| `RF_BACKEND` | `live` | `fake` runs on the in-process fake Airwallex |
| `RF_VAR` | `./var` | state directory (ledger, registry, keys) |
| `RF_TENANTS` | all three | comma list to run a subset |
| `RF_MANDATE_KEY`, `RF_APPROVAL_KEY` | generated once into `var/keys.json` | signing keys for mandates and approvals |
| `RF_STRICT_NAME_MATCH` | off | `1` blocks anything but a full bank name match (the sandbox calls real accounts invalid, so it is off there) |
| `RF_PUBLIC` | off | `1` for a public site: throttles, banner and kill switch |
| `RF_PUBLIC_URL` | from the request | base URL used in approval links |
| `RF_ENROLL_KEY` | none | secret needed to enrol a passkey at `/passkey` |
| `RF_PLAY_*` | see [playground.py](../ringfence/playground.py) | limits for the Try it and MCP worlds: live and fake world counts, daily and per-IP caps, idle and total time |

## Run the MCP server yourself

To approve an agent run with your own passkey:

1. Start the app with `RF_ENROLL_KEY=<a long random secret>` and `RF_PUBLIC_URL=<the URL you will open>`. A passkey is bound to the host name, so use `localhost` or an `https` host.
2. Open `<url>/passkey`, enter the enrol key and register your passkey (it must be ES256 or RS256).
3. Connect your agent: `claude mcp add --transport http ringfence <url>/mcp`.
4. Run payroll from the agent and open the `approve_at` link.

For the offline, local-only tools: `claude mcp add ringfence -- uv run python -m ringfence.mcp_server --backend fake`. See [MCP.md](MCP.md).

## Metal on-chain funding

Optional second way for a short employer to fund payroll. Set `RF_METAL=1`, `METAL_RPC_URL` and `METAL_RPC_SECRET`, then run `python scripts/metal_setup.py` once. Details: [METAL.md](METAL.md).

## In your own code

[examples/embed.py](../examples/embed.py) prices a run, has a named person approve it, sends it and verifies it in about 15 lines, offline. It is also a test. Swap `build_backend("fake")` for `"live"` to use the sandbox. Read-only run state is available over HTTP: [API.md](API.md).

## Reproduce the findings

`uv run python scripts/breakit.py [approval|batch|retry]` reproduces the findings on your own sandbox accounts. The evidence is in [FINDINGS.md](../FINDINGS.md).

## Deploy

[deploy/](../deploy/) has the Azure VM files: a cloud-init, a systemd unit, a Caddy config template and `deploy.sh`, which ships the current commit to a VM over SSH.

## If something goes wrong

| Symptom | Check |
|---|---|
| `make fake-demo` fails to start | Python older than 3.12, or `make sync` was not run |
| The live demo opens but stays on "starting" | Missing `AWX_*` variables, or `setup_demo` was not run |
| Approval page says "No passkey is enrolled on this server yet" | Enrol one at `/passkey` with `RF_ENROLL_KEY` |
| Approval page says the signature came from another site | `RF_PUBLIC_URL` or the host you opened differs from the host the passkey was enrolled on |
| MCP `run_payroll` says it could not read a payroll | Check `ANTHROPIC_API_KEY` is set: reading files sent over MCP uses a model |
