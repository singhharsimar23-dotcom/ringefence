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

### A1. A reopened line could be paid twice
*Ringfence's first Alta design.*

**What was found.** A line is reopened as attempt 2 and a second credential is signed. Attempt 1's credential stays bound and unspent, and the server still holds its pull key, so both credentials are payable: the contractor is paid twice.

**The fix.** The device revokes every earlier attempt before it signs the next one, and refuses to sign a line whose earlier attempt already paid. Release preflight refuses while any earlier attempt could still pay. The auditor checks it.

**Tests.** `test_the_stale_attempt_credential_is_a_double_pay_and_preflight_blocks_it`, `test_device_revokes_the_earlier_attempt_before_it_signs_the_next`. Live: attack 6.

### A2. A renewed approval left the old credentials payable
*Ringfence's device, found by its own test.*

**What was found.** The batch is approved again after a change. The credentials signed for the first approval still carry a pull key on the server, so the server can pay a line under an approval the human has since replaced.

**The fix.** When a credential no longer matches the current approval the device revokes it on chain and sets it aside before it signs the new one. Preflight also refuses any credential whose signed description is not the current batch hash.

**Tests.** `test_a_renewed_approval_retires_the_old_credential_of_an_unchanged_line`, `test_a_credential_signed_for_another_batch_blocks_release`. Live: attack 7.

### A3. Alta's default mandate is broad
*Alta CLI 0.3.3 defaults, measured on the testnet.*

**What was found.** Without --payee a credential pays any address; without --max-occurrences it can be pulled until the budget is gone; the default life is 30 days. An agent wallet set up the usual way lets a compromised server pay any address, above or below what anyone approved, and pay the same line again (attacks 1 to 4, broad side).

**The fix.** The device never uses a default: one payee from its own book, cap equal to budget equal to the line, one pull, expiry no later than the approval. Preflight refuses any credential whose terms differ from the approved line.

**Tests.** `test_a_credential_for_a_different_wallet_or_amount_blocks_release`, `test_device_rejects_a_wallet_the_server_supplies`. Live: attack 1.

### A4. Alta's pull memory is local to one machine
*Alta's own documentation, reproduced live.*

**What was found.** Alta remembers a payment id on the disk that ran the pull. A retry from another machine signs a new payment, so a broad mandate with budget left is paid twice (attack 4, broad side).

**The fix.** A one-pull mandate makes 'once' a property of the chain, not of one disk. The executor never re-sends: after an uncertain pull it reads the credential's state, and a refusal that says the line is spent is adopted, not retried.

**Tests.** `test_retry_from_a_fresh_home_cannot_pay_twice`, `test_a_line_paid_from_another_machine_mid_release_is_adopted_not_failed`. Live: attack 4.

### A5. The live top-up holds the employer's owner key
*Ringfence's earlier Metal top-up, still deployed.*

**What was found.** The deployed top-up signs mandates on the server, so the server holds the Harbour owner key. Whoever controls the server can mint a mandate for any amount to any address and bind it. Settlement mode closes this by design.

**The fix.** In settlement mode the server never holds an owner key. The device signs and binds on another key and another process. The server's own attempt to bind a mandate for the principal is refused by the chain (attack 5). The existing top-up is unchanged and labelled; moving it onto the device is the next step.

**Tests.** `test_server_side_never_signs_binds_or_revokes`, `test_a_pull_key_cannot_revoke_or_bind`. Live: attack 5.

### A6. Slow signing made credentials outlive the approval
*Ringfence's device, found by the first live payroll.*

**What was found.** The device worked out the credential lifetime once, then created and bound one line after another. Each create and bind takes about a minute on the testnet, so the later credentials expired after the approval did. Preflight refused both lines (outlives_approval) and nothing was paid.

**The fix.** The lifetime is worked out again for each credential just before it is created, with 30 seconds of slack, and the device refuses a line when the approval has run out while it was signing.

**Tests.** `test_every_credential_expires_before_the_approval_even_when_signing_is_slow`, `test_device_refuses_a_line_when_the_approval_runs_out_while_signing`.

### A7. A payroll that paid nothing was certified as a pass
*Ringfence's verifier, found by the same live run.*

