# Decisions

The choices that shape Ringfence, with the reason and what it costs. Each stays until a better reason is found.

## The model never touches money

**Decision.** The agent proposes. Code validates, prices, gates, sends and verifies. No tool takes a bank detail, and the employer is fixed by the harness before the model starts.
**Why.** Any model can be talked into paying the wrong account by a document it reads. The safe design assumes it will be.
**Cost.** The agent cannot fix a bad document by itself. It is flagged, and a person decides.

## No approve tool

**Decision.** Neither MCP server has a tool to approve. Approval is a person's signature on the exact batch.
**Why.** An agent that can approve its own run is only as safe as the agent. Without the tool, no prompt can reach it.
**Cost.** A person must be present for every run. That is the design: one signature, not one per payment.

## Bank details are bound by content, not by ID

**Decision.** Approval fingerprints the bank details. They are re-read before release, and each transfer carries them inline.
**Why.** Airwallex lets a payee's bank details change while keeping its ID, so an approval bound to an ID is bound to nothing ([F1](../FINDINGS.md#f1-approval-swap)).
**Cost.** One extra read per payee before release.

## No batch transfers

**Decision.** Every payout is its own transfer.
**Why.** A batch pays the payee's account as it is at submit, and the API cannot cancel it ([F5](../FINDINGS.md#f5-batch-payroll)).
**Cost.** More API calls per run.

## Request IDs are fixed before the first try

**Decision.** `sha256(run, employer, contractor, attempt)`, stored before the first call. The amount is not part of it. After a timeout Ringfence looks up and never resends.
**Why.** A retry with a new ID pays twice, and a payout cannot be pulled back ([F4](../FINDINGS.md#f4-a-retry-pays-twice)).
**Cost.** A genuinely changed amount needs a new attempt and a new approval.

## Separate accounts, not connected accounts

**Decision.** Each employer is its own Airwallex account in one organisation, reached by one scoped key.
**Why.** The sandbox blocks connected-account onboarding ("This account cannot onboard business/individual accounts"). The account-level isolation is the same: own balances, payees and global accounts, and cross-account calls refused.
**Cost.** One key reaches every employer, so isolation between employers rests on code. Moving to connected accounts changes only [`TenantClient._login`](../ringfence/awx.py#L85): log in as the platform and add `x-on-behalf-of`.

## `Decimal` for money, never float

**Decision.** All amounts are `Decimal`. Airwallex amounts are major units.
**Why.** A float cannot hold 0.1 exactly, and a payroll total must be exact ([money.py](../ringfence/money.py)).

## A pure gate with 25 refusal codes

**Decision.** `(action, facts) -> Allow or Deny(code)`, with no I/O, clock or model. A missing limit is a refusal.
**Why.** A pure function is testable exhaustively and cannot be influenced by a model. It has 100% branch coverage.

## A signed webhook is a hint

**Decision.** A valid webhook only triggers a re-fetch of the transfer.
**Why.** Truth is what Airwallex returns when asked, not what an event says.

## SQLite for the ledger

**Decision.** Append-only, hash-chained SQLite with triggers blocking `UPDATE` and `DELETE`.
**Why.** One file, no server, and tamper-evident. Right for a single-node sandbox.
**Cost.** Single-node. A shared database is on the [roadmap](../ROADMAP.md).

## One money worker thread

**Decision.** One thread performs every money operation in the app.
**Why.** No concurrent release, so no race between two releases of the same run.
**Cost.** Throughput is bounded. Payroll is bursty and deadline-driven, not high-volume.

## Pricing is a policy on a meter

**Decision.** The meter charges per landed payout and credits a return. The price is a function on top of it. Today it is a flat GBP 1.50.
**Why.** The gate checks only that the amount equals the expected amount, so tiers, percentages, floors and caps change one function ([fees.py](../ringfence/fees.py)).
