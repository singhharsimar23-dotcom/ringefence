# Ringfence

**Multi-Employer Payroll Executor: deadline-aware, fund-isolated payroll runs on Airwallex.**
Airwallex Agentic Banking Hackathon, Kit 06.

A payroll provider pays contractors for several companies from one place. Ringfence lets an AI agent run every company's payroll on Airwallex. It never pays one company's people with another company's money. It never pays a bank account that nobody approved. Each company is told what it owes, and by when, in time to make payday.

- **Live demo** (no login, test money only): https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com
- **Main video, the product:** https://drive.google.com/file/d/12EMcRB7AoGwF9cdbaqS5QGDKp-xv-E7r/view?usp=sharing
- **Deep dive, the findings:** https://drive.google.com/file/d/1zJT3bRolDF0d6HG6CB4pQZLJZWVne-vB/view?usp=sharing

![Three employers](docs/img/demo.png)

## The four parts of the brief

### 1. Multi-employer
Each employer is its own Airwallex account, with its own balances, payees, global accounts, approver and rules.
The rules are a **signed mandate** per employer. A mandate sets the allowed currencies, the allowed contractors, a cap per payment and a cap per run, whether FX is allowed and within what rate band, who approves, and when the mandate expires ([mandate.py](ringfence/mandate.py)).
One screen shows every employer's run side by side. Each run moves on its own: one can be paid while another waits for its approver and a third waits for money.

### 2. Fund-isolated
- **One login per employer, chosen by code.** Ringfence logs in to Airwallex *as* that employer (`x-login-as`), so the token can only see and move that employer's money. The model never chooses the account.
- **Airwallex enforces it too.** We tried 12 cross-account calls with one employer's token against another's account. All 12 returned `401`.
- **The release gate checks it again** before any money moves ([gate.py](ringfence/gate.py)). It checks that every line, the run, the token and the mandate belong to the same employer. It refuses a payee whose account is another employer's own account. It checks funds against this employer's balance only.
- **Balances are never pooled or summed.** FX sells only this employer's spare currency. Incoming money counts only if it lands in this employer's own account with the exact reference Ringfence issued ([funding.py](ringfence/funding.py)).

### 3. Deadline-aware
- Every run has a **pay date**. Each currency has a bank cut-off on that day (e.g. AUD 11:00 Sydney, GBP 12:00 London). Ringfence works back two hours from the cut-off to get an **act-by time**, shown in the employer's own timezone.
- When an employer is short, it gets a **funding card**: the exact amount, its own account details, a unique reference, and the act-by time. Example: *"Short AUD 1,240.17. Fund by Sat 09:00."*
- When a deposit with that reference covers the shortfall, the run **re-prices and carries on by itself**. A short deposit keeps the request open. A reversed deposit asks again for what is still missing.
- After release, every payout is tracked to **PAID**, including the transfers that Airwallex marks `OVERDUE`. A payout that bounces *after* PAID is caught as **RETURNED**. Sending it again needs a fresh approval.

### 4. Payroll runs
1. **Read.** The agent (Claude) reads timesheets and the inbox.
2. **Price.** Code prices every line in `Decimal`, adds fees, and quotes FX where it is needed.
3. **Approve.** A named person approves the exact batch: amounts, payees and *their bank details*.
4. **Release.** The gate re-checks everything, then each payment is created once.
5. **Track.** Each payment is followed through to PAID, and returns are handled. A per-payout fee is collected, and credited back if a payout returns.

Each payment's request ID is fixed before the first attempt. A timeout never triggers a second payment. Ringfence looks up the request ID instead and adopts the payment if it exists ([executor.py](ringfence/executor.py)).

## What is new

- **The agent proposes, code decides.** Claude reads documents and drafts the run. Amounts, caps, approvals, request IDs and which employer's login is used all come from code. Emails and invoices are untrusted. A bank change found in one is quarantined until someone confirms it by phone.
- **Approval covers the destination, not just the name.** The bank details are part of what the approver signs. If a payee's account changes on Airwallex after approval, the run is held, not paid.
- **Money waits for its own employer.** A short employer is never covered from another employer's balance. It gets its own instructions and deadline, and the run resumes when its money lands.
- **Tamper-evident record.** Every step goes into a hash-chained ledger. The ledger head is sent with each Airwallex transfer, so a rewritten ledger no longer matches Airwallex's copy. Run certificates verify offline.

## From the shortlisted proposal to the build

