# Where Airwallex's recommended agent stack sends money wrong

Live findings on the Airwallex sandbox, 3–6 Nov 2026. "The recommended stack" means what Airwallex tells an integrator or
an agent builder to use:
- the official `@airwallex/node-sdk`;
- the official `@airwallex/developer-mcp`;
- the AgentOS skills in `github.com/airwallex/airwallex-marketplace`;
- the API docs and guides.

**How to read the labels.**
- **Status**:
  - CONFIRMED: reproduced live and checked by independent verifiers who were asked to refute it.
  - FACT, LOSS NOT SHOWN: the API behaviour is real, but a verifier argued the money loss needs a step the docs don't recommend.
  - IN FLIGHT: the probe is still running.
- **None of these is an Airwallex security vulnerability.** No cross-tenant 2xx was ever observed. Tenant isolation held
  every time it was tested. These are API-design, SDK and integration-guidance gaps: places where following Airwallex's
  own advice puts money in the wrong place.
- **Safety.** Writes went only to Northwind and Kestrel, at GBP/EUR ≤ 5. Every transfer was cancelled where the API
  allows it, and every throwaway payee was deleted. Raw outputs are in `bench/probes/*.out.txt`.

## Summary

| # | Gap | Who it hurts | Status |
|---|---|---|---|
| 1 | Approval binds a beneficiary id; the id can be repointed in place while approval waits | Any human-in-the-loop agent (AgentOS "require manual approval") | CONFIRMED 3/3 |
| 2 | Batch transfers, pitched for payroll, pay the payee as it is at submit; the batch never shows bank details; an API key can't cancel a batch | Payroll on batches | CONFIRMED 4/4 |
| 3 | Charges / Connected Account Transfers docs say: on a duplicate `request_id`, retry with a **new** one | Platforms doing fee sweeps or employer top-ups | CONFIRMED live double funding |
| 4 | `GET /transfers` ignores `page_num`, which the payouts guide says to use | Every reconcile or "who's unpaid" job | CONFIRMED, 2 verifiers |
| 5 | The official Node SDK's auto-retry drops the query and headers of a GET | The docs' "look it up by request_id" recovery | CONFIRMED, 2 verifiers |
| 6 | The official MCP mints a fresh random `request_id` per create, strips error details, and makes the paying account an optional per-tool argument | Agents on the official MCP | Code CONFIRMED; payer trial IN FLIGHT |
| 7 | Airwallex Pay (wallet-to-wallet) settles to PAID in about 2 s, can't be cancelled, and its snapshot has no bank details | Anyone whose controls check bank details | CONFIRMED |
| 8 | `duplicate_request_id` ignores payload differences | Retry logic | CONFIRMED (3 Nov) |
| 9 | `request_id` dedupe is per account, including batches | Multi-account platforms | CONFIRMED |
| 10 | PAID is not final: PAID → FAILED is real | Anyone who closes a run at PAID | CONFIRMED |
| 11 | A transfer can't be cancelled for a few seconds after create | Recall-on-detect controls | CONFIRMED |
| 12 | A failed transfer auto-cancels in 0.14 s, so one return produces two terminal events | Webhook handlers | FACT, LOSS NOT SHOWN |
| 13 | `GET /beneficiaries/{id}` returns **200 with an empty body** for a deleted, random or other-employer id | Every existence check | FACT, LOSS NOT SHOWN |
| 14 | The documented `?company_name=` filter is ignored and returns every payee; AgentOS's dedupe step relies on it | AgentOS beneficiary skill | FACT, LOSS NOT SHOWN |
| 15 | The batch items list returns 200 `{"items": []}` for a batch you don't own or that doesn't exist | Batch recovery | FACT, LOSS NOT SHOWN |

The first seven are the video. 8–11 are the supporting cast. 12–15 are honest footnotes.

---

## 1. Approval approves an id, and the id can change underneath it

**Recommendation broken.** AgentOS guidance: "Require manual approval for tool calls" for money-moving writes. The
approval card shows a `beneficiary_id`, an amount and a currency.

