# Ringfence

**Multi-Employer Payroll Executor: deadline-aware, fund-isolated payroll runs on Airwallex.**
Airwallex Agentic Banking Hackathon, Kit 06.

A payroll provider pays contractors for several companies. Ringfence lets an AI agent prepare every company's payroll.
It never pays one company's people with another company's money, never pays the wrong person, and never misses a pay deadline without warning.

- **Live demo** (no login, test money only): https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com
- **Video 1, the product** (non-technical): _link_
- **Video 2, the findings** (technical, the seven bugs in depth): _link_
- **Findings:** [FINDINGS.md](FINDINGS.md). Seven ways an agent on Airwallex can be led to pay the wrong person, each proven live and fixed in Ringfence.

![Three employers](docs/img/demo.png)

## How it meets the brief

| Brief | How Ringfence does it |
|---|---|
| **Multi-employer** | Each employer is its own Airwallex account, with its own beneficiaries, balances, approver and rules. |
| **Fund-isolated** | Code logs in as each employer: one token per employer, chosen by the harness, never by the model. Balances are never pooled or summed. Airwallex returns `401` if one employer's token touches another account. |
| **Deadline-aware** | Each run knows its pay date. A short employer is told exactly how much to send, to its own account, and by when (e.g. "Short AUD 1,240.17, fund by Sat 09:00"). The run pays automatically when the money lands. Late or failed payouts are flagged. |
| **Payroll runs** | Timesheets are read, priced (with FX where needed), approved by a named person, then executed exactly once. Every payout is tracked to PAID, including a late return. |

**The agent proposes. Code decides.** Claude reads timesheets and emails. Amounts (in `Decimal`), limits, approvals, request IDs and the employer binding all come from code.
Untrusted input, such as a bank-change email or a hidden instruction, is quarantined. Every step goes into a hash-chained ledger whose head is stamped into each Airwallex transfer.

## Try it

1. Open the live demo and go to **Three employers**. Press **Run Friday payroll**. Kestrel pays, Northwind waits for its approver, and Harbour is short of AUD and gets its own funding instructions.
2. Approve Northwind. Fund Harbour, then approve.
3. Use the **Try to break it** cards: a bank-change email, a double click, a network drop, a cross-employer call, a tampered ledger.
4. Open **Proof**: per-employer isolation checks, and certificates that verify offline.
5. Open **Try it**: upload a timesheet from [demo/samples/](demo/samples/) or type your own payroll.

Every row is badged **Live on Airwallex**, **Airwallex simulator** or **Simulated by us** (`[SIMULATED]`), so you always know what is real.

## Use it from Claude (MCP)

Ringfence ships an MCP server. It has no approve tool, so a human always signs.

```
claude mcp add ringfence -- uv run python -m ringfence.mcp_server --backend fake
```

Or open this repo in Claude Code: `.mcp.json` already registers it. The tools are `get_status`, `price_run`, `propose_run`, `request_release` and `certificate`.
Use `--backend live` with the sandbox environment variables below.

## Run it locally

Requires [uv](https://docs.astral.sh/uv/). No keys are needed for the offline demo, which uses a fake Airwallex and a scripted agent.

```
make sync
make fake-demo     # http://127.0.0.1:8000
make check         # lint + the offline test suite
```

**Live sandbox.** Set `AWX_CLIENT_ID`, `AWX_API_KEY`, `AWX_BASE_URL`, `AWX_PLATFORM_ACCOUNT` and `AWX_EMPLOYER_A/B/C` as environment variables (never commit them).
Then run `uv run python -m ringfence.setup_demo` and `make demo`. Set `ANTHROPIC_API_KEY` to use Claude; without it, the scripted agent runs.

## Repo map

| Path | What |
|---|---|
| [FINDINGS.md](FINDINGS.md) | The seven findings, with evidence and fixes |
| `ringfence/` | Gate (pure rules), executor (exactly-once), ledger (hash chain), funding and deadlines, FX, agent loop, app, MCP server |
| `static/` | The single-page UI |
| `tests/` | The offline suite against a fake Airwallex |
| `scripts/` | `breakit.py` (reproduces the findings), isolation and money-path checks, sandbox probes |
| `bench/` | Probe outputs (`bench/probes/*.out.txt`) and benchmark results |
| `docs/` | [DEMO.md](docs/DEMO.md), [AIRWALLEX_GAPS.md](docs/AIRWALLEX_GAPS.md), [PROBES.md](docs/PROBES.md), [GAUNTLET.md](docs/GAUNTLET.md), [BENCH.md](docs/BENCH.md) |
| `deploy/` | Azure VM, Caddy HTTPS, systemd |
| `video/` | Source for the demo film (Remotion) |

## Honest notes

- Sandbox only. Fee credits and some deposits are `[SIMULATED]` because the sandbox can't do them. Every other Airwallex call in the live demo is real.
- The live demo is shared. Runs reset on request, and playground runs are deleted after 30 minutes.
- No secrets are in this repo.
