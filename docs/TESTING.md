# Testing

Ringfence moves money, so most of the effort is in trying to break it.

| Layer | What it proves | Run it |
|---|---|---|
| Offline suite, 588 tests | Gate, mandate, executor, funding, FX, ledger, verifier, parser, MCP, app. Runs on a fake Airwallex built from recorded sandbox behaviour ([PROBES.md](PROBES.md)), with fault injection. | `make check` |
| Coverage floor | `make check` fails below 85% of statements and branches. Measured 88% on 21 Nov, with the gate and mandate at 100%. | `make check` |
| Property tests | 31 [Hypothesis](https://hypothesis.readthedocs.io/) properties over the gate, signing, batch hashes, request IDs, money and bank-detail fingerprints, 150 generated cases each, derandomized so a failure repeats. One of them found a real bug: a non-ASCII signature raised instead of being refused. [test_properties.py](../tests/test_properties.py) | `make check` |
| Fault schedules | The executor run under every one of the 81 ways to inject nothing, a lost reply or a failed send before each of four release attempts, then one clean attempt. Each line is paid exactly once every time. [test_executor.py](../tests/test_executor.py) | `make check` |
| Random sequences | 500 random operation sequences, with money invariants checked after every step ([tests/invariants.py](../tests/invariants.py), [test_stateful.py](../tests/test_stateful.py)) | `make check` |
| Mutation testing | [scripts/mutate.py](../scripts/mutate.py) changes `gate.py`, `mandate.py` and `money.py` one edit at a time (435 mutants) and reruns the tests. All 435 were caught, none survived, in 10 minutes on 8 workers on 21 Nov. See below. | `uv run python scripts/mutate.py` |
| TLA+ model | The release protocol checked with TLC over a small instance: 479,088 distinct states, no violation, and the two naive variants break as the findings say ([formal/](../formal/README.md)). | `bash formal/run.sh` |
| Gauntlet | 36 hostile documents (9 goals in 4 framings): an agent that obeys every instruction attempted 28 attacks and the gate blocked all 28. Claude followed none ([GAUNTLET.md](GAUNTLET.md)). | `uv run python scripts/gauntlet.py` |
| Fuzzing | The timesheet parser reads untrusted documents. It is fuzzed with Atheris and tested with Hypothesis. A hostile table either parses to valid hours or raises `TimesheetError`. | `uv run --with atheris==3.1.0 python fuzz/fuzz_timesheet.py -max_total_time=45` |
| Bench | A recommended agent setup with a human approving every write, against Ringfence, on live faults ([BENCH.md](BENCH.md)) | `bench/` |
| Live sandbox | 20 parallel releases with 3 dropped responses made exactly one transfer per line. Findings reproduce on your own accounts. | `make live`, `scripts/breakit.py` |
| Verifier | 10 checks per employer, including a live cross-employer `401` probe, signed as an Ed25519 certificate you can verify offline | `uv run python -m ringfence.verify cert docs/proof/northwind.json` |

## Mutation testing

`mutmut` does not run on Windows, so [scripts/mutate.py](../scripts/mutate.py) is a small mutator built on Python's `ast` module. It applies one change at a time: a flipped comparison, `and` for `or`, a swapped reason code, a `Deny` turned into `Allow`, a constant or a branch condition changed. Each mutant runs against the fast tests first, then against the whole offline suite if it survived.

Result on 21 Nov 2026: 435 mutants (`gate.py` 290, `mandate.py` 66, `money.py` 79). 432 failed a test, 3 made the module crash on import (a mangled decimal literal), 0 timed out, 0 survived. 44 were caught only by the full suite, not the fast tests. There are no equivalent mutants to list.

What that does and does not mean:

- A perfect score on these three files is a fact about this operator set, not proof that there are no bugs. The operators are comparison, boolean, arithmetic, constant, return-value, reason-code and branch changes. It skips docstrings, f-string text, class and function decorators, and type annotations.
- Only those three files are mutated. The executor and ledger are covered by the fault schedules, random sequences and invariants, but are not mutation-tested.
- To check the runner can fail, it was rerun against `gate.py` with only the money tests, and it reported survivors as expected.

[mutation.yml](../.github/workflows/mutation.yml) runs it weekly and on demand, and fails below 100%. It does not run on every pull request because it takes about 10 minutes.

## What the fuzzer found

A stray carriage return in a timesheet raised an unhandled `csv.Error`, so intake crashed instead of rejecting the file. The parser now turns it into `TimesheetError`, and a regression test covers it.

## Markers

| Marker | Needs | In `make check` |
|---|---|---|
| none | nothing | yes |
| `live` | Airwallex sandbox variables | no |
| `live_llm` | `ANTHROPIC_API_KEY` | no |

## CI

Every push and pull request runs `check` (lint and the offline suite with the coverage floor). Separate workflows run the TLA+ check (`formal`, when `formal/` changes), the weekly mutation run, CodeQL, the Atheris fuzz target, OpenSSF Scorecard, a daily OSV scan of `uv.lock`, and on pull requests a dependency review. Actions are pinned to commit SHAs and workflow tokens are read-only. See [.github/workflows/](../.github/workflows/).

## Adding a test

Anything that touches money, approval, the gate or the parser gets a test that fails without the change. The fake Airwallex ([fake_awx.py](../ringfence/fake_awx.py)) has fault injection, such as lost responses. Look at [tests/test_executor.py](../tests/test_executor.py) for the pattern.
