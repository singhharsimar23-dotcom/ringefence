# Draft: private findings note to Airwallex (send before the video or repo is public)

**To:** devhelp@airwallex.com, plus Airwallex's security / responsible-disclosure channel if one is listed on
airwallex.com (check before sending). **Optional CC:** the hackathon organisers.
**Attach:** `docs/AIRWALLEX_GAPS.md` (every transfer id). Fill in the two `[ ]` fields before sending.

---

**Subject:** Sandbox findings from the Agentic Banking Hackathon: SDK, MCP and docs fixes, plus hardening notes

Hi Airwallex team,

I'm Harsimar Singh, a shortlisted participant in the Agentic Banking Hackathon (Kit 06, multi-employer payroll).
While building a payroll agent on your sandbox, I found nine places where money can go to the wrong place, go
twice, or be wrongly reported as paid. The table says which ones we showed live and which come from reading code.

They fall into two kinds:
- **Honest mistakes.** A developer follows Airwallex's own SDK, MCP or docs, and ordinary network blips or
  retries cause the loss.
- **Fraud.** Someone who can edit a payee (for example through a phished agent or a leaked key) redirects pay,
  and nothing records the change.

The list is ranked by how likely the loss is and whether it can be undone. Each item has a fix. Everything was
verified on the sandbox or in your published packages; the two code quotes were re-checked on 9 Nov.

Our own severity estimate is in the table. None of these breaks a security boundary: every one needs either the
integrator's own credentials or the integrator's own code to act on what it gets back. You may reasonably classify
several as docs fixes or by-design behaviour.

| # | Finding | Kind | Our estimate | Shown live? | Fix size |
|---|---|---|---|---|---|
| 0 | Node SDK is a process-global singleton: constructing a 2nd `Airwallex` re-binds the 1st, so a call on instance A goes out with B's token (wrong payer) | Honest mistake | **High** (multi-account integrators) | Verified offline (token attached), not fired at server | small |
| 1 | Docs: on `request_id_duplicate`, "retry with a new `request_id`", which moved money twice, instantly, with no cancel | Honest mistake | Medium | Yes (double payment) | 1 doc row |
| 2 | Node SDK retry swaps two arguments, so "did it land?" is re-asked without its filter | Honest mistake | Medium | Wrong result yes; money loss no | 2 lines |
| 3 | Developer MCP `create_transfer` mints a new `request_id` on every call | Honest mistake | Medium | Code only | ~3 lines |
| 4 | A payee's bank account can be changed in place with no event or audit field, and an approved payment pays the new account | Needs payee write access | Low–Medium (hardening) | Yes (3/3) | webhook + field |
| 5 | Batch transfers show no bank details, pay the payee as it is at submit, and an API key can't cancel them | Needs payee write access | Low–Medium | Yes (4/4) | API / UI |
| 6 | `GET /transfers` ignores `page_num`, which the payouts guide says to use | Honest mistake | Medium–Low | Yes (read-only) | doc line or API |
| 7 | `GET /beneficiaries/{id}` and the batch items list return 200 with an empty body for ids that don't exist or aren't yours | Both | Low | return 404 |
| 8 | `?company_name=` on the beneficiary list is ignored, but the AgentOS dedupe step relies on it | Honest mistake | Low | filter or doc |

### 0. The Node SDK is a process-global singleton — the wrong account pays

`@airwallex/node-sdk@2.1.0-beta.5` (and `latest` 2.0.0-beta.4). The `Airwallex` constructor registers itself as a
module-level singleton (`apiClient.initialize(this)`), and the API classes (e.g. `payouts.transfers`) call that
module singleton, not the instance you built. The request interceptor reads the token from
`this.getAirwallex().token`, i.e. from the **last-constructed** instance.

The README documents building a client per account (the `accountId` option on a scoped key spanning several
accounts) — which is exactly the multi-tenant payroll pattern. If an integrator builds one client per employer,
every call routes through whichever client was constructed last.

- **Verified offline (9 Nov, `bench/probes/sdk_singleton_check.js`, `.out.txt`):** construct A (`acct_AAAA`) then B
  (`acct_BBBB`), give each a sentinel token, then call `A.payouts.transfers.createTransfer(...)`. The request routed
  through the module singleton and would attach **B's token**. The module singleton's `accountId` was `acct_BBBB`.
- **Honest scope:** I verified *which token the SDK attaches* (no network call). I did **not** fire it at the server,
  so I'm not claiming a completed cross-account payment — but a transfer created with B's scoped token executes on
  B's account, i.e. the wrong employer pays (or it 401s). A single-instance integrator is unaffected.
- **Fix:** make `Airwallex` instance-scoped — the API classes should use `this` / the instance's own client, not a
  module-level singleton. Until then, document loudly that only one `Airwallex` instance per process is supported,
  and route multi-account calls through `x-on-behalf-of` on that one instance.

