# Ringfence

**Multi-Employer Payroll Executor: deadline-aware, fund-isolated payroll runs on Airwallex.**
Airwallex Agentic Banking Hackathon, Kit 06.

[Live demo](https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com) · [Video: the product](https://drive.google.com/file/d/12EMcRB7AoGwF9cdbaqS5QGDKp-xv-E7r/view?usp=sharing) · [Video: the security findings](https://drive.google.com/file/d/1zJT3bRolDF0d6HG6CB4pQZLJZWVne-vB/view?usp=sharing) · [Findings report](FINDINGS.md)

![Three employers, one run each](docs/img/demo.png)

## Problem

A payroll provider pays contractors for several employers. The hard part is not the arithmetic. Payments can't be undone, each employer's money must stay separate, and every run has a pay-day deadline. Most failures are operational: an employer funds too late, a retry pays twice, or bank details change just before a run. An AI agent adds a new failure: it can be talked into paying the wrong account.

## Solution

Ringfence runs each employer's payroll on that employer's own Airwallex account. Claude reads timesheets and emails and proposes the run. Deterministic code decides everything that moves money.

| Brief | How Ringfence meets it |
|---|---|
| **Multi-employer** | One Airwallex account and one signed mandate per employer: allowed payees, currencies, caps, FX rate band, approver ([mandate.py](ringfence/mandate.py)). Each employer's run moves on its own. |
| **Fund-isolated** | Each run uses a token logged in as that employer only. The token is chosen by code, never by the model. The release gate re-checks the employer on every line, and balances are never pooled ([gate.py](ringfence/gate.py)). |
| **Deadline-aware** | The employer gets an act-by time: its currency's bank cut-off on pay day, minus 2 hours. A short employer gets a funding request to its own account with a unique reference, and the run resumes when that deposit lands ([funding.py](ringfence/funding.py)). |
| **Payroll runs** | Read, then price (in `Decimal`, with FX quoted), then a named approver signs the exact batch. After that comes the gate check, then each payment exactly once, then tracking to `PAID` or `RETURNED` ([executor.py](ringfence/executor.py)). |

## Architecture

```
 timesheets, inbox ──► Claude (10 tools, none can move money)
                          │ proposals only
                          ▼
                  gate.check_propose ──► run priced in Decimal, FX quoted
                                              │
                         named approver signs the exact batch (HMAC)
                                              │
                  gate.check_release (pure function, 25 refusal codes)
                                              │
     executor: INTENT saved ──► POST /transfers with this employer's token
                                              │
     poller ──► PAID / RETURNED      verifier (no LLM) ──► signed certificate per employer
```

1. **The model has no money tool.** The agent's 10 tools only read or propose ([agent/tools.py](ringfence/agent/tools.py)). The employer is fixed by the harness, so no tool even takes an employer as input.
2. **A pure release gate.** It has no I/O, no clock and no model: facts go in, and Allow or Deny comes out. Examples of its 25 refusal codes: `TENANT_MISMATCH`, `INSUFFICIENT_OWN_FUNDS`, `APPROVAL_HASH_MISMATCH`, `FX_RATE_OUT_OF_BAND`. A missing cap counts as a refusal.
3. **Approval binds content, not IDs.** The approver signs a SHA-256 hash of every line, and the approval expires after 2 hours. Each payee's bank details are pinned and re-read from Airwallex before release. They are sent inline in the transfer, and the transfer is read back after it is created.
4. **Each payment happens exactly once.** The request ID is fixed before the first attempt. After a timeout, Ringfence looks the payment up and never resends. An existing transfer is adopted only if its payee, amount and currency match.
5. **A record you can verify.** The ledger is append-only and hash-chained, and its head is stamped into each transfer's Airwallex metadata. A separate verifier with no LLM runs 10 checks per employer and signs an Ed25519 certificate ([verify.py](ringfence/verify.py)).

## Security findings

Before building, we built a reference agent the way Airwallex's docs, SDK and MCP suggest, and tried to make it pay the wrong account. Five issues can cost a company money. Each one is closed in Ringfence. **[FINDINGS.md](FINDINGS.md)** has the full report for each: a plain explanation, the impact, screenshots, transfer IDs, the API calls involved, and a script that reproduces it.

| # | Issue | What happened | Ringfence |
|---|---|---|---|
| [F1](FINDINGS.md#f1-approval-swap) | Approval swap | The payee's bank account was changed after approval, and the approved payment went to the new account (live, 3 of 3) | Bank details pinned, re-read, sent inline: run held |
| [F2](FINDINGS.md#f2-bank-change-from-an-email) | Bank change from an email | The agent paid the account from a fake invoice (live, 5 of 5) | Quarantined until a phone callback |
| [F3](FINDINGS.md#f3-the-node-sdk-shares-one-login) | The Node SDK shares one login | Client A's payment went out on client B's login | One token per employer, set by code |
| [F4](FINDINGS.md#f4-a-retry-pays-twice) | A retry pays twice | A lost response plus a new request ID moved GBP 2 for GBP 1 owed (live) | Request ID fixed before the first try |
| [F5](FINDINGS.md#f5-batch-payroll) | Batch payroll | The batch booked to a swapped account, and the API can't cancel it (live, 4 of 4) | No batches; bank details in each payment |

Airwallex's own account isolation held: 12 of 12 cross-account calls were refused.

## From the proposal to the build

| Shortlisted proposal | Status | Notes |
|---|---|---|
| Harness binds each run to one employer | Built, changed | Uses `x-login-as` per employer instead of `x-on-behalf-of`, because connected-account onboarding isn't enabled on our sandbox. Only the binding layer would change. |
| Run mandate and deterministic gate | Built | |
| Isolation evidence from a non-LLM verifier | Built | Signed certificate per employer, verifiable offline |
| Funding deadline, `OVERDUE` transfers | Built | |
| Bank-detail changes before a run | Built | See F1 and F2 |
| Batch limits and retries | Built, changed | Batches dropped after F5. Deterministic request IDs. Late returns after `PAID` are tracked. |
| Approval delay | Built, changed | Approvals expire after 2 hours. There are no batch dates to move. |
| Timeline projection with an act-by time | Partly built | The act-by time is built. Not built: a full wallet timeline, including the 9:00 processing start. |
| Provisional funds and direct-debit limits | Not built | The sandbox has no direct debit. Settled-only funding is one flag (`ACCEPT_PENDING`). |
| Sandbox demo: 3 employers, fault injection, pass criteria | Built | Each pass criterion is a check in the per-employer report |

## Testing

- **462 offline tests** against a fake Airwallex that mirrors recorded sandbox behaviour ([PROBES.md](docs/PROBES.md)).
- **500 random operation sequences**, with the money invariants checked after every step.
- **36 prompt-injection documents.** An agent that obeys every instruction attempted 28 attacks, and the gate blocked all 28. Claude followed none ([GAUNTLET.md](docs/GAUNTLET.md)).
- **Live on the sandbox:**
  - 20 parallel releases with 3 dropped responses made exactly one transfer per line.
  - 12 of 12 cross-employer calls were refused.
- **Benchmark** against a reference agent with a human approving every write ([BENCH.md](docs/BENCH.md)).

## Quick start

You need [uv](https://docs.astral.sh/uv/). The offline demo needs no keys: it uses a fake Airwallex and a scripted agent.

```
make sync
make fake-demo     # http://127.0.0.1:8000
make check         # lint + offline tests
```

**Live sandbox.**
1. Set `AWX_CLIENT_ID`, `AWX_API_KEY`, `AWX_BASE_URL`, `AWX_PLATFORM_ACCOUNT` and `AWX_EMPLOYER_A/B/C` as environment variables. Never commit them.
2. Run `uv run python -m ringfence.setup_demo`, then `make demo`.
3. Optional: set `ANTHROPIC_API_KEY` to use Claude. Without it, the scripted agent runs.

**MCP server.** It has no approve tool, so a person always signs:

```
claude mcp add ringfence -- uv run python -m ringfence.mcp_server --backend fake
```

**Live demo walkthrough.**
1. Open **Three employers** and press **Run Friday payroll**. Kestrel pays, Northwind waits for its approver, and Harbour is short of AUD.
2. Approve Northwind. Fund Harbour, then approve it.
3. Try the **Try to break it** cards.
4. Open **Proof** for the per-employer certificates.

## Repository layout

| Path | Contents |
|---|---|
| [ringfence/](ringfence/) | `gate.py`, `mandate.py`, `funding.py`, `fx.py`, `executor.py`, `ledger.py`, `verify.py`, `agent/`, `app.py`, `mcp_server.py` |
| [tests/](tests/) | Offline test suite |
| [scripts/](scripts/) | `breakit.py` (reproduces the findings), isolation and money-path checks |
| [bench/](bench/) | Sandbox probes and benchmark results, the evidence behind FINDINGS.md |
| [static/](static/) | Web UI |
| [deploy/](deploy/) | Azure VM, Caddy, systemd |

## Limitations

- **Sandbox only.** Three steps are simulated because the sandbox can't do them: fee credits, employer top-ups, and payouts reaching `PAID`. They are labelled `[SIMULATED]` in the UI and logs.
- Bank cut-off times are configured assumptions, not Airwallex data.
- Wage and tax calculation stay in the employer's payroll system. This is not compliance software.
