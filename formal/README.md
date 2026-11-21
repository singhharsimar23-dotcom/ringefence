# Formal model of the release protocol

[RingfenceRelease.tla](RingfenceRelease.tla) models how one payroll run is released, and TLC checks it exhaustively over a small instance. It checks the protocol, not the Python. The Python is checked by the tests ([TESTING.md](../docs/TESTING.md)).

## What is modelled

A batch is proposed, a person approves a hash of the exact batch (amounts plus the pinned bank details), and release re-reads the live bank details and holds on any difference. Each line then goes through INTENT and a send. A send can succeed, time out after the bank booked it, or fail before it booked. The process can crash and restart. A payment can be returned.

An attacker can edit any payee's bank details at any moment, including between the gate and the send, and can edit a line amount before release. The bank rejects a repeated request ID.

## Result

TLC 2.19 (8 Aug 2024), Temurin 21, 12 workers, on 21 Nov 2026. Three payees, two amounts, three bank accounts (the approved one, an attacker's, and another employer's).

| Config | Switches | Result |
|---|---|---|
| [ringfence.cfg](ringfence.cfg) | pinned details on, stable request ID on | No error. 7,245,512 states generated, 479,088 distinct, depth 21, 14 s. |
| [naive_f1.cfg](naive_f1.cfg) | pinned details off | `PaidOnlyApproved` violated, a 7-state trace. [Trace](counterexample-naive_f1.txt). |
| [naive_f4.cfg](naive_f4.cfg) | stable request ID off | `NoDoublePay` violated, a 9-state trace. [Trace](counterexample-naive_f4.txt). |

Invariants checked on the Ringfence config:

| Invariant | Meaning |
|---|---|
| `NoDoublePay` | A payee is never paid twice in a round, unless the first payment was returned. |
| `PaidOnlyApproved` | Every payment goes to the pinned account for exactly the approved amount. |
| `NoCrossEmployer` | No payment lands in another employer's account. |
| `NoSendWithoutApproval` | Nothing is booked before approval. This follows from the guard on the send step, so it checks the model rather than finding bugs. The code's version is invariant I7 in [tests/invariants.py](../tests/invariants.py). |

## The naive variants

Each switch turns one fix off, and TLC finds the matching finding in [FINDINGS.md](../FINDINGS.md).

- **F1, approval swap.** With `PinnedDetails = FALSE` the approval binds payee IDs, and the send names the payee by ID. The trace: approve, pass the gate, the attacker edits the payee, release sends, and the money goes to the attacker's account.
- **F4, a retry pays twice.** With `StableRequestId = FALSE` a retry gets a fresh request ID and never looks the payment up. The trace: send, the reply is lost, retry under a new ID, and the payee is paid twice.

Three reachability checks (`reach_*.cfg`) must also find violations: a run where every line is paid, a hold after a payment, and a return. They show the model does the things the invariants guard against.

## What this does not show

- The model is small: one run, one employer, three payees. It does not model approval expiry, funds, FX, or the 25 gate refusals, which are covered by tests.
- It does not prove the Python matches the model. The two are linked by hand, and by the tests that use the same scenarios.
- Fresh-ID retries after a return (a new round and a new approval) are not modelled.
- Dafny was not used. Only TLA+ with TLC was run.

## Run it

Needs Java 17 or later and `tla2tools.jar` from the [TLA+ v1.7.4 release](https://github.com/tlaplus/tlaplus/releases/tag/v1.7.4) (sha256 `936a2620…8e50e88`; the exact hash is in [formal.yml](../.github/workflows/formal.yml)).

```
TLA_JAR=/path/to/tla2tools.jar bash formal/run.sh
```

It exits non-zero if the Ringfence config finds an error or a naive config stops finding its counterexample. CI runs the same script ([formal.yml](../.github/workflows/formal.yml)).