(Two independent source reviews reached this; the offline test above confirms the token binding. Please reproduce
with a two-instance live call before you classify it.)

### 1. The documented recovery for a duplicate request pays twice

"Error codes for Charges and Connected Account Transfers", row `request_id_duplicate`: *"Retry the request with a
new `request_id`."* The live error message says the same ("please use a different request_id").

- **Effect (live):** CA transfer Northwind → Kestrel, GBP 1, settled (`tr_iJL2nwzWO46QVtihKjf6OQ`). We then
  simulated a lost response and followed the documented recovery, which moved **GBP 2 for a GBP 1 payable**
  (`tr_EVfI4fFUMiKaByQv2_pW4w`, `tr_i7K2mR5GNpqv0iirL3-rGg`, both SETTLED). CA transfers settle instantly and have no
  cancel, so we reversed it by hand.
- **Fix (docs):** *"The original request already succeeded. Fetch it using `details.source_id` and treat it as the
  result. Use a new `request_id` only for a genuinely new payment."*
- **Related:** CA transfers return `request_id_duplicate` + `details.source_id`, while transfers return
  `duplicate_request_id` + `details.id`. The reference calls the first spelling "legacy", but it is live. A handler
  written for one spelling misses the other.

### 2. Node SDK: the retry swaps two arguments and drops the query

`@airwallex/node-sdk@2.1.0-beta.5` (also `latest` 2.0.0-beta.4), `dist/client/apiClient.js`:

```js
// retry path
const response = await this._request(method, url, config, data);
// signature
async _request(method, url, data, config) {
```

On a GET, `data` is undefined, so the retry sends **no query params and no per-call headers**. That drops
`request_id` and `x-on-behalf-of`. Separately, `config.retry || 1` means `retry: 0` can't turn retries off.

- **Effect (live):** `GET /transfers?request_id=<never used>` returned 0 items. The SDK's retry of the same call
  returned **201 items**, none with that request_id. The reference docs say to recover from an unknown create by
  looking it up by `request_id`, so an integrator who treats a non-empty result as "it landed" would mark a
  never-paid employee as paid. We showed the wrong result, not a resulting loss. Under the README's
  platform-token + `x-on-behalf-of` pattern, the retry reads the platform's own ledger instead of the connected
  account's.
- **Fix:**
  ```diff
  - const response = await this._request(method, url, config, data);
  + const response = await this._request(method, url, data, config);
  - const maxAttempts = this.getAirwallex().config.retry || 1;
  + const maxAttempts = this.getAirwallex().config.retry ?? 1;
  ```
  It's worth adding a regression test that asserts the retried request keeps the same params and headers.

### 3. Developer MCP: `create_transfer` mints a new `request_id` on every call

`@airwallex/developer-mcp@0.3.0-beta.13`, `dist/tools/createTransfer.js`: `request_id: (0, uuid_1.v4)()`, and
`request_id` is not in the input schema. Agents retry tool calls routinely (timeouts, client restarts, a model
re-issuing a call), and each retry would be a fresh, independent transfer. This is from reading the code; we did not
run a live double payment through the MCP. Also, `errorHandler.js` builds the tool error from
`error.status || error.statusCode || 500` and the message only. The SDK appends `details` **only when it is an
array**, so a `duplicate_request_id` whose `details` is an object `{id: ...}` is dropped — the exact field the model
would need to recover the original. And a timeout/network error has no `.status`, so it reaches the model as
"(500)", an unknown outcome presented as a failure. Contrast, in the same package: `createBillingProduct.js`
already exposes an optional `request_id` ("Optional idempotency key"); only money-moving `create_transfer` omits it.

- **Fix:** add an optional `request_id` input (10–50 chars) and use `args.request_id ?? uuid.v4()`. Tell the agent in
  the tool description to reuse the same `request_id` when it retries the same payment. Include `details` in error
  text so the model can see `details.id` / `details.source_id`.

### 4. A payee's bank account can change silently under an approved payment

`POST /beneficiaries/{id}/update` rewrites the bank details and keeps the id. The beneficiary object has no
`updated_at` or version, and there is no beneficiary-changed webhook. The AgentOS guidance says to "require
manual approval" for money-moving tool calls, and that approval shows id + amount + currency.

- **Effect (live):** a strong model (Opus 5.5) with a diligent approver checking id, amount and currency. The payee's
  bank account was edited while approval was pending, and **3 of 3** approved payments went to the edited account
  (`22c0a5d8-acbf-4bd6-8a35-6369d04d68e8`, `49a84d09-2d5e-4c46-8436-0e69c75dc7de`,
  `0d0b978b-3393-4c92-a8f6-141e19477689`). To be precise about detectability: each `/transfers` item does carry a
  `beneficiary.bank_details` snapshot, so a reconciler that diffs snapshots across runs **can** spot the change.
  What's missing is anything *proactive* — no `beneficiary.updated` event, no `updated_at`/version on the payee —
  and the in-flight approval shows only the id. The edit needs write access to the payee (the account's own
  credentials), so we see this as a detection/hardening gap, not a bypass. It is the step Microsoft's April 2026
  "payroll pirate" write-up (Storm-2755) describes attackers targeting.
