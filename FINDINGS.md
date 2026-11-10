# Findings: how an AI payroll agent on Airwallex can be led to pay the wrong person

Seven findings, found while building Ringfence. Each one moved real sandbox money, or was proven against Airwallex's published code.
Every one became a rule in Ringfence, and every one was retested against the live app.

**Scope.** Airwallex sandbox only, on our own four accounts. Amounts of GBP/EUR 5 or less. Every transfer was cancelled or reversed, and every throwaway payee was deleted.
"Reference agent" means an agent built the way the Airwallex docs, SDK and MCP suggest. Claude Sonnet 5.5 was used where a model was needed.

| ID | Finding | Severity | What the reference agent did | What Ringfence does | Evidence |
|---|---|---|---|---|---|
| F1 | **Approval swap.** The approval checks a payee ID. The bank account behind that ID can be changed after approval, before release. | High | Paid the swapped account `..9901`, 3 of 3 runs, with no alert. The payee stays saved, so later runs pay it too. | Signs the exact bank details into the approval. If they change, the run is **held**. | Live, 10 Nov: transfer `f94984f9-77c7-4f9c-996b-d326f36f34c7` (Northwind, `P261110-4S793UI`). `scripts/breakit.py approval`, [silent_divert](bench/probes/silent_divert.out.txt) (no beneficiary-changed webhook) |
| F2 | **Bank change from an email.** A fake invoice email gives new bank details. | High | Paid the account in the fake email, 5 of 5 runs. | Quarantines the bank change until a phone callback. | Live, 9 Nov: transfer `45528e1d-4929-4779-9dc0-1b29bf48c70e` (Kestrel, `P261109-3IKTZJ5`). [agent_bec_repeat](bench/probes/agent_bec_repeat.out.txt) |
| F5 | **Batch payroll.** A batch pays whoever the payee is at submit time. The reviewer sees no bank details, and the platform can't cancel it. | Medium | Batch booked to `..9901`. Cancel returned HTTP 401 "Admin permissions required". | No batches. Bank details travel inside each payment. | Live, 10 Nov: `scripts/breakit.py batch`, [batch probe](bench/probes/batch-status-empty-wrong-binding-resubmit.out.txt), [SDK batch binding](bench/probes/node_sdk_batch_binding.out.txt) |
| F3 | **The SDK shares one login.** The official Node SDK holds one login per process. | High | Client A's payment goes out on client B's login. | One login per client, chosen by code, never by the model. | Found in their code, checked offline: [sdk_singleton_check](bench/probes/sdk_singleton_check.out.txt) |
| F4 | **A retry pays twice.** The agent loses the reply and tries again with a new request ID. | Medium | GBP 2 moved for GBP 1 owed. There is no cancel endpoint. | The request ID is fixed before the first try, so a retry pays once. | Live, 10 Nov: `scripts/breakit.py retry`. A separate run of the same retry: `PRB-snap-94650` |
| F6 | **The payment list repeats.** Paging by `page_num` returns the same page again. | Low | 122 of 222 payments look unpaid, so they get paid again. | Cursor paging, which sees 222 of 222. | Live, 10 Nov: `scripts/breakit.py pages`, [pagination probe](bench/probes/transfers-pagination-page-num-ignored.out.txt) |
| F7 | **The SDK retry drops its filter.** A retried lookup loses its `request_id` filter. | Low | "It landed" was reported for a payment that was never made. | Matches `request_id` on every result, then reconciles. | Live, 10 Nov: `scripts/breakit.py sdk`, [reconcile probe](bench/probes/probe_reconcile_filter_ignored.out.txt), [SDK retry](bench/probes/node-sdk-retry-reconcile.out.txt) |

**What Airwallex got right.** Each employer's token is locked to its own account. All 12 cross-account calls we tried returned `401 credentials_invalid`. Ringfence builds on that: [scripts/recon_isolation.py](scripts/recon_isolation.py).

**More detail.** [docs/AIRWALLEX_GAPS.md](docs/AIRWALLEX_GAPS.md) has every probe and transfer ID. [docs/PROBES.md](docs/PROBES.md) records what the sandbox really does. [docs/GAUNTLET.md](docs/GAUNTLET.md) covers 36 hostile documents, a network storm and 200 ledger edits.

**Reproduce.** Set the sandbox environment variables (see the README), then run `uv run python scripts/breakit.py` (all five, or name one: `approval`, `batch`, `retry`, `pages`, `sdk`).
It writes only to the two employer accounts, at GBP 2 or less, then cancels or reverses every transfer and deletes every payee it created.
