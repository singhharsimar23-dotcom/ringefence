# Live sandbox probes (3 Nov 2026)

Live results beat the spec. Each row says what was sent, what came back, and what changed in the fake or the code.
Scripts are in `scripts/probe_*.py` and re-runnable. P0, P3 (re-verified in T1), P6 (needs a tunnel) are not yet recorded here.

| # | Question | Result | Consequence |
|---|---|---|---|
| P1 | Transfer create with zero balance (Harbour AUD 0, AUD 10) | 400 `balance_insufficient` "insufficient Wallet balance". No transfer exists afterwards. Retrying the SAME request_id gives the same `balance_insufficient`, not `duplicate_request_id`, so **a rejected create does not burn the request_id**. | Fake: code is `balance_insufficient`; `rejected_create_burns_request_id` stays False. Executor: a rejected create may be retried with the same request_id. |
| P2 | When is the balance debited? (Kestrel USD 1) | Debited **at create** (SCHEDULED): 10,000,000 -> 9,999,999. Unchanged through SENT and PAID. A simulated FAILED credits it back at once. Same simulated transitions work under an employer token (P8). | `own_available` from `/balances/current` already excludes scheduled transfers. Fake `balance_debit_at="create"` is right. |
| P4 | Beneficiary corridors | AU/AUD LOCAL: `account_routing_type1=bsb`, `state` must be `AU-NSW` style (error 016 lists the options). DE/EUR: IBAN + `swift_code` validates for LOCAL and SWIFT. US/USD: `aba`, `bank_account_category` `Checking`. GB sort codes as in CLAUDE.md. | `demo/employers.json` corridors. Create response is `{id, nickname, payer_entity_type, transfer_methods, beneficiary}`: the id is `id`, not `beneficiary_id`. |
| P5 | FX under an employer token | Quote under Northwind and Harbour tokens works. Quotes are `usage: MULTI_USE`. Conversion response id is `conversion_id`, amounts come back as strings. A `sell_amount` quote gave the exact AUD drain (Harbour AUD 3000 -> 0). Northwind GBP->AUD 10: client_rate 1.912035, SETTLED, AUD balance 10. | Fake quotes are multi-use. Never rely on single-use quotes; the request_id is the idempotency key. |
| P7 | `GET /transfers?request_id=` under an employer token | Works, returns `{"items":[...]}` | Reconcile path confirmed. |
| P8 | Simulation transitions under an employer token | SENT, PAID and FAILED(`BENEFICIARY_BANK_RETURNED`) all work (Kestrel). | Scenarios can drive live transfers per tenant. |
| P9 | Bad token | Garbage bearer: 401 `unauthorized`. No auth header: 403 HTML. Cross-tenant `x-on-behalf-of`: 401 `credentials_invalid` (re-verified). | `awx.py` re-logs-in once on `credentials_expired` or `unauthorized`, never on `credentials_invalid`. |
| P10 | Pagination and `from_created_at` | `/transfers` returns only `items` (no `has_more`). `/beneficiaries` returns `items`, `has_more`, `total_count`. `from_created_at` accepts `...+0000`, `...Z` and a bare date. | Page `/transfers` by `page_num`/`page_size` until a short page. |
| P11 | Fee beneficiary on B and C; USD GA on Kestrel | GB 041907 / 07371376 validates and creates under Kestrel and Harbour. Kestrel US/USD global account created (ACTIVE) only with `required_features: [{currency: USD, transfer_method: LOCAL}]`; missing method is `field_required`, `ACH` is `invalid_argument` (must be LOCAL or SWIFT). A GA has no top-level `currency`; read `required_features[0].currency`. | Fake mirrors this. `setup_demo` must create GAs with `transfer_method`. |

State left on the sandbox by the probes: Harbour has an AU probe beneficiary and a fee beneficiary, AUD 0; Kestrel has a US probe beneficiary, a fee beneficiary and a USD GA; Northwind holds AUD 10.

## Live full run (3 Nov, step 10)
- `python -m ringfence --backend live demo`: Kestrel auto-released (2 PAID), Northwind approved with one FX leg (3 PAID), Harbour short, funded by a `[SIMULATED]` AUD 1240.17 deposit, approved, paid (3 PAID). 3 fee transfers (GBP 3.00 / 4.50 / 4.50), ledger chain OK, rerun is a no-op.
- GET `/beneficiaries/{id}`, GET `/deposits` fields and `/transfers?request_id=` all behave as the code assumes.
- A simulated deposit is not matchable for ~2 s after creation (it showed up SETTLED right after). The orchestrator is polled, so a miss is just a later tick; the demo loops with a 2 s sleep.

## Live E2E from reset (3 Nov, T3 build)
- Via the HTTP API only: reset, start, approve Northwind, Harbour top-up scenario, approve Harbour. All three lanes DONE, isolation report ok, chain ok, three certificates VALID.
- Gap found by tests, fixed: a short or split deposit used to close the funding request and strand the run. Requests now stay open until deposits with the reference cover them.
- P3 (PENDING deposit availability), P6 (webhooks, needs a tunnel) and the live Claude path are still unverified.
