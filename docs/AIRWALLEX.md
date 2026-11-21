# How Ringfence uses Airwallex

Ringfence runs on the Airwallex sandbox. This page lists what it calls, how accounts are laid out, what is real and what is simulated, and the Airwallex docs each behaviour rests on. A recorded run with every ID is in [PROOF.md](PROOF.md).

## Accounts

One Airwallex organisation holds four accounts:

| Account | Role |
|---|---|
| Platform | The operator. Collects Ringfence's fees. |
| Northwind Studio, Kestrel Labs, Harbour Foods | Three employers, each paying from its own balances, payees and global accounts |

Each employer has its own login. A token is logged in as that account only ([`x-login-as`](https://www.airwallex.com/docs/api/authentication/api_access_token/login.md)), and code picks the token, never the model. Cross-account calls are refused by Airwallex (12 of 12 in the probes, [PROBES.md](PROBES.md)).

The sandbox blocks connected-account onboarding, so employers are separate accounts reached by one scoped key. The reasoning and the upgrade path are in [DECISIONS.md](DECISIONS.md#separate-accounts-not-connected-accounts).

## What Ringfence calls

| Airwallex API | Used for |
|---|---|
| Login with `x-login-as` | one token per employer |
| `/balances/current` | funds check against this employer's own balance |
| `/beneficiaries` | create payees, read them back, quarantine changes |
| `/global_accounts`, `/deposits` | the account a short employer funds, and matching its deposit |
| `/fx/quotes/create`, `/fx/conversions/create` | convert the employer's own spare currency |
| `/transfers/create` | pay, with the approved bank details inline |
| `/transfers` (get, list by `request_id`, cancel) | read back, recover after a timeout, cancel a redirected payment |
| `/webhooks` | signed events, treated as a hint |
| `/simulation/*` | sandbox only: the source of every `[SIMULATED]` step |

## Behaviours that matter, and where Airwallex documents them

- **Idempotency.** [Create a transfer](https://www.airwallex.com/docs/api/payouts/transfers/create.md): a `request_id` is rejected for 7 days. After a timeout, Ringfence looks the payment up by `request_id` and never resends. [Cancel](https://www.airwallex.com/docs/api/payouts/transfers/cancel.md) is used only for a payment found to point at the wrong account.
- **A payee can be edited in place.** [Update a beneficiary](https://www.airwallex.com/docs/api/payouts/beneficiaries/update.md) keeps the ID and changes the bank details. This is why approvals bind the bank details, not the ID ([F1](../FINDINGS.md#f1-approval-swap)).
- **Batch transfers pay the account as it is at submit.** [Batch transfers](https://www.airwallex.com/docs/api/payouts/batch_transfers.md) cannot be cancelled by the API, so Ringfence never uses them ([F5](../FINDINGS.md#f5-batch-payroll)).
- **Scoped keys and login.** [Scoped API keys](https://www.airwallex.com/docs/developer-tools/api/manage-api-keys.md) and the login page above.
- **Webhooks.** [Signature check](https://www.airwallex.com/docs/developer-tools/webhooks/listen-for-webhook-events.md#check-webhook-signatures): HMAC-SHA256 of the timestamp and raw body. A valid event only prompts a re-fetch.
- **FX.** [Create a conversion](https://www.airwallex.com/docs/api/transactional_fx/conversion/create.md). Quotes are multi-use, and Ringfence sells only the employer's own spare currency.
- **Simulation.** [Simulate a transfer status](https://www.airwallex.com/docs/api/simulation/transfers/transition.md), sandbox only.

## Real and simulated

| Real sandbox calls | Simulated (`[SIMULATED]`) |
|---|---|
| Transfers, FX, beneficiaries, the global account, the isolation check, fees | Payouts reaching `PAID`, a short employer's deposit, the platform's fee credit |

The sandbox does not credit the platform for fees, so Ringfence records that credit itself. Every simulated step is labelled in the UI, the ledger and the proof.

## Deadlines and funding

Pay-day cut-offs are the currency's bank cut-off minus 2 hours, shown in the employer's timezone: AUD 11:00 Sydney, GBP 12:00 London, EUR 12:00 Berlin, USD 15:00 New York ([funding.py](../ringfence/funding.py#L29)). They are configured assumptions, not Airwallex data.

A short employer gets the exact amount, its own global account details and a unique reference `RF-<EMP>-<run>-<rand>`. A deposit counts only if reference, account, currency and status all match. Several deposits add up, the run re-prices and resumes, and a reversed deposit reopens the request. Transfers that are `OVERDUE` or `IN_APPROVAL` are tracked to completion and count as not yet debited.

## Connecting your own sandbox

Variables and setup steps are in [RUN_IT.md](RUN_IT.md#on-the-live-airwallex-sandbox).