**Break.** `POST /beneficiaries/{id}/update` rewrites the bank details and **keeps the id**. Airwallex's payouts webhook
list has no beneficiary-changed event, so nothing tells the integrator.

**Receipts** (`bench/market_agent.py approval`, `bench/results/market-approval-*.json`):
- Steelmanned baseline: Opus 5.5 at high effort, a best-practice prompt, `get_beneficiary` checked against the sheet,
  and a diligent approver checking id, amount and currency.
- 3/3 trials paid Ben's GBP 2 to **..9901**:
  - `22c0a5d8-acbf-4bd6-8a35-6369d04d68e8`
  - `49a84d09-2d5e-4c46-8436-0e69c75dc7de`
  - `0d0b978b-3393-4c92-a8f6-141e19477689`
- In-place edit, same id, new destination: `94d17365-…`, T1 to ..5678, then T2 to ..9901 (`23bddced-…`) (`scripts/probe_inplace.py`).

**Why it matters.** This is the API form of the Storm-2755 "payroll pirate" attack
([Microsoft, 9 Apr 2026](https://www.microsoft.com/en-us/security/blog/2026/04/09/investigating-storm-2755-payroll-pirate-attacks-targeting-canadian-employees/)):
the attacker changes the deposit account, and every id-based control still passes.

**What held.** Each transfer snapshots its destination at create, including future-dated ones (`978f0b6f…`).

**Ringfence's fix.** It pins a fingerprint of the bank details at approval, re-reads the payee live at release and holds
on drift (3/3 HELD). After create, it compares each transfer's own snapshot against the pin and cancels a mismatch
(3/3 CANCELLED: `0aaad98f…`, `17c78b76…`, `e32f97fd…`).

**Video line.** "Airwallex's guidance says put a human on every payment. We did. The human approved the right id, the
right amount, and the money went to a different bank account, three times out of three."

## 2. Batch payroll pays whoever the payee is at submit, and you can't see or stop it

**Recommendation broken.** "Create a batch transfer"
([docs](https://www.airwallex.com/docs/payouts/batch-transfers/create-a-batch-transfer.md)) pitches batches for "payroll
runs and supplier payments", including for platforms via `x-on-behalf-of`, and routes API batches through the approval
workflow.

**Break.** Create a batch, add an item for the payee at ..4444, edit the payee in place to ..9901, then submit.

**Receipts** (`bench/probes/batch_draft.py`, `snapshot_timing.py`, outputs alongside): **4/4 booked to ..9901.**
- `f5bd21a8-f6d5-4972-bf83-f6b811733893`
- `f1cd2e93-6bd0-4956-a11e-7c87c929d006`
- `66404ad8-5105-4884-bfa6-ab72b3750485`
- `f72b2134-357f-4e3b-bdd3-a13cb42801c1`

**Three compounding problems:**
- **The batch never shows a reviewer where the money goes.** The item preview (`GET /batch_transfers/{id}/items` →
  `transfer_draft`) carries no bank details at any stage.
- **An API integration can't stop a submitted batch.** `POST /batch_transfers/{id}/cancel` with the scoped key returns
  401 "Admin permissions required", and admin keys are deprecated and disabled. The only recourse is to cancel the
  spawned transfers one by one, while they're still cancellable.
- **Batches work under an employer token** (BOOKED in 4 s: batch `e9fa7e41…`, transfer `358ddce5…`), so this applies to
  multi-employer platforms.

**Fix that works.** Put the bank details inline in the batch item instead of a `beneficiary_id`: `05bf3293-e9b9-43b4-ab30-bd47ae282b0b`
went to ..8888 with `beneficiary_id` null (`batch_inline.py`). With no id, there is nothing to repoint.

**Not tested.** Whether a batch waiting in the approval workflow binds at submit or after approval. That needs the policy
enabled in the web app.

**Video line.** "Airwallex's payroll batch API paid the edited account four out of four times, and the batch preview
never shows a bank account to check."

## 3. The docs tell platforms to double-charge on a lost response

**Recommendation broken.** "Error codes for Charges and Connected Account Transfers"
(`api/scale/charges/create`, `api/scale/connected_account_transfers/create`), row `request_id_duplicate`, verbatim:
"Retry the request with a new `request_id`." The live error message agrees: "please use a different request_id for this
request".

**Break.** A create lands, the response is lost, and the integration retries the documented way. That is a second,
independent movement of money.

**Receipts** (`bench/probes/charges-request-id-duplicate-new-id*.py`, `.out.txt`):
- CA transfer Northwind → Kestrel, GBP 1: `tr_iJL2nwzWO46QVtihKjf6OQ` SETTLED. An identical retry returned 400
  `request_id_duplicate` with `details.source_id`.
- The docs-following handler moved **GBP 2 for a GBP 1 payable**: `tr_EVfI4fFUMiKaByQv2_pW4w` and
  `tr_i7K2mR5GNpqv0iirL3-rGg`, both SETTLED.
- CA transfers settle instantly and have **no cancel endpoint**. Reversal needs a transfer back from the receiving
  account: `tr_xz4paWGePKWy7EOocfwB8g` and `tr_fWTEfm3vPqaL6Wp2KQnaTQ`, net 0.
- **The same error is spelled two ways.** Transfers return `duplicate_request_id` with `details.id` (control
  `04e82a15-acb3-43a3-8095-90f13af90186`). CA transfers return `request_id_duplicate` with `details.source_id`. The
  transfers reference calls the second spelling "legacy", but it is live on CA transfers. A generic "adopt the original
  on duplicate" handler misses one of them.
- Charges itself returned 400 "Permission denied." on this sandbox, so that half is docs-only.

**Ringfence.** It never mints a new id: ids are deterministic per run, tenant, contractor and attempt. On the CA
spelling today it fails closed, but leaves the fee unrecorded. The normaliser is in the Sonnet handoff.

**Video line.** "Airwallex's own error table says: if you see a duplicate, retry with a new id. We did exactly that, and
it moved the money twice. Instantly, with no cancel."

## 4. The payouts guide's pagination doesn't paginate

**Recommendation broken.** The payouts guide, "Step 3: retrieve transfer details", says to "use … the pagination
parameters (page_num, page_size) to refine the results".

**Break.** Live, `GET /transfers` **ignores `page_num`**:
- `page_num` 0, 1 and 2 return the same 100 ids (sha `0be7d0b5bf3717e8`), with no `has_more`.
- The real pager is an undocumented cursor: `page=0`, then follow `page_after`.
- `page_num` does work on `/beneficiaries`, so the inconsistency is in `/transfers` only.

**Receipts** (`bench/probes/probe_transfers_paging.py`, `transfers-pagination-page-num-ignored.out.txt`; 2 independent
verifiers re-ran it read-only and could not refute it):
- Reproduced on Northwind and on Kestrel.
- A reconcile written to the guide, run over Northwind's real history, reports **99 of 199 transfers as unpaid**. 66 of
  those are live debits that a re-pay job would pay a second time.
- The official MCP's `list_transfers` sends no query parameters at all
  (`@airwallex/developer-mcp@0.3.0-beta.13 dist/tools/listTransfers.js`).

**Ringfence.** Its own Proof paged with `page_num` too, and looped forever past 100 transfers. That is fixed in the
working tree with the cursor pager (see the handoff).

**Video line.** "Follow Airwallex's guide to check who's been paid, and half of Northwind's payments disappear. Re-pay
the missing ones, and you've paid 66 people twice."

## 5. The official Node SDK's retry throws away the question

**Recommendation broken.** The `transfers/create` reference says that when you're unsure of the outcome, "get a payout
with this request_id to find out". The `@airwallex/node-sdk` README says the SDK automatically retries timeouts and
network errors.

**Break.** `dist/client/apiClient.js:157` retries with `this._request(method, url, config, data)`, but the signature at
:172 is `_request(method, url, data, config)`. On a GET, `data` is undefined, so the retry sends **no params and no
per-call headers**: the `request_id` filter and `x-on-behalf-of` are both dropped. `retry: 0` can't turn it off, because
the code reads `config.retry || 1`. The typed `payouts.transfers.getTransfers` goes through the same path. The bug is in
both published dist-tags (`latest` 2.0.0-beta.4 and `beta` 2.1.0-beta.5).

**Receipts** (`bench/probes/node-sdk-retry-reconcile.py`, `.out.txt`; 2 verifiers read the source line by line and
re-ran the live GETs):
- First attempt, `GET /transfers?request_id=prb-never-used-000001`: 0 items.
- The SDK's retry, the same GET without its filter: **201 items**, none with that `request_id`.
- So a "non-empty means it landed" check marks a never-paid employee as paid, or binds another employee's transfer to
  the line.
- Under the README's platform token plus `x-on-behalf-of` pattern, the retry reads the **platform's own ledger** instead
  of the employer's.
- Offline, a shared SDK client sent Northwind's batch-status read as Kestrel and got `{"items": []}`
  (`node_sdk_batch_binding.out.txt`: `wrong_binding=true`).

**Partly shown.** A 409 `request_pending` carries no transfer id (two creates 16 ms apart; `30cc77fb…`, CANCELLED). If
the POST retry ever gets fixed, a slow create can surface as an error even though it booked. That is a mechanism, not
an observed double pay.

**Ringfence.** `transfer_by_request` matches the `request_id` on each item instead of trusting the server filter, and its
GET retry re-sends the same params. Run offline against a fake that ignores the filter entirely: 0 duplicates.

**Video line.** "Airwallex's own SDK, on one network blip, asks 'did this payment go through?' without saying which
payment, and gets back 201 that look like yes."

## 6. The official MCP: no idempotency, no error details, payer chosen by the model

**Code facts** (`@airwallex/developer-mcp@0.3.0-beta.13`, read on unpkg, confirmed by the node-sdk verifiers):
- `create_transfer` sets `request_id: uuid.v4()` on **every call** (`dist/tools/createTransfer.js` ~L59). Retrying a
  tool call is a brand-new payment, so Airwallex's idempotency can't help.
- `errorHandler.js:16` builds the tool's error text from status and message only. A 409 `request_pending` tells the
  model nothing it could use to find the original.
- `create_transfer`, `get_balances`, `list_beneficiaries` and `list_transfers` each take their **own optional**
  `connected_account_id`. When it's left out, the call runs as the server's default account. The paying account is a
  free argument the model fills in per call, and nothing ties it to whose payroll it is.
- It accepts either `source_amount` or `transfer_amount`, with nothing binding which unit the human approved.

**Why the payer matters.** Read-only live facts:
- 10 beneficiaries share name and last-4 between Northwind and Kestrel.
- A transfer object carries no account field.
- `wallet_info.account_name` is "Sandbox Business" on all 4 accounts (a sandbox naming artifact).

So an approver checking name, last-4, amount and currency can't tell which employer pays.

**Status.** The code facts are confirmed. The live model trial (`bench/probes/official-mcp-payer-unbound.py`) had a
harness bug in its first trial (moved to invalid) and is being re-run.

**Video line, only if the trial lands.** "The official MCP lets the model pick whose money pays, per call, and the
approval card can't show it."

## 7. Airwallex Pay: instant, irreversible, and invisible to bank-detail checks

**Recommendation broken.** Transfers via Airwallex Pay: "Flight time Instant", "Funds will be immediately deducted". The
payee is identified by account number plus name from `GET /account/wallet_info`.

**Receipts** (`bench/probes/sibling-wallet-repoint-airwallex-pay.py`, `.out.txt`):
- A Northwind transfer to Kestrel's wallet reached **PAID in 2.11 s**.
- Cancel returned 400 `update_unsupported`; the status stayed PAID.
- Kestrel was credited GBP 1, Northwind debited GBP 1. Not reversed: it is a 1 GBP movement between our own accounts.
- The transfer's snapshot keys are `['digital_wallet', 'type']`, with **no `bank_details`**, so any control that compares
  bank details has nothing to compare.

**What held.** Switching an existing bank payee to a wallet in place is refused: 400 `beneficiary_switch_unsupported`.
So the repoint-in-place attack does not extend to this rail, and an attacker needs a new payee.

**Ringfence gap.** Ringfence's snapshot checks skip a missing `bank_details` (fails open). This is in the handoff.

**Video line.** "On Airwallex Pay, a payment to another employer's wallet was final in two seconds. No recall."

## 8–11. Documented behaviours that break naive agents

| Gap | Receipt |
|---|---|
| **8. `duplicate_request_id` ignores the payload.** The same id with a different amount returns the original, and `details.id` points at it. An adopter that doesn't compare amount, currency and payee adopts the wrong payment. | 3 Nov, `docs/PROBES.md`. Ringfence's `_adopt` compares all three. |
| **9. Dedupe is per account, batches included.** Kestrel reused Northwind's batch `request_id` and item `request_id` and BOOKED. | `28b0802a…`, transfer `bc1460be…` (CANCELLED). Bound correctly, Northwind's reuse was caught (`request_id_used`, `f0cbff0d…`). |
| **10. PAID is not final.** SCHEDULED → SENT → PAID → FAILED, with reason "90802: Beneficiary bank returned". The docs say so too. | CLAUDE.md sandbox notes; Ringfence turns it into RETURNED, which needs a new approval. |
| **11. A transfer can't be cancelled right after create.** 400 `update_unsupported` for a few seconds, which is exactly when a recall-on-detect control needs it. | Race runs `92c4eda7…`, `7ce0f4ef…`, `36e8b244…` (detected, not cancelled before the retry existed). |

## 12–15. Real API facts, money loss not shown

| Gap | Receipt | Why the loss was refuted |
|---|---|---|
| **12.** One bank return produces FAILED, then an automatic CANCELLED 0.14 s later (two documented events). | `b2452320-45e8-4777-97dc-d78ce2c38c43` | The docs warn about the auto-cancel. Re-paying on both events is not advised. The `failure` object (code 90802) survives the cancel. |
| **13.** `GET /beneficiaries/{id}` returns 200 with 0 bytes for a deleted id, a random uuid, or another employer's id. A 404 would be correct. | `probe_ben_fail_open.out.txt` | An existence check that treats 200 as "exists" fails open. But a create against that id is refused (400 `045`). It crashed Ringfence's release check with a TypeError (fixed in the working tree). |
| **14.** `?company_name=` is documented ("Filter on company name") but ignored, and returns all payees. COMPANY payees don't even store `company_name`. AgentOS `beneficiary-creation/SKILL.md` Step 9: "Search by name/company_name… If match exists, user decides: skip, update". | `Probe Co`: `?company_name=Probe%20Co` → 16, `?name=Probe%20Co` → 1 | A human still has to choose "update" on a plainly different payee. |
| **15.** `GET /batch_transfers/{id}/items` returns 200 `{"items": []}` for another account's batch or a nonexistent one. `GET /batch_transfers/{id}` correctly returns 404. | `e9fa7e41…` read under Kestrel | The docs resubmit only BOOKING_FAILED items, and an empty list has none. A wrong-bound resubmit with Northwind's beneficiary id fails at 400. |

## What Airwallex got right (say this on camera; it buys credibility)

- **Tenant isolation.** Employer A's token with `x-on-behalf-of` B returns 401 `credentials_invalid`. Kestrel's token
  paying to Northwind's beneficiary id returns 400 `validation_failed`. No cross-tenant read or write ever succeeded.
- **Destination snapshots.** Single transfers, including future-dated ones, keep the destination they had at create.
- **The in-place switch to a wallet is refused** (`beneficiary_switch_unsupported`).
- **`request_id` dedupe within an account.** It did most of the retry safety in the bench, for both systems.

## One-line thesis for the film

Airwallex's controls bind **pointers**: a beneficiary id, a request id, an account chosen per call. The money follows
the **content** behind the pointer. Every gap above is a place where the pointer stayed the same and the content didn't.
Ringfence binds the content.
