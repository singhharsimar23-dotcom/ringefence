# Testing

Ringfence moves money, so most of the effort is in trying to break it.

| Layer | What it proves | Run it |
|---|---|---|
| Offline suite, 476 tests | Gate, mandate, executor, funding, FX, ledger, verifier, parser, MCP, app. Runs on a fake Airwallex built from recorded sandbox behaviour ([PROBES.md](PROBES.md)), with fault injection. | `make check` |
| Coverage floor | `make check` fails below 85% of statements and branches. Measured 88% on 21 Nov, with the gate and mandate at 100%. | `make check` |
| Random sequences | 500 random operation sequences, with money invariants checked after every step ([tests/invariants.py](../tests/invariants.py), [test_stateful.py](../tests/test_stateful.py)) | `make check` |
| Gauntlet | 36 hostile documents (9 goals in 4 framings): an agent that obeys every instruction attempted 28 attacks and the gate blocked all 28. Claude followed none ([GAUNTLET.md](GAUNTLET.md)). | `uv run python scripts/gauntlet.py` |
| Fuzzing | The timesheet parser reads untrusted documents. It is fuzzed with Atheris and tested with Hypothesis. A hostile table either parses to valid hours or raises `TimesheetError`. | `uv run --with atheris==3.1.0 python fuzz/fuzz_timesheet.py -max_total_time=45` |
| Bench | A recommended agent setup with a human approving every write, against Ringfence, on live faults ([BENCH.md](BENCH.md)) | `bench/` |
| Live sandbox | 20 parallel releases with 3 dropped responses made exactly one transfer per line. Findings reproduce on your own accounts. | `make live`, `scripts/breakit.py` |
| Verifier | 10 checks per employer, including a live cross-employer `401` probe, signed as an Ed25519 certificate you can verify offline | `uv run python -m ringfence.verify cert docs/proof/northwind.json` |

## What the fuzzer found

A stray carriage return in a timesheet raised an unhandled `csv.Error`, so intake crashed instead of rejecting the file. The parser now turns it into `TimesheetError`, and a regression test covers it.

## Markers

| Marker | Needs | In `make check` |
|---|---|---|
| none | nothing | yes |
| `live` | Airwallex sandbox variables | no |
| `live_llm` | `ANTHROPIC_API_KEY` | no |

## CI

Every push and pull request runs `check` (lint and the offline suite with the coverage floor). Separate workflows run CodeQL, the Atheris fuzz target, OpenSSF Scorecard, a daily OSV scan of `uv.lock`, and on pull requests a dependency review. Actions are pinned to commit SHAs and workflow tokens are read-only. See [.github/workflows/](../.github/workflows/).

## Adding a test

Anything that touches money, approval, the gate or the parser gets a test that fails without the change. The fake Airwallex ([fake_awx.py](../ringfence/fake_awx.py)) has fault injection, such as lost responses. Look at [tests/test_executor.py](../tests/test_executor.py) for the pattern.