**What was found.** The same refused payroll produced a signed certificate saying PASS. Every line was consistent with the chain (no payment, none expected yet), but nothing had been paid, so a reader would take it for a settled payroll.

**The fix.** A certificate says PASS only when every line is paid. A consistent payroll that is not yet paid says INCOMPLETE, and the payroll script refuses to record anything but a PASS.

**Tests.** `test_a_payroll_that_has_not_paid_is_incomplete_not_a_pass`.

### A8. Every pull failed, and the error said the wallet was unfunded
*Ringfence's Alta adapter, found by the same live run.*

**What was found.** The adapter passed the pull key as --key on a pull. On the real CLI that flag names a funded key for refusal records, so every pull failed with 'm.key.json does not hold a 32-byte private key'. The adapter then reported any pull that failed without a stated reason as insufficient_funds, which pointed at the wrong cause. The offline fake accepted the flag, so no test saw it.

**The fix.** The adapter no longer passes --key on a pull (the CLI uses the pull key beside the credential). The fake chain now rejects the flag with the CLI's own error, so the mistake cannot come back unseen.

**Tests.** `test_a_pull_never_names_the_pull_key_as_the_key_flag`.

### A9. Alta's own verifier cannot prove two of its eleven refusal reasons
*Alta CLI/SDK 0.3.3 (metal-pay), read from its own source.*

**What was found.** mandate verify rebuilds a payment or a refusal from the chain alone, but its reason-checking code only decides six of the eleven reasons Mandate Binding can refuse for: revoked, expired, outside the window, payee not allowed, over the per-payment cap, outside recurrence. A refusal for over budget or over occurrences passes with no check at all, because the chain's MandateRefused event carries no spent or occurrences count, unlike MandatePayment, which does: the running total the refusal must have broken never reaches the chain, so no verifier can confirm or contradict it from the chain alone.

**The fix.** Ringfence's own audit never calls Alta's verifier and never reads a refusal's stated reason at all: it reads the mandate's own live spent, occurrences and payments straight from mandate status, the chain's current state, not a reconstruction from events. A test pins that the audit's result cannot change no matter what reason a refusal claims.

**Tests.** `test_the_audit_never_trusts_a_refusal_reason_alta_cannot_prove`.


## Attack lab, live on the testnet

The attacker is the Ringfence server: every pull key, no owner key. Each attack runs against a broad mandate (any payee, budget equal to the whole batch, cap equal to the largest line, unlimited pulls: what an agent wallet is usually given) and against Ringfence's per-line mandates. Attacks 6 and 7 compare Ringfence before and after the fix. Amounts are 0.05 and 0.04 USDZ.

Run 2026-11-25, alta testnet (chain 63825).

