# Ringfence

**Multi-Employer Payroll Executor: deadline-aware, fund-isolated payroll runs on Airwallex.**
Airwallex Agentic Banking Hackathon, Kit 06. Runs on the Airwallex sandbox, with optional on-chain funding on the Metal testnet.

[Live demo](https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com) · [Video: the product](https://drive.google.com/file/d/12EMcRB7AoGwF9cdbaqS5QGDKp-xv-E7r/view?usp=sharing) · [Video: the security findings](https://drive.google.com/file/d/1zJT3bRolDF0d6HG6CB4pQZLJZWVne-vB/view?usp=sharing) · [Findings report](FINDINGS.md)

![Three employers, one run each](docs/img/demo.png)

## Problem

A payroll provider pays contractors for several employers. The hard part is not the arithmetic. Payments can't be undone, each employer's money must stay separate, and every run has a pay-day deadline. Most failures are operational: an employer funds too late, a retry pays twice, or bank details change just before a run. An AI agent adds a new failure: it can be talked into paying the wrong account.

## Solution

Ringfence runs each employer's payroll on that employer's own Airwallex account. Claude reads timesheets and emails and proposes the run. Deterministic code decides everything that moves money.

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

## Features

### Multi-employer and fund isolation
| Feature | How it works | Code |
|---|---|---|
| One login per employer | Each employer's token is logged in as that account only (`x-login-as`). The token is chosen by code, never by the model. | [awx.py](ringfence/awx.py#L85) |
| Signed mandate per employer | HMAC-signed rules: allowed contractors, currencies, cap per payment and per run, FX rate band, approver, expiry | [mandate.py](ringfence/mandate.py#L33) |
| Deterministic release gate | A pure function with no I/O, clock or model, and 25 refusal codes. Examples: `TENANT_MISMATCH`, `INSUFFICIENT_OWN_FUNDS`, `BENEFICIARY_IS_OTHER_TENANT_ACCOUNT`, `OVER_RUN_CAP`. A missing cap counts as a refusal. | [gate.py](ringfence/gate.py#L87) |
| No pooled funds | Funds are checked against this employer's balance only. FX sells only this employer's spare currency, in the currencies its mandate allows. | [fx.py](ringfence/fx.py#L47) |

### Deadline-aware funding
| Feature | How it works | Code |
|---|---|---|
| Act-by time | The currency's bank cut-off on pay day, minus 2 hours, shown in the employer's timezone (AUD 11:00 Sydney, GBP 12:00 London, EUR 12:00 Berlin, USD 15:00 New York) | [funding.py](ringfence/funding.py#L29) |
| Funding request | A short employer gets the exact amount, its own global account details, and a unique reference (`RF-<EMP>-<run>-<rand>`) | [funding.py](ringfence/funding.py#L42) |
| Deposit matching | A deposit counts only if it matches the reference, the global account, the currency and the status. Several deposits add up. The run re-prices and resumes by itself. A reversed deposit reopens the request. | [funding.py](ringfence/funding.py#L69) |
| Settled-only mode | A single switch (`ACCEPT_PENDING`) decides whether pending deposits count | [funding.py](ringfence/funding.py#L25) |
| `OVERDUE` and `IN_APPROVAL` tracking | Transfers in either state are tracked to completion, and they count as not yet debited in the funds check | [executor.py](ringfence/executor.py#L167) |

### Approval and bank-detail protection
| Feature | How it works | Code |
|---|---|---|
| Approval bound to the exact batch | The approver signs a SHA-256 hash of the run, the employer, the round and every line, including its request ID. It expires after 2 hours. | [mandate.py](ringfence/mandate.py#L109), [gate.py](ringfence/gate.py#L167) |
| Payee pinning | Bank details are fingerprinted when approved. They are re-read from Airwallex before release, and the run is held if they changed. | [beneficiaries.py](ringfence/beneficiaries.py#L131) |
| Bank details sent inline | Each transfer carries the approved bank details, not a payee ID that can be edited | [executor.py](ringfence/executor.py#L206) |
| Read-back recall | Each transfer is read back after it is created, and cancelled if it points anywhere else | [orchestrator.py](ringfence/orchestrator.py#L187) |
| Bank-change quarantine | A bank change found in an email is held until an approver confirms it by phone callback. Someone who edited a payee can't approve that payee's payment. | [beneficiaries.py](ringfence/beneficiaries.py#L204) |

### Exactly-once execution
| Feature | How it works | Code |
|---|---|---|
| Deterministic request IDs | `sha256(run, employer, contractor, attempt)`, minted once and stored before the first call. The amount is not part of it. | [mandate.py](ringfence/mandate.py#L115) |
| Timeouts never resend | After a timeout, Ringfence looks the payment up by request ID and adopts it only if the payee, amount and currency match. Otherwise it holds the line (`DUPLICATE_MISMATCH`). | [executor.py](ringfence/executor.py#L258) |
| Already-paid check | Before release, Ringfence asks Airwallex whether each line was already paid. This catches a lost database. | [orchestrator.py](ringfence/orchestrator.py#L173) |
| Late returns | A payout that fails after `PAID` becomes `RETURNED`. Its fee is credited back, and paying again needs a new approval. | [executor.py](ringfence/executor.py#L304) |
| Signed webhooks | HMAC-SHA256 is checked in constant time. A webhook is only a hint: Ringfence always re-fetches the transfer. | [webhooks.py](ringfence/webhooks.py#L32) |

### Proof and audit
| Feature | How it works | Code |
|---|---|---|
| Hash-chained ledger | Append-only SQLite, with database triggers that block `UPDATE` and `DELETE`. Each row's hash includes the previous row's. | [ledger.py](ringfence/ledger.py#L45) |
| Ledger stamped at Airwallex | Each transfer carries the ledger head (`rf_seq`, `rf_hash`) in its metadata, so a rewritten ledger no longer matches Airwallex's copy | [executor.py](ringfence/executor.py#L206) |
| Isolation verifier | Separate code with no LLM. It reads each employer's transfers with that employer's own token and runs 10 checks, including a live cross-employer `401` probe. | [verify.py](ringfence/verify.py#L108) |
| Signed certificates | One Ed25519 certificate per employer, verifiable offline | [verify.py](ringfence/verify.py#L63) |

### Agent and integrations
| Feature | How it works | Code |
|---|---|---|
| Agent with no money tool | 10 tools that read or propose. The employer is fixed by the harness, and every input is validated, then checked by the gate. | [agent/tools.py](ringfence/agent/tools.py#L79) |
| MCP server | `get_status`, `price_run`, `propose_run`, `request_release`, `certificate`. There is no approve tool, so a person always signs. | [mcp_server.py](ringfence/mcp_server.py) |
| Platform fee | A per-payout fee is collected from each employer and credited back if a payout returns | [fees.py](ringfence/fees.py#L42) |

## Metal: on-chain funding mandates

[Metal](https://testnet.metalntwx.com) is a blockchain testnet (chain ID 63825) whose wallets support on-chain spending mandates. Its test token is USDZ. Ringfence uses it as a second way for a short employer to cover its payroll, through the pinned `@metalntwx/metal-agent@0.3.3` CLI.

**How it works.**
1. Harbour is short of AUD. It signs a mandate on Metal for exactly the shortfall in USDZ. The mandate allows one pull, pays only the platform's settlement wallet, and expires in one hour.
2. The agent pulls the shortfall once. The pull and its transaction hash are written to the ledger.
3. The matching Airwallex deposit is simulated and labelled `[SIMULATED]`. The normal deposit matcher then closes the funding request.
4. A pull above the cap, or to a lookalike wallet address, is refused by Metal itself, and the refusal is recorded on chain.

**Device-signed mode.** A mandate becomes payable only when its owner binds it. Harbour's device signs and binds one-shot mandates with its own key ([harbour_device.py](scripts/harbour_device.py)), and the server never holds that key. A compromised server can pull at most what Harbour signed, once, and only to the payee Harbour named ([metal.py](ringfence/metal.py#L108)).

**Live receipts** (Metal testnet, [proof_device_signed.py](scripts/proof_device_signed.py), run on a server holding no Harbour key):

| Step | Result | Transaction |
|---|---|---|
| The server pulls the shortfall under Harbour's mandate | paid | [0x65c108fb…63bf](https://testnet.metalntwx.com/tx/0x65c108fbd62681b4ba788cad3cf56e3ed29063e80f8177bdaccce2a08d2463bf) |
| The same mandate is pulled again | refused, `mandate_budget_spent` | [0x9ff764b4…1468](https://testnet.metalntwx.com/tx/0x9ff764b4879ad69b1a21031d2eca28fc87e8e4fb88eb982b9dbe6d8085021468) |
| A pull to a lookalike of the settlement wallet | refused, `mandate_payee_not_listed` | [0x598bb65d…c703](https://testnet.metalntwx.com/tx/0x598bb65db1c032762020dc6a6039af57a1b0a5382225b82ad0fa13146e4ec703) |
| The server writes and binds its own mandate on Harbour's account | bind reverted | none |

Code: [metal.py](ringfence/metal.py#L134). Tests: [test_metal.py](tests/test_metal.py), 14 tests. Because the testnet faucet is capped at about 100 USDZ, the demo treats 1 USDZ as USD 10. The pulled USDZ is sent back after each run. On the live demo, open Harbour's funding card and choose the Metal option.

## Security findings

Before building, we built a reference agent the way Airwallex's docs, SDK and MCP suggest, and tried to make it pay the wrong account. Five issues can cost a company money. Each one is closed in Ringfence. **[FINDINGS.md](FINDINGS.md)** has the full report for each: a plain explanation, the impact, screenshots, transfer IDs, the API calls involved, and a script that reproduces it.

| # | Issue | What happened | Ringfence |
|---|---|---|---|
| [F1](FINDINGS.md#f1-approval-swap) | Approval swap | The payee's bank account was changed after approval, and the approved payment went to the new account (live, 3 of 3) | Bank details pinned, re-read and sent inline. The run is held. |
| [F2](FINDINGS.md#f2-bank-change-from-an-email) | Bank change from an email | The agent paid the account from a fake invoice (live, 5 of 5) | Quarantined until a phone callback |
| [F3](FINDINGS.md#f3-the-node-sdk-shares-one-login) | The Node SDK shares one login | Client A's payment went out on client B's login | One token per employer, set by code |
| [F4](FINDINGS.md#f4-a-retry-pays-twice) | A retry pays twice | A lost response plus a new request ID moved GBP 2 for GBP 1 owed (live) | Request ID fixed before the first try |
| [F5](FINDINGS.md#f5-batch-payroll) | Batch payroll | The batch booked to a swapped account, and the API can't cancel it (live, 4 of 4) | No batches. Bank details travel in each payment. |

Airwallex's own account isolation held: 12 of 12 cross-account calls were refused.

## Testing

- **462 offline tests** against a fake Airwallex that mirrors recorded sandbox behaviour ([PROBES.md](docs/PROBES.md))
- **500 random operation sequences**, with the money invariants checked after every step
- **36 prompt-injection documents.** An agent that obeys every instruction attempted 28 attacks, and the gate blocked all 28. Claude followed none. ([GAUNTLET.md](docs/GAUNTLET.md))
- **Live on the sandbox:** 20 parallel releases with 3 dropped responses made exactly one transfer per line, and 12 of 12 cross-employer calls were refused
- **Benchmark** against a reference agent with a human approving every write ([BENCH.md](docs/BENCH.md))

## Quick start

You need [uv](https://docs.astral.sh/uv/). The offline demo needs no keys: it uses a fake Airwallex and a scripted agent.

```
make sync
make fake-demo     # http://127.0.0.1:8000
make check         # lint + offline tests
```

**Live sandbox.**
1. Set these environment variables, and never commit them: `AWX_CLIENT_ID`, `AWX_API_KEY`, `AWX_BASE_URL`, `AWX_PLATFORM_ACCOUNT`, `AWX_EMPLOYER_A/B/C`.
2. Run `uv run python -m ringfence.setup_demo`, then `make demo`.
3. Optional: set `ANTHROPIC_API_KEY` to use Claude. Without it, the scripted agent runs.

**Metal (optional).** Set `RF_METAL=1`, `METAL_RPC_URL` and `METAL_RPC_SECRET`, then run `python scripts/metal_setup.py` once.

**MCP server.**
```
claude mcp add ringfence -- uv run python -m ringfence.mcp_server --backend fake
```

**Live demo walkthrough.**
1. Open **Three employers** and press **Run Friday payroll**. Kestrel pays, Northwind waits for its approver, and Harbour is short of AUD.
2. Approve Northwind. Fund Harbour (by Airwallex deposit or by Metal), then approve it.
3. Try the **Try to break it** cards.
4. Open **Proof** for the per-employer certificates and the Metal transactions.

## Repository layout

| Path | Contents |
|---|---|
| [ringfence/](ringfence/) | Gate, mandate, funding, FX, executor, ledger, verifier, Metal, agent, web app, MCP server |
| [tests/](tests/) | Offline test suite |
| [scripts/](scripts/) | `breakit.py` (reproduces the findings), isolation checks, Metal setup and device signing |
| [bench/](bench/) | Sandbox probes and benchmark results: the evidence behind FINDINGS.md |
| [static/](static/) | Web UI |
| [deploy/](deploy/) | Azure VM, Caddy, systemd |

## Limitations

- **Sandbox and testnet only.** Steps the sandbox can't perform are simulated and labelled `[SIMULATED]`: fee credits, employer top-ups, and payouts reaching `PAID`.
- The sandbox has no direct debit, so direct-debit reversals and shared direct-debit limits are not exercised.
- Bank cut-off times are configured assumptions, not Airwallex data.
- Wage and tax calculation stay in the employer's payroll system. This is not compliance software.
