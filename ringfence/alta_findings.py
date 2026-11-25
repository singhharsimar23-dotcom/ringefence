"""Every defect found while building Alta settlement, how it was broken, and what fixed it. The /alta page, the MCP's
attack_report, the README and docs/ALTA_SETTLEMENT.md all state these; tests/test_alta_findings.py checks that each named
test exists, so a finding cannot outlive its proof."""
from __future__ import annotations

FINDINGS = [
    {"id": "A1", "title": "A reopened line could be paid twice",
     "where": "Ringfence's first Alta design",
     "broke": "A line is reopened as attempt 2 and a second credential is signed. Attempt 1's credential stays bound and unspent, "
              "and the server still holds its pull key, so both credentials are payable: the contractor is paid twice.",
     "fixed": "The device revokes every earlier attempt before it signs the next one, and refuses to sign a line whose earlier "
              "attempt already paid. Release preflight refuses while any earlier attempt could still pay. The auditor checks it.",
     "tests": ["test_the_stale_attempt_credential_is_a_double_pay_and_preflight_blocks_it", "test_device_revokes_the_earlier_attempt_before_it_signs_the_next"],
     "attack": 6},
    {"id": "A2", "title": "A renewed approval left the old credentials payable",
     "where": "Ringfence's device, found by its own test",
     "broke": "The batch is approved again after a change. The credentials signed for the first approval still carry a pull key on "
              "the server, so the server can pay a line under an approval the human has since replaced.",
     "fixed": "When a credential no longer matches the current approval the device revokes it on chain and sets it aside before it "
              "signs the new one. Preflight also refuses any credential whose signed description is not the current batch hash.",
     "tests": ["test_a_renewed_approval_retires_the_old_credential_of_an_unchanged_line", "test_a_credential_signed_for_another_batch_blocks_release"],
     "attack": 7},
    {"id": "A3", "title": "Alta's default mandate is broad",
     "where": "Alta CLI 0.3.3 defaults, measured on the testnet",
     "broke": "Without --payee a credential pays any address; without --max-occurrences it can be pulled until the budget is gone; "
              "the default life is 30 days. An agent wallet set up the usual way lets a compromised server pay any address, "
              "above or below what anyone approved, and pay the same line again (attacks 1 to 4, broad side).",
     "fixed": "The device never uses a default: one payee from its own book, cap equal to budget equal to the line, one pull, "
              "expiry no later than the approval. Preflight refuses any credential whose terms differ from the approved line.",
     "tests": ["test_a_credential_for_a_different_wallet_or_amount_blocks_release", "test_device_rejects_a_wallet_the_server_supplies"],
     "attack": 1},
    {"id": "A4", "title": "Alta's pull memory is local to one machine",
     "where": "Alta's own documentation, reproduced live",
     "broke": "Alta remembers a payment id on the disk that ran the pull. A retry from another machine signs a new payment, so a "
              "broad mandate with budget left is paid twice (attack 4, broad side).",
     "fixed": "A one-pull mandate makes 'once' a property of the chain, not of one disk. The executor never re-sends: after an "
              "uncertain pull it reads the credential's state, and a refusal that says the line is spent is adopted, not retried.",
     "tests": ["test_retry_from_a_fresh_home_cannot_pay_twice", "test_a_line_paid_from_another_machine_mid_release_is_adopted_not_failed"],
     "attack": 4},
    {"id": "A5", "title": "The live top-up holds the employer's owner key",
     "where": "Ringfence's earlier Metal top-up, still deployed",
     "broke": "The deployed top-up signs mandates on the server, so the server holds the Harbour owner key. Whoever controls the "
              "server can mint a mandate for any amount to any address and bind it. Settlement mode closes this by design.",
     "fixed": "In settlement mode the server never holds an owner key. The device signs and binds on another key and another "
              "process. The server's own attempt to bind a mandate for the principal is refused by the chain (attack 5). The "
              "existing top-up is unchanged and labelled; moving it onto the device is the next step.",
     "tests": ["test_server_side_never_signs_binds_or_revokes", "test_a_pull_key_cannot_revoke_or_bind"],
     "attack": 5},
    {"id": "A6", "title": "Slow signing made credentials outlive the approval",
     "where": "Ringfence's device, found by the first live payroll",
     "broke": "The device worked out the credential lifetime once, then created and bound one line after another. Each create and "
              "bind takes about a minute on the testnet, so the later credentials expired after the approval did. Preflight "
              "refused both lines (outlives_approval) and nothing was paid.",
     "fixed": "The lifetime is worked out again for each credential just before it is created, with 30 seconds of slack, and the "
              "device refuses a line when the approval has run out while it was signing.",
     "tests": ["test_every_credential_expires_before_the_approval_even_when_signing_is_slow",
               "test_device_refuses_a_line_when_the_approval_runs_out_while_signing"],
     "attack": None},
    {"id": "A7", "title": "A payroll that paid nothing was certified as a pass",
     "where": "Ringfence's verifier, found by the same live run",
     "broke": "The same refused payroll produced a signed certificate saying PASS. Every line was consistent with the chain "
              "(no payment, none expected yet), but nothing had been paid, so a reader would take it for a settled payroll.",
     "fixed": "A certificate says PASS only when every line is paid. A consistent payroll that is not yet paid says INCOMPLETE, and "
              "the payroll script refuses to record anything but a PASS.",
     "tests": ["test_a_payroll_that_has_not_paid_is_incomplete_not_a_pass"],
     "attack": None},
    {"id": "A8", "title": "Every pull failed, and the error said the wallet was unfunded",
     "where": "Ringfence's Alta adapter, found by the same live run",
     "broke": "The adapter passed the pull key as --key on a pull. On the real CLI that flag names a funded key for refusal "
              "records, so every pull failed with 'm.key.json does not hold a 32-byte private key'. The adapter then reported "
              "any pull that failed without a stated reason as insufficient_funds, which pointed at the wrong cause. The "
              "offline fake accepted the flag, so no test saw it.",
     "fixed": "The adapter no longer passes --key on a pull (the CLI uses the pull key beside the credential). The fake chain now "
              "rejects the flag with the CLI's own error, so the mistake cannot come back unseen.",
     "tests": ["test_a_pull_never_names_the_pull_key_as_the_key_flag"],
     "attack": None},
]

LIMITS = [
    "The chain, not the adapter, is the final enforcer. The adapter and the preflight add independent refusals before it.",
    "Alta has no command that lists a principal's mandates, so the proof covers only credentials this server holds.",
    "A mandate caps a payment, it does not set it: a compromised server can pay a line less than approved, never more. The proof flags a line whose paid amount differs from the approved one.",
    "Pending and held pull outcomes cannot be forced on the testnet; they are tested against a fake chain that prints the CLI's real text.",
    "Airwallex fees and the employer registry run on an offline fake and are labelled [SIMULATED]. Payments on chain are real testnet payments.",
    "1 USDZ stands for USD 10 on the testnet, a fixed scale chosen so a faucet balance covers a payroll.",
    "The approver's device is a separate process and key. A compromised device is out of scope: it is the root of trust.",
    "Blind signing is reduced, not solved: the device shows what it binds, and the person still has to read it.",
]