| # | Attack | Incident class | Unprotected | Ringfence |
|---|---|---|---|---|
| 1 | approval swap: pay line A's money to the attacker's wallet | Bybit, Feb 2025: signers approved what they could not read | paid [0x18e23736…eeb6](https://testnet.metalntwx.com/tx/0x18e23736442be9f8ecf00cbeb0a63dd65a5c4abb9a9ec109fe10721e51d6eeb6) | refused, `mandate_payee_not_listed` [0xb0009932…5b78](https://testnet.metalntwx.com/tx/0xb00099329cfff7e8a8fe37a13d085880078058c178a8f002ed04416195c55b78) |
| 2 | address poisoning: pay a wallet that looks like A's (same first 6 and last 4) | address-poisoning losses, every year | paid [0x95058881…d577](https://testnet.metalntwx.com/tx/0x95058881bbc66f9021187f5034f5727b006184978710cafc64d9d2e331e1d577) | refused, `mandate_payee_not_listed` [0x37ce85e1…938c](https://testnet.metalntwx.com/tx/0x37ce85e1fcf912de7e2b1c61953965f23c2fcc8cbf30f26d93e3ee334609938c) |
| 3 | inflated amount: pay A more than the approved line | Lobstar Wilde, Feb 2026: an agent sent far more than meant | paid [0xe78558d4…da71](https://testnet.metalntwx.com/tx/0xe78558d4a59b657cfa77962ad5dd3f27cb0e02c419f3df33ed47a05e2b02da71) | refused, `mandate_cap_exceeded` [0x8b41ade6…1eb7](https://testnet.metalntwx.com/tx/0x8b41ade6adbd7fa1e4bc2621cdc1bd7295e608625f1a9b00cc436c14bbcc1eb7) |
| 4 | double pull: pull A's line a second time with a new payment id from a fresh machine | Alta's own docs: dedup is local to one disk | paid [0xe7ef0647…3c0c](https://testnet.metalntwx.com/tx/0xe7ef0647ee24a01d10638e4153895fdeacc10e5bb5359c64bc3d66f3624f3c0c) | refused, `mandate_budget_spent` [0x898783e9…f1c2](https://testnet.metalntwx.com/tx/0x898783e9d3d34169553aa96db711d2a544a68ee91c2952bf996d8c1577e5f1c2) |
| 5 | server binds its own mandate: mint and bind a mandate for the employer's principal without the owner key | AIXBT, Mar 2025: operator access abused | paid [0x7e1b1fc2…6e96](https://testnet.metalntwx.com/tx/0x7e1b1fc206c3f4f6cf3dcad9b0ebce6929fb6ffa587d61a9fdc9a0af55fe6e96) | refused, `the` |
| 6 | stale attempt: a line is reopened as attempt 2, then the server pays attempt 1 as well | found by us, in our first design | paid [0xe08f4229…962e](https://testnet.metalntwx.com/tx/0xe08f4229f6710b3a9609e6b90511d4ce3f384afb36d81acade6e155ceb46962e) | refused, `mandate_revoked` [0xcdcee4d9…f79f](https://testnet.metalntwx.com/tx/0xcdcee4d988ed3ca6c807415fa8032ab165087002f3f5a011d977199048b1f79f) |
| 7 | stale approval: the batch is re-approved, then the server pays the line under the OLD approval | found by us, in our first design | paid [0xb136ffa9…5c81](https://testnet.metalntwx.com/tx/0xb136ffa9eb7012ad2e2662b75e5f70b906abcbde39cfbaf959e43753a8d05c81) | refused, `mandate_revoked` [0x056abf3f…f2e9](https://testnet.metalntwx.com/tx/0x056abf3fef5d0a2fae431f8c129c52f7ed7b61d4e0db9ded5366697ed28cf2e9) |

## A payroll, end to end

Recorded in [payroll-2026-11-25/](payroll-2026-11-25/): the approved batch, each credential file (never a pull key), the line report and the signed certificate. Result: **PASS**. The Airwallex fee step ran on the offline fake and is [SIMULATED]; the payments are real testnet payments.

| Line | Ledger state | Paid (USDZ) | Checks |
|---|---|---|---|
| noah | PAID | 0.11 | all passed |
| zoe | PAID | 0.1 | all passed |

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

- The chain, not the adapter, is the final enforcer. The adapter and the preflight add independent refusals before it.
- The proof covers every credential this server holds, each read back from the chain.
- A mandate caps each payment at the approved amount, and the proof flags any line paid for a different amount than approved.
- Pending and held pull outcomes are covered by tests against a chain double that prints the CLI's real text.
- Airwallex fees and the employer registry run on an offline fake and are labelled [SIMULATED]. Payments on chain are real testnet payments.
- 1 USDZ stands for USD 10 on the testnet, a fixed scale chosen so a faucet balance covers a payroll.
- The approver's device is a separate process and key, and it is the root of trust.
- Before signing, the device shows what it binds: the payee, the amount, one pull and the expiry.

## Tests

[test_alta.py](../tests/test_alta.py), [test_alta_device.py](../tests/test_alta_device.py), [test_alta_attacks.py](../tests/test_alta_attacks.py), [test_alta_verify.py](../tests/test_alta_verify.py), [test_alta_app.py](../tests/test_alta_app.py), [test_alta_findings.py](../tests/test_alta_findings.py), against [fake_chain.py](../tests/fake_chain.py), which prints the CLI's real output text and applies only the rules the spike measured. That includes the executor under every fault schedule of four release attempts, and the existing nine invariants run unchanged over chain payments.