The proposal said the hard part of multi-employer payroll is not arithmetic. It is irreversible money movement, from separate employer balances, against fixed pay-day deadlines. Here is each item of the proposal and what was built.

**Core design**

| Proposal | Status | What was built |
|---|---|---|
| Harness binds each run to one employer; the model never picks the account | **Built, changed** | Proposed `x-on-behalf-of` from one platform account. Connected-account onboarding isn't enabled on our sandbox, so each employer has its own login (`x-login-as`), chosen by code. Only the binding layer would change if onboarding is enabled. |
| Run mandate + deterministic gate: "the agent proposes; the gate decides" | **Built** | Signed mandate per employer: allowed contractors, currencies, cap per payment and per run, FX rate band, approver, expiry. The gate ([gate.py](ringfence/gate.py)) re-checks every release and blocks anything outside it. The pay date lives on the run. |
| Timeline projection and an "act by" time, not just a balance check | **Partly built** | Act-by = the currency's bank cut-off on pay day minus 2 hours, in the employer's timezone, with a live countdown on the funding card. Deposits matched by reference resume the run. Not built: a full model of the wallet over time (expected deposits, direct-debit settlement, the 9:00 processing start). |
| Isolation evidence from a separate non-LLM verifier | **Built** | [verify.py](ringfence/verify.py) reads each employer's transfers with that employer's own token and checks them against the ledger. Each employer gets a report and an Ed25519-signed certificate that verifies offline. |

**Failure cases**

| Proposal | Status | What was built |
|---|---|---|
| Funding deadline, `OVERDUE` transfers | **Built** | A short employer gets a funding card: exact amount, its own account, a unique reference, act-by time. `OVERDUE` transfers are tracked and counted as not yet debited in the funds check. |
| Provisional funds, direct-debit reversals, shared direct-debit limits | **Not built** | The sandbox has no direct debit, and its deposit settle/reverse calls return 404. Deposits are accepted while `PENDING` because the sandbox makes them available at once (one flag, `ACCEPT_PENDING`, switches to settled-only). A reversed deposit reopens the funding request. There is no shared-limit allocation. |
| Approval delay | **Built, changed** | No batches, so no batch date moves. Approvals expire and must be given again (`APPROVAL_EXPIRED`). Transfers in `IN_APPROVAL` are tracked. There's no automatic escalation beyond the countdown. |
| Bank-detail changes before a run (payroll diversion) | **Built, extended** | A bank change from an email is quarantined until a phone callback. Each payee is re-read from Airwallex before release. Each transfer is read back right after it is created, and recalled if it points elsewhere. See findings F1 and F2. |
| Batch limits and retries | **Built, changed** | No batches at all: testing showed a batch pays whoever the payee is at submit time and can't be cancelled (finding F5). Each payment is a single transfer with a request ID fixed before the first try. A timeout leads to a lookup, never a resend. PAID is not final: a late return becomes `RETURNED`, and paying again needs a new approval. |

**Sandbox demo**

| Proposal | Status | What was built |
|---|---|---|
| Three employer accounts, one in a second currency | **Built** | Northwind pays GBP, EUR and AUD (with FX), Kestrel pays USD, and Harbour pays AUD and starts short. |
| Faults: short funding, late approval, changed beneficiary, retried submission, out-of-mandate payment | **Built** | Live cards for short funding, bank-change email, change during send, network drop, cross-employer call, FX rate move, ledger tampering and late return. Hostile instructions to the agent: ghost contractor, pay from another employer, split under the cap, skip approval, CEO override. Approval expiry is covered in the test suite. |
| Pass criteria: zero cross-account debits, zero duplicate payouts, every payout traceable to a run, an isolation report per employer | **Built** | Each criterion is a check in the per-employer report. Every payee is that employer's own. No contractor was paid twice. Each intent has exactly one transfer. Every transfer has a ledger entry and carries the run in its reference. |

**Scope is unchanged.** Sandbox only. Wage and tax calculation stay in the employer's payroll system, and this is not compliance software. Behaviour the sandbox can't reproduce is simulated and labelled `[SIMULATED]`.

## Try it

1. Open the live demo and go to **Three employers**. Press **Run Friday payroll**. Kestrel pays. Northwind waits for its approver. Harbour is short of AUD and gets its own funding card.
2. Approve Northwind. Fund Harbour, then approve it.
3. Use the **Try to break it** cards: a bank-change email, a double click, a network drop, a cross-employer call, a tampered ledger.
4. Open **Proof** for the per-employer isolation checks and certificates that verify offline.
5. Open **Try it**: upload a timesheet from [demo/samples/](demo/samples/), or type your own payroll.

