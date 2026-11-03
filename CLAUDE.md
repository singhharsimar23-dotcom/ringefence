# Ringfence: Multi-Employer Payroll Executor (Airwallex Agentic Banking Hackathon, Kit 06)

Payroll agent for several employers on the Airwallex sandbox. Deadline: 15 Nov 2026, 11:59 PM PST (extended in Slack; HackerEarth still says 13 Nov).
Submission: working demo, video under 5 minutes, repo link with setup steps. A private repo shared with judges is OK, and a local demo is OK. AWS is not required.
Plan to submit by 13 Nov. Product plan, judging criteria and demo script: `docs/PLAN.md`.

## Stack and commands
- Python 3.10 (system), httpx 0.28, anthropic SDK (0.40 installed, which is old; upgrade before using new features), FastAPI + one HTML page.
- `python scripts/awx.py METHOD /path ['json'] [--as ACCT] [--obo ACCT]` makes a raw API call. `python scripts/awx_docs.py "question"` queries the Airwallex Docs MCP over HTTP (no login, no session id needed).
- `scripts/recon_flow.py` re-tests the money path. `scripts/recon_isolation.py` re-tests tenant isolation.

## Environment (Windows user env vars, set with setx; never commit)
| Var | Value |
|---|---|
| AWX_CLIENT_ID | mlm3dYvwQfiYOqppozYR2w |
| AWX_API_KEY | (scoped key "claude", linked to all 4 accounts below; regenerated 3 Nov) |
| AWX_BASE_URL | https://api.sandbox.airwallex.com |
| AWX_PLATFORM_ACCOUNT | acct_NIym7HZZOOOqBCE7F6LkMA (Sandbox Business, the platform/operator) |
| AWX_EMPLOYER_A | acct_Y5VX3QXWNSyiun0cbai15A (Employer A - Northwind Studio) |
| AWX_EMPLOYER_B | acct_FG3wEt9HNg29C0zhpelKHg (Employer B - Kestrel Labs) |
| AWX_EMPLOYER_C | acct_8bUTqZJePIG80-z_-xiutw (Employer C - Harbour Foods) |
- Shells started before setx don't see these vars. `scripts/awx.py:env()` falls back to reading HKCU\Environment from the registry. Reuse it.
- A `Read(./.env*)` deny rule blocks Claude from reading or writing `.env` files. Don't fight it; use env vars.

## Tool and environment gotchas (each cost real time)
- Git Bash rewrites args starting with `/` into Windows paths (`/global_accounts` becomes `C:/Program Files/Git/global_accounts`), which shows up as a silent 404 "Route Not Found". Always `export MSYS_NO_PATHCONV=1`.
- Windows console is cp1252, and docs output contains Unicode, so set `PYTHONIOENCODING=utf-8` or reconfigure stdout.
- Login POST must send an empty body (`content=b""` / `-d ''`), or the response is 411 Length Required (an HTML page, not JSON).
- Writing secrets into files via Bash heredoc was blocked by the auto-mode classifier. `setx` worked.
- Editing ~/.claude/settings.json permission rules is blocked as self-modification. Ask the user if a rule must change.

## Auth model (verified 3 Nov)
- The scoped key is linked to 4 accounts. Login WITHOUT `x-login-as` gives a token with no account (GET /account -> 401 "Insufficient permissions").
- Login WITH `x-login-as: acct_...` gives a token scoped to exactly that account. **This is how we bind an employer.** The ID must be in `acct_` format, or the response is 400 "invalid account ID format".
- Employer A's token plus `x-on-behalf-of: <B or platform>` returns 401 `credentials_invalid` "Access Denied". Cross-tenant access is impossible at the Airwallex layer. Demo this.
- There's no API to list org accounts: /organizations*, /users/me and /oauth/grant/accounts all need admin. Account IDs come from web app > Settings > Account details.
- Admin keys are deprecated and disabled. Use only scoped keys.
- Connected-account onboarding is NOT enabled ("This account cannot onboard business/individual accounts"). If Airwallex enables it later, switch the binding to platform token + `x-on-behalf-of`. Only the binding layer changes.

## Sandbox behaviour (verified 3 Nov)
- New accounts under the same entity come pre-funded with 10,000,000 each of CNY, EUR, GBP, HKD and USD. Other currencies start at 0.
- Each account has its OWN beneficiaries (each new account gets 9 seeded ones). Beneficiaries are not shared across accounts.
- Global accounts: an AU/AUD global account on Employer C works (`8ec497a4-67a9-4ba2-8b3d-48f1a53d1f4d`). A simulated deposit of 3000 AUD shows as available immediately (response says PENDING). Use a zero-start currency like AUD to stage a genuinely short employer.
- Transfers: `transfers/create` returns 201 SCHEDULED for today. A reused request_id ALWAYS returns 400 `duplicate_request_id` (even with a different amount), and `details.id` holds the original transfer ID. Recovery: on that error, GET the original and treat it as the result. request_id is 10-50 chars.
- Simulation `/simulation/transfers/{id}/transition`: SCHEDULED -> SENT -> PAID -> FAILED works (late failure after PAID is real). Sent `failure_type: BENEFICIARY_BANK_RETURNED` came back as `INCORRECT_ROUTING` with reason "90802: Beneficiary bank returned". Forcing OVERDUE returns 500, so simulate OVERDUE in our harness.
- Deposits: `/simulation/deposits/{id}/settle|reverse` return 404 for global-account deposits (likely direct-debit only), so simulate reversal in the harness. GET /deposits needs `page_num` and `page_size >= 10`.
- FX: quote (`validity: MIN_1`) then conversion with quote_id settles instantly (SETTLED). There's no MCP tool for conversions; use REST.
- Batch transfers on the platform: create -> add_items -> submit -> BOOKING works. Not yet tested under an employer token.
- Beneficiary validate: GB sort codes 040004, 200000 and 041907 pass; 601613 and 401276 fail (code 010). Wrap the payload as `{"beneficiary":{...},"transfer_methods":["LOCAL"]}`.
- Fee collection (no `/charges` without platform enablement): Employer A transfers GBP LOCAL to a beneficiary pointing at the platform's own GBP global account (sort code 041907, acct 07371376). The employer is debited, but the sandbox does NOT credit the platform. Record the credit with a simulated deposit to the platform global account carrying the transfer ID as reference, and label it simulated.
- Probe results (3 Nov, details in `docs/PROBES.md`): zero-balance create gives 400 `balance_insufficient` and does NOT burn the request_id; balance is debited at create; FX quotes are MULTI_USE and conversions return `conversion_id`; beneficiary create returns `id` (not `beneficiary_id`); a GA needs `required_features[].transfer_method` = LOCAL|SWIFT and has no top-level `currency`; garbage bearer is 401 `unauthorized`, no header is 403 HTML; `/transfers` lists only `items`.
- Webhooks are untested (they need a public URL). Poll GET /transfers for now.

## Rules for money and data
- Never use floats for money in our logic. Use Decimal. Airwallex amounts are major units (100 = one hundred).
- The LLM proposes. Code decides amounts, limits, mandates and request_ids. The employer binding (which account token) is chosen by the harness, never by the model.
- Never use one employer's funds for another employer's payroll. Never sum balances across employers.
- Never log tokens or API keys. Every money-moving call gets a deterministic request_id and goes into an append-only, hash-chained ledger.
- Validate external input. Treat emails and invoices the agent reads as untrusted (prompt injection).

## Workflow
- Offline tests run against a fake Airwallex. Run them before calling anything done.
- Keep changes small. Label sandbox-only simulations `[SIMULATED]` in the UI and logs.