- **Fix:** a `beneficiary.updated` webhook, plus `updated_at` / `version` on the object. Better still, let an
  approval or a transfer pin the destination it expects (for example an expected account fingerprint) and
  reject the transfer on mismatch.

### 5. Batch transfers: destination invisible at review, bound at submit, not cancellable by API

Batch transfers are pitched for payroll. The batch review shows no bank details. Editing a payee after adding it
to a batch and then submitting pays the edited account (**4 of 4**: `f5bd21a8…`, `f1cd2e93…`, `66404ad8…`,
`f72b2134…`). Cancelling a submitted batch with an API key returns "Admin permissions required", so the only stop is
cancelling each spawned transfer one by one.

- **Fix:** show the destination per item in the batch view, snapshot destinations when items are added, and allow
  a scoped key with transfer permission to cancel its own batch.

### 6. `GET /transfers` ignores `page_num`

The payouts guide (Step 3) says to use `page_num` / `page_size`. On `/transfers`, `page_num` 0, 1 and 2 return the
same 100 ids with no `has_more`. The working pager is the undocumented `page` / `page_after` cursor. `page_num`
does work on `/beneficiaries`. The MCP's `list_transfers` sends no paging params at all.

- **Effect (live, read-only):** a reconcile written to the guide, run on one account's history, reported 99 of 199
  transfers as unpaid. 66 of those were real debits that a re-pay job would pay again.
- **Fix:** document the cursor for `/transfers`, or honour `page_num` there.

### 7. Fail-open reads

`GET /beneficiaries/{id}` returns 200 with an empty body for a deleted, random or other-account id. The batch items
list returns 200 `{"items": []}` for a batch you don't own or that doesn't exist. Code that treats 200 as "exists"
or "empty" is misled. **Fix:** 404.

### 8. Unknown query filters on `/beneficiaries` are silently ignored

`GET /beneficiaries?company_name=...` returns every payee. This isn't limited to `company_name`: an unknown
`?status=NONEXISTENT_STATUS_XYZ` also returned the full list unchanged (15 vs 15, verified 9 Nov). So the endpoint
ignores filters it doesn't recognise instead of rejecting them, which silently returns more than the caller asked
for. The AgentOS beneficiary skill relies on `company_name` to dedupe, so it may create duplicate payees or pick
the wrong one. **Fix:** honour documented filters and reject unknown query params with a 400.

### 9. MCP `create_payment_link` is not atomic, has no idempotency, and emails an arbitrary address

`@airwallex/developer-mcp@0.3.0-beta.13`, `dist/tools/createPaymentLink.js`: it creates the link, then POSTs
`/pa/payment_links/{id}/notify_shopper` with a model-chosen `shopper_email`, inside one try block, with no
`request_id`. If notify fails or times out, the link already exists but the model gets an error and no id, so a
retry creates a duplicate. Because `shopper_email`, `title` and `description` are model-set, a prompt-injected
agent can make Airwallex send a payment email to any address — a possible phishing/exfiltration channel. Sandbox
only in this package. **Fix:** make it idempotent (accept `request_id`), and separate or constrain the
notify step so the recipient isn't free-form model input.

### 10. MCP `get_fx_quote` is labelled read-only but performs a POST

`dist/tools/getFxQuote.js` sets `readOnlyHint: true` but calls `POST /api/v1/fx/quotes/create`. An MCP client
that auto-approves read-only tools will auto-approve a state-creating call. (The quote can't convert funds, so the
blast radius is small.) **Fix:** set `readOnlyHint: false`. More broadly, `create_transfer` has no
`destructiveHint`/`idempotentHint`, so clients can't reason about which tools move money.

### What held

Tenant isolation was solid in every test (cross-account tokens get 401 `credentials_invalid`). Amount, payer and
FX-quote binding were enforced. A cancelled transfer refunded to the penny. Single transfers snapshot their
destination at create. We tested whether the MCP's per-call payer argument leads a model to pay from the wrong
account, and we could **not** reproduce it (0/17), so we make no claim there.

### Scope and publishing

Sandbox only, our own org accounts, amounts of GBP/EUR 5 or less. Every test transfer was cancelled or reversed
and every test payee deleted. Our hackathon video mentions #4 for about 40 seconds as "the gap our design closes".
It does not use the word vulnerability and gives no reproduction steps. If you'd like us to hold or reword
anything, please tell me by [12 Nov]. Submission closes 15 Nov. I'm happy to open PRs for #2 and #3 if the repos
accept them.

Thanks for the sandbox and the hackathon.

Harsimar Singh
[contact]
