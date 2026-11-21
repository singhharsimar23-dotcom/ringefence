# Contributing

Ringfence moves money on the Airwallex sandbox and the Metal testnet. Changes to the gate, the executor, approval or the ledger get the most care, because a mistake there is a payment to the wrong place.

## Set up

You need [uv](https://docs.astral.sh/uv/) and Python 3.12 or newer.

```
make sync
make check      # ruff, then the offline tests with a coverage floor
```

`make check` needs no network and no keys. It is what CI runs. More on running the app, the live sandbox and the MCP server: [docs/RUN_IT.md](docs/RUN_IT.md).

## Before you open a pull request

1. Branch from `main` and keep the change to one thing.
2. Add or update a test. Anything that touches money, approval, the gate or the parser needs one that fails without your change.
3. Run `make check`. CI blocks a merge unless the `check` job passes.
4. If you changed behaviour users can see, add a line under `Unreleased` in [CHANGELOG.md](CHANGELOG.md).
5. Describe what changed and why. Say what you did not test.

## Rules that are not negotiable

- **Money is `Decimal`, never float** ([money.py](ringfence/money.py)).
- **No path from the model to money.** The model proposes. The gate decides, and nothing the model emits is trusted as a payee, an amount or an employer.
- **Exactly once.** A request ID is fixed before the first try, and a timeout means lookup, never resend.
- **A missing limit is a refusal**, not a default.
- **No secrets in the repo, logs or tests.** Never print a token or an API key. Sandbox simulations are labelled `[SIMULATED]`.
- **No claim without a way to check it.** Numbers in docs come from a test, a recorded run or an Airwallex ID.

## Tests

| Where | What |
|---|---|
| [tests/](tests/) | the offline suite against a fake Airwallex built from recorded sandbox behaviour |
| [tests/test_fuzz_timesheet.py](tests/test_fuzz_timesheet.py), [fuzz/](fuzz/) | property tests and the Atheris fuzz target for the timesheet parser |
| `make live` | tests marked `live`, against your own sandbox |

Details: [docs/TESTING.md](docs/TESTING.md).

## Reporting a vulnerability

Do not open a public issue. Use [private reporting](https://github.com/singhharsimar23-dotcom/ringefence/security/advisories/new). See [SECURITY.md](SECURITY.md).

## Commits

Plain, direct messages that say what changed. The first line is under about 72 characters.

## License

By contributing you agree that your contribution is licensed under the [MIT license](LICENSE).
