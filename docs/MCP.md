# Ringfence MCP

Any MCP client that supports Streamable HTTP can run payroll through Ringfence. There is no login and nothing to install. The agent hands over the payroll files, code prices and checks the run, a person approves with a passkey, and the agent sends exactly what was approved.

## Connect

```
claude mcp add --transport http ringfence https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com/mcp
```

For another client, add an HTTP MCP server with the URL `https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com/mcp`. For your own instance use `https://<your-host>/mcp` ([self-host](RUN_IT.md#run-the-mcp-server-yourself)).

## What happens, in order

1. You tell the agent to run this week's payroll from a folder.
2. The agent calls `run_payroll` with every file, verbatim, including emails it thinks are suspicious. Ringfence decides what to trust.
3. Code reads the files, prices the run on the employer's own Airwallex account and checks every bank account against what Airwallex has saved.
4. The agent shows you the payments, anything flagged, and an **approval link**.
5. You open the link and approve with a passkey (Windows Hello, Touch ID or a security key).
6. You tell the agent you approved. It calls `release_payroll`, which sends exactly what you approved.
7. The agent can fetch the status and a signed proof at any time.

## Tools

The remote server has four tools. None takes a bank detail, and none can approve.

| Tool | Arguments | Does | Returns |
|---|---|---|---|
| `run_payroll` | `files`: object, file name to full text | Reads the files, opens an employer account, checks payees, prices the run and FX | `run_id`, `payments` (name, amount, currency, account ending, state), `totals`, `fx`, `refused_or_flagged`, `bank_change_requests`, `approve_at` |
| `release_payroll` | `run_id` | Sends an approved run. Re-reads every payee from Airwallex first. | Same summary plus `what_happened`, and `changed_after_approval` if a payee was repointed |
| `payroll_status` | `run_id` | Reads where the run is | Same summary, with each payment's Airwallex transfer ID once sent |
| `payroll_proof` | `run_id` | Re-reads every transfer from Airwallex and checks it | `result`, `signature_valid`, `all_checks_passed`, a `download` link to the signed certificate, `payments` |

Limits: 1 to 6 files per run, 8,000 characters in total, one employer per run. A new run replaces the previous agent run, and never while a payout is being sent.

## What you will see

| Situation | What the agent gets |
|---|---|
| `release_payroll` before anyone approved | An error: "Not approved. Only a person can approve this run, with their passkey, at `<link>`. No tool can approve it, and asking again will not change that." |
| An email asks to change a payee's bank account | The request appears under `bank_change_requests` as "quarantined: not used". The old verified account is the only one that is paid. |
| A payee's bank account changes on Airwallex after approval | `release_payroll` sends nothing, holds the whole run and reports `changed_after_approval`: the account approved against what Airwallex says now. |
| `release_payroll` on a run already sent | The summary with the note "Already sent. Nothing new was sent." |
| Unknown or expired `run_id` | "Ringfence has no agent run with that id." Runs are throwaway and expire. |
| Another run is mid-payout | "Another payroll is being sent right now. Try again in a minute." |
| More than 6 files, or over 8,000 characters | A plain error naming the limit |

Every payment is labelled `[SIMULATED]` where the sandbox cannot do it for real, and `bank` tells you whether the run used the live Airwallex sandbox or a simulated bank.

## The approval page

`/approve/<run_id>` shows the payments as the signer will be bound to them: each payee, amount, currency and the account ending the money goes to. Approving signs a one-time challenge with a passkey that was enrolled on the server.

- The challenge is used once and expires after 5 minutes.
- The signature must come from an enrolled passkey, for this site, with the person verified by the authenticator (a PIN or biometric, not only a touch).
- If the payroll changed after the page was opened, the approval is refused and the page must be reloaded.
- A pending bank-change request must be rejected, or confirmed by a second person by phone, before the run can be approved.
- The server verifies the signature itself ([mcp_remote.py](../ringfence/mcp_remote.py)); there is no third-party identity service.

**On the public demo,** passkeys are enrolled by the operator, so a visitor's approval link works only on the operator's enrolled device. To watch the approval flow without that, use the **Try it** tab on the site, where a drop-down user approves. To approve with your own passkey, run your own instance and enrol it at `/passkey` ([steps](RUN_IT.md#run-the-mcp-server-yourself)).

## The local server

For offline use, Claude Code or Claude Desktop can run a local stdio server against the fake Airwallex:

```
claude mcp add ringfence -- uv run python -m ringfence.mcp_server --backend fake
```

This repo's [.mcp.json](../.mcp.json) already declares it. It has five tools, all keyed by employer (`northwind`, `kestrel` or `harbour`).

| Tool | Does |
|---|---|
| `get_status` | State of every employer's run |
| `price_run` | Totals, changes since last week, FX legs, shortfall. Moves no money. |
| `propose_run` | Submits the run through the same gate. Waits for a person unless the signed mandate allows auto-release. |
| `request_release` | Releases an already-approved run. Refused unless a person approved this exact batch. |
| `certificate` | The signed segregation certificate for an employer |

It has no approve tool either. Approval is a person's signed act in the Ringfence UI or CLI.

## Why no approve tool

An agent that can approve its own run is only as safe as the agent. Leaving the approve step out of the tool list means no prompt, document or email can talk the agent into it. The only door is the passkey page, and it signs the batch the person saw.

## Side by side

![Left: a standard agent on the Airwallex API approved a batch, and Tom's pay went to his changed account, which it could not cancel. Right: the Ringfence agent re-read the payees and held the whole run](img/mcp-compare.png)

Same model, same Airwallex account, same payroll. Between approval and sending, Tom's bank account was changed on Airwallex. On the left, the standard agent approved a batch of IDs, with no names or bank accounts, and Tom's pay went to the new account (`99999901`). The batch cancel failed with `401 Admin permissions required`, and Airwallex has switched admin keys off. On the right, Ringfence held the run and nothing was sent. The standard agent's batch hit this 4 times out of 4 ([F5](../FINDINGS.md#f5-batch-payroll)). The two panes are two takes of the same demo, shown side by side as in the video: [watch it used on Claude MCP](https://youtu.be/QnPQ9EYWWQQ).

More evidence: [BENCH.md](BENCH.md). Injection results: [GAUNTLET.md](GAUNTLET.md).

## Known limits

- The public endpoint has no login. Each run is a throwaway sandbox world with one employer, and any caller can replace the last agent run.
- Sandbox only. See [Limitations and path to production](../README.md#limitations-and-path-to-production).