Every row is badged **Live on Airwallex**, **Airwallex simulator** or **Simulated by us** (`[SIMULATED]`), so you can see which parts are real.

## Use it from Claude (MCP)

Ringfence ships an MCP server. It has no approve tool, so a person always signs.

```
claude mcp add ringfence -- uv run python -m ringfence.mcp_server --backend fake
```

If you open this repo in Claude Code, `.mcp.json` registers the server automatically. Its tools are `get_status`, `price_run`, `propose_run`, `request_release` and `certificate`. To use the live sandbox, pass `--backend live` and set the environment variables below.

## Run it locally

You need [uv](https://docs.astral.sh/uv/). The offline demo needs no keys: it uses a fake Airwallex and a scripted agent.

```
make sync
make fake-demo     # http://127.0.0.1:8000
make check         # lint + the offline test suite
```

**Live sandbox.** Set these environment variables, and never commit them: `AWX_CLIENT_ID`, `AWX_API_KEY`, `AWX_BASE_URL`, `AWX_PLATFORM_ACCOUNT` and `AWX_EMPLOYER_A/B/C`.
Then run `uv run python -m ringfence.setup_demo` and `make demo`. Set `ANTHROPIC_API_KEY` to use Claude. Without it, the scripted agent runs.

## How we tested it: the findings

To test Ringfence, we built a reference agent the way Airwallex's docs, SDK and MCP suggest, then tried to make it pay the wrong person. These five findings could cost a company real money. Each one became a rule in Ringfence and was retested against the live app. **[FINDINGS.md](FINDINGS.md)** has the full report for each one: what happens, why it hurts, Airwallex screenshots, transfer IDs, and a script that reproduces it.

| # | Finding | Severity | Reference agent | Ringfence |
|---|---|---|---|---|
| [F1](FINDINGS.md#f1-approval-swap) | Approval swap | High | paid ..9901 · 3/3 | bank details signed into the approval → HELD |
| [F2](FINDINGS.md#f2-bank-change-from-an-email) | Bank change from an email | High | paid ..9901 · 5/5 | quarantined until a phone callback |
| [F3](FINDINGS.md#f3-the-sdk-shares-one-login) | SDK shares one login | High | A's payment on B's login | own login per client, set by code |
| [F5](FINDINGS.md#f5-batch-payroll) | Batch payroll | Medium | booked ..9901 · can't cancel | no batches · bank details in each payment |
| [F4](FINDINGS.md#f4-a-retry-pays-twice) | Retry pays twice | Medium | GBP 2 moved for GBP 1 | request ID fixed before the first try → pays once |
| [✓](FINDINGS.md#what-airwallex-got-right) | Airwallex isolation | Held | 12/12 cross-account calls blocked | built on it |

## Repo map

| Path | What |
|---|---|
| [ringfence/](ringfence/) | `gate.py` (release rules), `mandate.py` (signed per-employer rules), `funding.py` (shortfalls and deadlines), `fx.py`, `executor.py` (exactly-once payouts), `ledger.py` (hash chain), `agent/` (Claude loop), `app.py`, `mcp_server.py` |
| [static/](static/) | The single-page UI |
| [tests/](tests/) | The offline suite, run against a fake Airwallex |
| [FINDINGS.md](FINDINGS.md) | The findings report: evidence, screenshots and fixes |
| [scripts/](scripts/) | `breakit.py` (reproduces the findings), isolation and money-path checks, sandbox probes |
| [bench/](bench/) | Probe outputs and benchmark results |
| [docs/](docs/) | [DEMO.md](docs/DEMO.md), [PROBES.md](docs/PROBES.md), [GAUNTLET.md](docs/GAUNTLET.md), [BENCH.md](docs/BENCH.md) |
| [deploy/](deploy/) | Azure VM, Caddy HTTPS, systemd |
| [video/](video/) | Source for the demo film (Remotion) |

## Honest notes

- This runs on the Airwallex sandbox only. Some steps are simulated because the sandbox can't do them: fee credits, employer top-ups, and payouts reaching PAID. These are all labelled `[SIMULATED]`. Every other Airwallex call in the live demo is real.
- Bank cut-off times are our own configured assumptions, not Airwallex data.
- The live demo is shared. Runs reset on request, and playground runs are deleted after 30 minutes.
- No secrets are in this repo.
