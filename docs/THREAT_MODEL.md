# Threat model

What Ringfence protects, who it protects it from, what stops each attack, and what is left. Every control links to code, a test or a recorded run. Scope is the sandbox build: see [Limitations](../README.md#limitations-and-path-to-production).

## What is protected

| Asset | Why it matters |
|---|---|
| Each employer's funds | A payout cannot be pulled back |
| Payee bank details | Whoever controls them controls where the money lands |
| The approval | It is the one human decision in the run |
| The ledger | It is the record of what was intended and what happened |
| Signing keys | They sign mandates and approvals |

## Who attacks

| Attacker | Capability |
|---|---|
| **Hostile document author** | Writes the timesheet, invoice or email the agent reads. Can ask for a bank change, an extra payment, or to skip approval. |
| **Prompt-injected agent** | The model obeys the document. Treated as fully compromised in the design. |
| **Payee-record editor** | Changes a payee's bank details on Airwallex after approval (an insider, a stolen login, a partner) |
| **Flaky network** | Lost responses, timeouts, retries, double fires, a restart mid-run |
| **Another employer** | Tries to reach or spend from a different employer's account |
| **The Ringfence server itself** | Stolen key, owned host, or a bug. Holds a scoped Airwallex key. |

## Attack, control, evidence

| Attack | Control | Evidence |
|---|---|---|
| A document tells the agent to pay a new account | The agent has no tool that takes bank details. A bank change is quarantined until a second person confirms by phone callback, and the editor cannot approve it. | [F2](../FINDINGS.md#f2-bank-change-from-an-email), [GAUNTLET.md](GAUNTLET.md) |
| The agent is told to approve its own run | There is no approve tool. Approval is a person's signature on the exact batch (a passkey for MCP runs). | [MCP.md](MCP.md#why-no-approve-tool), [mcp_remote.py](../ringfence/mcp_remote.py) |
| A payroll is released automatically after a payee's bank details changed | "Nothing changed" covers who is paid as well as how much. A run with a confirmed bank change always needs a person's approval. | [F6](../FINDINGS.md#f6-auto-release-after-a-bank-change), [test_controls.py](../tests/test_controls.py) |
| A payee's account is edited after approval | Bank details are fingerprinted at approval and re-read before release. A change holds the whole run. The transfer carries the approved details inline and is read back and cancelled if it points elsewhere. | [F1](../FINDINGS.md#f1-approval-swap), [F5](../FINDINGS.md#f5-batch-payroll), [BENCH.md](BENCH.md) |
| An approved batch is changed before sending | The approval signs a SHA-256 of the run, employer, round and every line including its request ID. Any change voids it. It expires after 2 hours. | [mandate.py](../ringfence/mandate.py), [gate.py](../ringfence/gate.py) |
| A retry or restart pays twice | The request ID is fixed and stored before the first call. A timeout means lookup, never resend. Before release, Airwallex is asked whether each line was already paid. | [F4](../FINDINGS.md#f4-a-retry-pays-twice), [executor.py](../ringfence/executor.py) |
| One employer pays from another's account | One token per employer, chosen by code. Funds are checked against that employer's own balance, and FX sells only its own spare currency. A verifier probes cross-employer access live. | [F3](../FINDINGS.md#f3-the-node-sdk-shares-one-login), [verify.py](../ringfence/verify.py) |
| A forged webhook sets a payment state | A webhook only prompts a re-fetch after its signature is verified. | [webhooks.py](../ringfence/webhooks.py) |
| A hostile timesheet crashes or confuses intake | Code parses it. Anything unreadable is rejected. The parser is fuzzed. | [TESTING.md](TESTING.md) |
| The ledger is rewritten | It is append-only and hash-chained, with database triggers blocking `UPDATE` and `DELETE`. Its head goes into each transfer's Airwallex metadata, so a rewritten ledger no longer matches the bank. | [ledger.py](../ringfence/ledger.py) |
| An approval is replayed or reused | The challenge is single-use and expires in 5 minutes. A changed payroll voids the page. | [MCP.md](MCP.md#the-approval-page) |

## What is left

| Risk | Status |
|---|---|
| A transfer is cancelled only until it is `SENT`. A repoint landing between the release check and the send is recalled right after release, but a transfer already `SENT` cannot be cancelled and a person has to chase the bank. | Known. 3 of 3 live race trials were cancelled in time ([BENCH.md](BENCH.md)). The structural fix is binding the payee content at a source Ringfence cannot rewrite. |
| One scoped key reaches every employer, so isolation between employers rests on code, not on Airwallex. | Known. Connected accounts remove it ([DECISIONS.md](DECISIONS.md#separate-accounts-not-connected-accounts)). |
| A stolen server key can create payees and transfers within the key's scope. | The gate and verifier detect it, but the key itself is the control. Production needs a secrets store and key rotation. |
| The approver's device is compromised. | Out of scope. The passkey proves a person unlocked the device, not what is on it. |
| The public MCP endpoint has no login, and any caller can replace the last agent run. | Sandbox only. Login is the first roadmap item ([ROADMAP.md](../ROADMAP.md)). |
| SQLite is single-node. | Known. A shared database is on the roadmap. |
| Cut-off times are assumptions. | Known. |

## Reporting

Found something not listed here? [SECURITY.md](../SECURITY.md).
