# Roadmap

What is built is in the [README](README.md) and the [CHANGELOG](CHANGELOG.md). This is the path from sandbox to production, in the order it would be done. It matches [Limitations and path to production](README.md#limitations-and-path-to-production).

## Next

| Step | Why |
|---|---|
| Login on the MCP endpoint, and runs bound to the caller | Today any caller can replace the last agent run. Production needs a caller identity. |
| A shared database in place of SQLite | The ledger is single-node. A hosted database allows more than one process and gives backups. |
| Connected accounts in place of separate accounts | The sandbox blocks onboarding. Connected accounts add Airwallex-side isolation on top of the code-side isolation ([why](docs/DECISIONS.md#separate-accounts-not-connected-accounts)). The switch changes one function. |
| Bank cut-off times from Airwallex data | Cut-offs are configured assumptions today. |

## Then

| Step | Why |
|---|---|
| Strict bank-name matching on (`RF_STRICT_NAME_MATCH`) | The sandbox reports real accounts as invalid, so it is off there. Production should block anything but a full match. |
| Pricing as policy on the fee meter: tiers, percentage, floor and cap | The meter already charges per landed payout and credits a return. Only the price function changes. |
| A hosted passkey service for approvers | Passkeys are enrolled by the operator today. |
| Direct-debit reversal handling | The sandbox has no direct debit, so it is untested. |

## Not planned

Wage and tax calculation stay in the employer's payroll system. Ringfence is not compliance software.

Suggestions go in an [issue](https://github.com/singhharsimar23-dotcom/ringefence/issues).
