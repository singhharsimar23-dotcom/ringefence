# Approval-bound settlement on Alta

Live page: `/alta` on the demo site. MCP: `/alta/mcp`. Network: Alta testnet (formerly Metal), chain 63825, token USDZ.

This document is the full write-up: what was measured on the chain, how the design follows from it, every defect found while building it, the live attack results, how to audit a run yourself, and its scope. Everything marked as run was run on the testnet; each result says where it ran.

## The idea

On a bank rail, Ringfence's gate is the only thing between a compromised server and the money. If the server is taken over, the gate goes with it.

On Alta the approval can be compiled into the payment itself. After a person approves one exact batch, an approver's device (a separate process and key) signs one mandate per approved line: one payee, one amount, one pull, an expiry no later than the approval, and the approved batch hash and request id in the credential's signed description. The server receives only a pull key bound to that line. Two independent enforcers then hold the same rule: Ringfence's gate before the send, and the employer's account in the transaction that moves the money. A compromised Ringfence server can pay only the approved lines, once each, before the approval expires.

The executor that is tested by 435 mutants and checked against the TLA+ model is the same code that sends on Alta. Only the client underneath it changes ([alta.py](../ringfence/alta.py)). The gate, mandate, executor and ledger are not edited.

## What was measured first

A live spike on 25 Nov 2026 ([scripts/probe_alta.py](../scripts/probe_alta.py), results in [spike-report-a.json](alta/spike-report-a.json) and [spike-report-b.json](alta/spike-report-b.json)) answered the questions the design depends on:

| Question | Result |
|---|---|
| Is the description inside the signed credential? | Yes. Editing it makes `status` and `pull` fail with `UndisclosedClaim`. A 118-character `rf:<batch hash>:<request id>` survives intact. |
| Can the pull key revoke or bind? | No. Revoke and bind need the owner key. |
| Does a refused pull use up the one occurrence? | No, with `--record-refusal`. The line can still be paid afterwards. |
| Pulling a spent one-pull mandate again | Same payment id: reported as already paid. New payment id, or a fresh HOME: refused. |
| An agent using Alta's own MCP under a line credential | Refuses any other payee. No payment was made. |
| Gas | About 1.16M gas to bind one mandate. |
| Can a principal's mandates be listed? | No such command. The proof therefore covers the credentials this server holds, and says so. |
| Pending (exit 3) and held (exit 4) | Cannot be forced on the testnet. They are tested against a fake chain that prints the CLI's real text. |

## Design

| Part | File | What it does |
|---|---|---|
| Adapter | [alta.py](../ringfence/alta.py) | Gives the executor the Airwallex client shape. A wallet payout becomes `mandate pull --payment-id <request id>`; fees and other currencies go to the inner client. Status reads never pull. The balance is the sum of unspent budgets of live credentials, so a revoked or expired credential stops the batch. |
| Approver's device | [alta_device.py](../ringfence/alta_device.py), [scripts/alta_device.py](../scripts/alta_device.py) | Recomputes the batch hash from the lines it shows. Takes each wallet from its own payee book, never from the server. Refuses non-cent amounts and approvals about to expire. Checks every line before signing any. Revokes earlier attempts and credentials from replaced approvals. Reads each credential back and compares it before binding. Never hands the owner key to the server. |
| Release preflight | [alta_release.py](../ringfence/alta_release.py) | Read-only. Every ready line must have one bound, unrevoked, unspent credential whose payee, cap, budget, one pull, expiry and signed description equal the approved line, and no earlier attempt may still be payable. Otherwise nothing is pulled. |
| Proof | [alta_verify.py](../ringfence/alta_verify.py) | Compares ledger and chain line by line in both directions and signs the result (Ed25519, as the Airwallex certificates are). |
| Auditor | [scripts/alta_audit.py](../scripts/alta_audit.py) | Needs neither this server nor its ledger: the approved batch, the credential files and an RPC URL are enough. |
| Attack lab | [alta_attacks.py](../ringfence/alta_attacks.py), [scripts/alta_attack_run.py](../scripts/alta_attack_run.py) | Runs each attack against a broad mandate and against Ringfence's mandates, live. |

## Defects found, and the fix for each

Each was reproduced before it was fixed. The named tests fail without the fix; [tests/test_alta_findings.py](../tests/test_alta_findings.py) checks that every named test exists.

<<FINDINGS>>

## Attack lab, live on the testnet

The attacker is the Ringfence server: every pull key, no owner key. Each attack runs against a broad mandate (any payee, budget equal to the whole batch, cap equal to the largest line, unlimited pulls: what an agent wallet is usually given) and against Ringfence's per-line mandates. Attacks 6 and 7 compare Ringfence before and after the fix. Amounts are 0.05 and 0.04 USDZ.

<<ATTACKS>>

## A payroll, end to end

<<PAYROLL>>

## Formal check

[formal/alta_model.py](../formal/alta_model.py) explores every reachable state of two approved lines against a fully hostile server: any pull, any payee, any amount, any number of times, and any reopen. It is plain Python (no TLA+ tool needed) and is run by [tests/test_alta_model.py](../tests/test_alta_model.py).

| Config | States | Result |
|---|---|---|
| Ringfence mandates, device revokes earlier credentials | 48 | No violation of PaidOnlyApproved or NoDoublePay |
| One broad mandate | 158 | Violates PaidOnlyApproved (a payment to a payee nobody approved) |
| Reopen without revoking the old credential | 126 | Violates NoDoublePay (defect A1) |

PaidOnlyApproved means every payment goes to an approved line's payee and is at most that line's amount. The check showed that a mandate caps a payment but does not set it, so a hostile server can pay a line less than approved; it can never pay more. The proof flags such a line. The model is small by design: it covers the rule, not the implementation, which is covered by the tests above.

## Audit a run yourself

```
python scripts/alta_audit.py --export docs/alta/payroll-<date>/export.json --creds docs/alta/payroll-<date>/creds --book docs/alta/payroll-<date>/book.json
```

It recomputes the batch hash, reads each credential from the chain, and prints PASS or FAIL per line. It cannot see a mandate that is not in the folder you give it.

## For agents

`/alta/mcp` (Streamable HTTP): `claude mcp add --transport http ringfence-alta https://<site>/alta/mcp`. Four tools: `price_payroll`, `attack_report`, `payroll_proof`, `recheck_on_chain`. All are read-only. There is no approve tool and no tool takes a wallet address or an amount ([tests/test_alta_app.py](../tests/test_alta_app.py) checks both).

## Limits

<<LIMITS>>

## Tests

[test_alta.py](../tests/test_alta.py), [test_alta_device.py](../tests/test_alta_device.py), [test_alta_attacks.py](../tests/test_alta_attacks.py), [test_alta_verify.py](../tests/test_alta_verify.py), [test_alta_app.py](../tests/test_alta_app.py), [test_alta_findings.py](../tests/test_alta_findings.py), against [fake_chain.py](../tests/fake_chain.py), which prints the CLI's real output text and applies only the rules the spike measured. That includes the executor under every fault schedule of four release attempts, and the existing nine invariants run unchanged over chain payments.
