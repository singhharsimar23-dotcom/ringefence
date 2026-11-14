# Ringfence

**Multi-Employer Payroll Executor: deadline-aware, fund-isolated payroll runs on Airwallex.**
Airwallex Agentic Banking Hackathon, Kit 06. Airwallex sandbox, with optional on-chain funding on the Metal testnet.

[Live demo](https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com) · [Video: security findings](https://drive.google.com/file/d/1zJT3bRolDF0d6HG6CB4pQZLJZWVne-vB/view?usp=sharing) · [Findings report](FINDINGS.md) · [Live run proof](#proof-a-live-run-on-airwallex)

![Three employers, one run each](docs/img/demo.png)

## What it does

A payroll provider pays contractors for several employers. Payments can't be undone, each employer's money must stay separate, and every run has a pay-day deadline. An AI agent adds a new risk: it can be talked into paying the wrong account.

Ringfence runs each employer's payroll on that employer's own Airwallex account. Claude reads timesheets and emails and proposes the run. Deterministic code decides everything that moves money.

```
 timesheets, inbox ──► Claude (10 tools, none can move money)
                          │ proposals only
                  gate.check_propose ──► run priced in Decimal, FX quoted
                          │
                  named approver signs the exact batch (HMAC)
                          │
                  gate.check_release (pure function, 25 refusal codes)
                          │
     executor: INTENT saved ──► POST /transfers with this employer's token
                          │
     poller ──► PAID / RETURNED     verifier (no LLM) ──► signed certificate per employer
```

## Security findings

We built a payroll agent the way Airwallex's docs, SDK and MCP suggest, then attacked it. It paid the wrong account or paid twice in five ways. Ringfence closes all five. Screenshots, transfer IDs and reproduce scripts are in **[FINDINGS.md](FINDINGS.md)**.

| # | Bug | Proven | Fix in Ringfence |
|---|---|---|---|
| [F1](FINDINGS.md#f1-approval-swap) | Payee bank account edited after approval; the approved payment goes to the new account | Live, 3/3 | Bank details pinned, re-checked before release, sent inline |
| [F2](FINDINGS.md#f2-bank-change-from-an-email) | Agent reads a fake invoice, changes the payee's bank account and pays it | Live, 5/5 | Bank changes held until a phone callback |
| [F3](FINDINGS.md#f3-the-node-sdk-shares-one-login) | Node SDK clients share one login, so one employer pays from another's account | SDK code | One token per employer, chosen by code |
| [F4](FINDINGS.md#f4-a-retry-pays-twice) | Retry after a lost response with a new request ID pays twice, with no cancel | Live | Request ID fixed before the first try; timeout means lookup, never resend |
| [F5](FINDINGS.md#f5-batch-payroll) | Batch pays the payee's account as it is at submit; the API can't cancel it | Live, 4/4 | No batches; bank details go in each transfer |

Airwallex's account isolation held: 12 of 12 cross-account calls were refused.

## How it works

**Fund isolation**
- One login per employer: each token is logged in as that account only (`x-login-as`), chosen by code, never by the model ([awx.py](ringfence/awx.py#L85)).
- An HMAC-signed mandate per employer sets allowed contractors, currencies, per-payment and per-run caps, FX rate band, approver and expiry ([mandate.py](ringfence/mandate.py#L33)).
- The release gate is a pure function (no I/O, clock or model) with 25 refusal codes, such as `TENANT_MISMATCH`, `INSUFFICIENT_OWN_FUNDS`, `BENEFICIARY_IS_OTHER_TENANT_ACCOUNT` and `OVER_RUN_CAP`. A missing cap is a refusal ([gate.py](ringfence/gate.py#L87)).
- No pooled funds: funds are checked against this employer's balance only, and FX sells only this employer's spare currency ([fx.py](ringfence/fx.py#L47)).
- **Why separate accounts, not connected accounts.** The sandbox blocks connected-account onboarding ("This account cannot onboard business/individual accounts"), so each employer is its own account in one organisation, reached by one scoped key. Isolation is the same (own balances, payees and global accounts; cross-account calls refused). The risk is also the same, since one key reaches every employer, so isolation rests on code. Switching to connected accounts changes only [`TenantClient._login`](ringfence/awx.py#L85): log in as the platform and add `x-on-behalf-of`.

**Deadline-aware funding**
- Act-by time is the currency's bank cut-off on pay day minus 2 hours, shown in the employer's timezone (AUD 11:00 Sydney, GBP 12:00 London, EUR 12:00 Berlin, USD 15:00 New York) ([funding.py](ringfence/funding.py#L29)).
- A short employer gets the exact amount, its own global account details and a unique reference `RF-<EMP>-<run>-<rand>` ([funding.py](ringfence/funding.py#L42)).
- A deposit counts only if the reference, global account, currency and status all match. Several deposits add up, the run re-prices and resumes by itself, and a reversed deposit reopens the request ([funding.py](ringfence/funding.py#L69)). `ACCEPT_PENDING` decides whether pending deposits count ([funding.py](ringfence/funding.py#L25)).
- `OVERDUE` and `IN_APPROVAL` transfers are tracked to completion and count as not yet debited ([executor.py](ringfence/executor.py#L167)).

**Approval and bank details**
- The approver signs a SHA-256 hash of the run, employer, round and every line including its request ID. It expires after 2 hours ([mandate.py](ringfence/mandate.py#L109), [gate.py](ringfence/gate.py#L167)).
- Bank details are fingerprinted at approval and re-read from Airwallex before release. The run is held if they changed ([beneficiaries.py](ringfence/beneficiaries.py#L131)).
- Each transfer carries the approved bank details inline, not an editable payee ID ([executor.py](ringfence/executor.py#L206)). It is read back after creation and cancelled if it points anywhere else ([orchestrator.py](ringfence/orchestrator.py#L187)).
- A bank change from an email is quarantined until an approver confirms it by phone callback. Whoever edited a payee can't approve that payee's payment ([beneficiaries.py](ringfence/beneficiaries.py#L204)).

**Exactly once**
- The request ID is `sha256(run, employer, contractor, attempt)`, minted once and stored before the first call. The amount is not part of it ([mandate.py](ringfence/mandate.py#L115)).
- After a timeout, Ringfence never resends. It looks the payment up by request ID and adopts it only if payee, amount and currency match. Otherwise it holds the line (`DUPLICATE_MISMATCH`) ([executor.py](ringfence/executor.py#L258)).
- Before release, it asks Airwallex whether each line was already paid, which catches a lost database ([orchestrator.py](ringfence/orchestrator.py#L173)).
- A payout that fails after `PAID` becomes `RETURNED`: its fee is credited back and paying again needs a new approval ([executor.py](ringfence/executor.py#L304)).
- Webhooks are HMAC-SHA256 checked in constant time and treated as hints. The transfer is always re-fetched ([webhooks.py](ringfence/webhooks.py#L32)).

**Proof and audit**
- Append-only, hash-chained SQLite ledger. Triggers block `UPDATE` and `DELETE` ([ledger.py](ringfence/ledger.py#L45)).
- Each transfer carries the ledger head (`rf_seq`, `rf_hash`) in its Airwallex metadata, so a rewritten ledger no longer matches Airwallex ([executor.py](ringfence/executor.py#L206)).
- A separate verifier with no LLM reads each employer's transfers with its own token and runs 10 checks, including a live cross-employer `401` probe ([verify.py](ringfence/verify.py#L108)). It issues one Ed25519 certificate per employer, verifiable offline ([verify.py](ringfence/verify.py#L63)).

**Agent and integrations**
- The agent's 10 tools only read or propose. The employer is fixed by the harness, and every input is validated, then checked by the gate ([agent/tools.py](ringfence/agent/tools.py#L79)).
- The MCP server offers `get_status`, `price_run`, `propose_run`, `request_release` and `certificate`. There is no approve tool, so a person always signs ([mcp_server.py](ringfence/mcp_server.py)).
- A per-payout platform fee is collected from each employer and credited back if a payout returns ([fees.py](ringfence/fees.py#L42)).

## Proof: a live run on Airwallex

Run `20261114-53jrfe` (pay date 14 Nov 2026), executed 11 Nov 2026 at 01:39 UTC through the public demo. Every ID can be looked up in the matching Airwallex sandbox account.

| Account | ID | Pays in |
|---|---|---|
| Platform (operator, collects fees) | `acct_NIym7HZZOOOqBCE7F6LkMA` | |
| Northwind Studio | `acct_Y5VX3QXWNSyiun0cbai15A` | GBP, EUR, AUD (with FX) |
| Kestrel Labs | `acct_FG3wEt9HNg29C0zhpelKHg` | USD |
| Harbour Foods | `acct_8bUTqZJePIG80-z_-xiutw` | AUD, starts short |

| Employer | Contractor | Amount | Transfer ID |
|---|---|---|---|
| Northwind | Ada Okoye | GBP 450.00 | `7730d4e5-50fe-4241-b702-25ee11556d45` |
| Northwind | Lukas Brandt | EUR 400.00 | `5295001b-4cad-4c8f-a93e-cb5fe2730b42` |
| Northwind | Mia Tran | AUD 300.00 | `fa7d28fb-14b4-43df-9a4a-8abbf14b7a4c` |
| Kestrel | Zoe Park | USD 500.00 | `e3534d8b-95b8-4e9b-bebb-7e00e9e6a4cf` |
| Kestrel | Noah Reyes | USD 550.00 | `31c9e9df-cee6-4a10-80ab-403b228aa234` |
| Harbour | Ivy Nguyen | AUD 700.00 | `893fa7a1-a902-45ec-b531-bcd30813034d` |
| Harbour | Omar Haddad | AUD 480.00 | `88ead1ba-d583-4305-b285-f0007366e5b1` |
| Harbour | Ruth Adler | AUD 60.17 | `1614a59d-8c4e-4ca4-86cf-e1d771b095f3` |

- **FX:** Northwind sold its own GBP 155.45 for AUD 300.00 at 1.929858, inside the approved rate band. Conversion `3e5a9c08-74fb-43c3-a78c-9709998a9804`, request ID `fx-20261114-53jrfe-northwind-AUD-r1`.
- **Short employer:** Harbour was AUD 1,240.17 short. It was asked to fund its own AUD global account `8ec497a4-67a9-4ba2-8b3d-48f1a53d1f4d` with reference `RF-HAR-JRFE-690Q` by 14 Nov 09:00 Sydney. Deposit `00db6d9e-9998-4866-a767-080d5da6153d` [SIMULATED] matched, and the run resumed.
- **Platform fees:** Northwind GBP 4.50 `5cd1d3a5-96f9-44ee-8250-b59bf003d37c`, Kestrel GBP 3.00 `7f9b745b-f449-46e1-a5d5-c00d7bd295ef`, Harbour GBP 4.50 `b0c08166-a751-4465-9651-e3e6a7818a4d`.
- **Certificates:** each employer passed all 10 verifier checks. The certificates in [docs/proof/](docs/proof/) list every debit with its request ID. `uv run python -m ringfence.verify cert docs/proof/northwind.json` prints `VALID ... PASS`, and any edited field gives `INVALID`.
- **Real vs simulated:** transfers, FX, fees, beneficiaries, the global account and the isolation check are real sandbox calls. Payouts reaching `PAID` and Harbour's deposit used Airwallex's `/simulation/*` endpoints. The platform's fee credit is recorded by Ringfence only, because the sandbox doesn't credit the platform. All simulated steps are labelled `[SIMULATED]`.
- **APIs used:** login per account (`x-login-as`), `/balances/current`, `/beneficiaries`, `/global_accounts`, `/deposits`, `/fx/quotes/create`, `/fx/conversions/create`, `/transfers/create`, `/transfers` (get, list by `request_id`, cancel), `/webhooks`, `/simulation/*`.

## Metal: on-chain funding mandates

[Metal](https://testnet.metalntwx.com) is a blockchain testnet (chain ID 63825) whose wallets support on-chain spending mandates, with test token USDZ. Ringfence uses it as a second way for a short employer to fund payroll, through the pinned `@metalntwx/metal-agent@0.3.3` CLI ([metal.py](ringfence/metal.py#L134)).

1. Harbour signs a mandate for exactly its shortfall: one pull, payable only to the platform's settlement wallet, expiring in one hour.
2. The agent pulls once, and the transaction hash goes into the ledger. The matching Airwallex deposit is [SIMULATED] and closes the funding request.
3. In device-signed mode, Harbour's own device signs and binds the mandate ([harbour_device.py](scripts/harbour_device.py)), and the server never holds that key. A compromised server can pull at most what Harbour signed, once, to the payee Harbour named ([metal.py](ringfence/metal.py#L108)).

Live testnet receipts from a server holding no Harbour key ([proof_device_signed.py](scripts/proof_device_signed.py)):

| Step | Result | Transaction |
|---|---|---|
| Server pulls the shortfall | paid | [0x65c108fb…63bf](https://testnet.metalntwx.com/tx/0x65c108fbd62681b4ba788cad3cf56e3ed29063e80f8177bdaccce2a08d2463bf) |
| Same mandate pulled again | refused, `mandate_budget_spent` | [0x9ff764b4…1468](https://testnet.metalntwx.com/tx/0x9ff764b4879ad69b1a21031d2eca28fc87e8e4fb88eb982b9dbe6d8085021468) |
| Pull to a lookalike wallet | refused, `mandate_payee_not_listed` | [0x598bb65d…c703](https://testnet.metalntwx.com/tx/0x598bb65db1c032762020dc6a6039af57a1b0a5382225b82ad0fa13146e4ec703) |
| Server binds its own mandate on Harbour's account | bind reverted | none |

The faucet gives about 100 USDZ, so the demo counts 1 USDZ as USD 10. Tests: [test_metal.py](tests/test_metal.py) (14).

## Testing

- 462 offline tests against a fake Airwallex built from recorded sandbox behaviour ([PROBES.md](docs/PROBES.md)), plus 500 random operation sequences with money invariants checked after every step.
- 36 prompt-injection documents: an agent that obeys every instruction attempted 28 attacks and the gate blocked all 28. Claude followed none ([GAUNTLET.md](docs/GAUNTLET.md)).
- Live on the sandbox, 20 parallel releases with 3 dropped responses made exactly one transfer per line. Benchmark against a reference agent with a human approving every write: [BENCH.md](docs/BENCH.md).

## Run it

Needs [uv](https://docs.astral.sh/uv/). The offline demo uses a fake Airwallex and a scripted agent, so it needs no keys.

```
make sync
make fake-demo     # http://127.0.0.1:8000
make check         # lint + offline tests
```

- **Live sandbox:** set `AWX_CLIENT_ID`, `AWX_API_KEY`, `AWX_BASE_URL`, `AWX_PLATFORM_ACCOUNT` and `AWX_EMPLOYER_A/B/C` (never commit them), then run `uv run python -m ringfence.setup_demo` and `make demo`. Set `ANTHROPIC_API_KEY` to use Claude instead of the scripted agent.
- **Metal:** set `RF_METAL=1`, `METAL_RPC_URL` and `METAL_RPC_SECRET`, then run `python scripts/metal_setup.py` once.
- **MCP:** `claude mcp add ringfence -- uv run python -m ringfence.mcp_server --backend fake`
- **Findings:** `uv run python scripts/breakit.py [approval|batch|retry]` reproduces them on your own sandbox accounts.
- **Demo walkthrough:** open **Three employers** and press **Run Friday payroll**. Kestrel pays, Northwind waits for approval, and Harbour is short of AUD. Approve Northwind, fund Harbour (deposit or Metal), approve it, then try **Try to break it** and **Proof**.

Layout: [ringfence/](ringfence/) core and web app · [tests/](tests/) · [scripts/](scripts/) findings and setup · [bench/](bench/) sandbox probes and evidence · [static/](static/) UI · [deploy/](deploy/) Azure VM.

## Limitations

- Sandbox and testnet only. Steps the sandbox can't perform are [SIMULATED]: fee credits, employer top-ups and payouts reaching `PAID`. The sandbox has no direct debit, so direct-debit reversals aren't exercised.
- Bank cut-off times are configured assumptions, not Airwallex data.
- Wage and tax calculation stay in the employer's payroll system. This is not compliance software.
