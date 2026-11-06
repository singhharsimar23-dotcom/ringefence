# When the payroll agent's own server is the attacker

Live findings on the Airwallex sandbox and Metal testnet, 6 Nov 2026. Each claim below has a receipt (an Airwallex
ID, a Metal transaction, or a test) or is marked as unproven.

## Thesis

Most controls on a money-moving agent bind a **pointer**: an approved beneficiary *id*, a request *id*, or a mandate
*file*. They don't bind the thing the pointer refers to: the bank account, the obligation, or who can make the
mandate payable. Whoever controls the runtime (a stolen key, an owned VM, the platform operator) can keep every
pointer valid while changing what it points at. The fix in each case below is the same move: bind the **content**,
and check it against a source of truth the runtime can't rewrite.

## Threat model

The attacker has the Ringfence server: its scoped Airwallex key (`beneficiary:write`, `transfer:write` on every
linked employer), its SQLite ledger, and its disk. The attacker doesn't have an employer's web-app login or Harbour's
signing device. The Airwallex layer still isolates tenants: Employer A's token with `x-on-behalf-of` B returns 401
`credentials_invalid` (see `docs/PROBES.md`).

## H1: the approved payee is repointed in place

**Break.** `POST /api/v1/beneficiaries/{id}/update` edits a beneficiary's bank details and **keeps its id**. Every
approval, quarantine and gate check that compares ids still passes, while the money goes to a different account. This
is the API form of Storm-2755's "payroll pirate" step: the attacker edits direct-deposit details inside the HR
system, and nothing else changes
([Microsoft, 9 Apr 2026](https://www.microsoft.com/en-us/security/blog/2026/04/09/investigating-storm-2755-payroll-pirate-attacks-targeting-canadian-employees/)).

**Receipts** (Northwind, `scripts/probe_inplace.py`):

| Step | Airwallex id | Destination |
|---|---|---|
| Beneficiary created | `94d17365-6ac2-48f4-801e-abe043a404de` | ..5678 |
| T1 created | `09f8222a-442d-4915-a239-de00eed4456b` | ..5678 |
| Beneficiary updated in place, **same id** | `94d17365-…` | ..9901 |
| T2 created against the same id | `23bddced-e6ba-4839-abe1-1eade459d399` | **..9901** |
| T1 re-read | `09f8222a-…` | ..5678 (transfers snapshot the destination at create) |

Both transfers are CANCELLED. An earlier probe (`5de33337-9d10-450c-bfd7-4556e64879a5`) showed the same id with a
new account number.

**Why our own code missed it.** The fee path already bound content: `fees.py` checks the live bank details against the
platform's global accounts. The payroll path bound only the id.

**Fix.**
- `ben.fingerprint()` hashes the destination itself (country, IBAN, routing, account), in
  [beneficiaries.py:57](../ringfence/beneficiaries.py#L57).
- The pin is taken from what we *meant* to create, not from what is live.
- At release, `ben.drifted()` ([beneficiaries.py:104](../ringfence/beneficiaries.py#L104)) re-reads every line's
  beneficiary live. Any mismatch, or a missing pin, holds the run with the ALERT `BENEFICIARY_CHANGED_OUTSIDE_RINGFENCE`
  ([orchestrator.py:178](../ringfence/orchestrator.py#L178)).
- Proof re-checks each transfer's own `beneficiary.bank_details` snapshot against the pin: "Every payment went to the
  bank account a human approved" ([verify.py:99](../ringfence/verify.py#L99)). This catches a repoint that lands between
  our check and our create.
- No false positives live across GB, DE (IBAN), AU and US beneficiaries plus all three fee beneficiaries.
- Tests: `test_payee_repointed_in_place_on_airwallex_holds_the_run` and
  `test_a_repoint_that_wins_the_race_with_the_release_check_still_fails_the_proof`.

**Residual.** The race window is milliseconds wide, and Proof catches it afterwards rather than preventing it. The
next step is to cancel the transfer while it's SCHEDULED (cancel works from SCHEDULED and PROCESSING; verified live).

## H2: a lost database pays payroll twice

**Break.**
- Exactly-once rested on our request ids, and those contained a random ledger epoch.
- A fresh disk, a restored backup, or `reset()` produced new ids for the same pay period, so Airwallex saw new
  payments.
- Airwallex remembers a request id for only 7 days anyway.

**Fix.**
- The run id is derived from the obligation (the pay date) and doesn't depend on the ledger.
- Before release, the orchestrator asks Airwallex whether each line's request id already has a transfer that isn't
  FAILED or CANCELLED. If so, it holds the run with `ALREADY_PAID_ON_AIRWALLEX`
  ([orchestrator.py:173](../ringfence/orchestrator.py#L173)).
- Test: `test_a_lost_database_does_not_pay_payroll_twice`. A brand-new ledger file gets the same run id, the run is
  held, and the transfer count is unchanged.

**Residual.**
- `RF_DEMO_TAKES=1` (demo VM only) brings back the random epoch so that repeated demo takes don't collide.
- An adopted older transfer can show as "missing" in Proof. That's a false FAIL, so it fails safe.

## H3: the server signs Harbour's money away (Metal custody)

**Break.**
- Harbour's top-ups run on Metal mandates.
- On Metal, **only the owner's `mandate bind` makes a mandate payable**. An issuer-only credential reports
  `bound no`, and its pull is refused as "not bound… the owner binds it with mandate bind". Live:
  `0x3f67705094aad6c8531a210781ba5b96db654bcf8f1734e31af1b89a7be4e369`.
- Our server held Harbour's owner key (`owner.json`), so whoever owned the server could write and bind any mandate on
  Harbour's account.
- We also found a double-pull in our own code: a retried top-up minted a *new* credential. Metal deduplicates a pull
  only locally ("known only under this home directory and this credential"), so a retry could pull twice.

**Fix: device-signed mode.**
- Harbour's device runs [scripts/harbour_device.py](../scripts/harbour_device.py). It signs one-shot credentials
  (`--max-occurrences 1`, budget = cap) and reads the terms back from the credential.
- It refuses to bind if the payee or the occurrence count differs from what the operator typed.
- It hands the server only `m.json` and its pull key.
- With no `owner.json`, the server can't mint ([metal.py:103](../ringfence/metal.py#L103)).
  `_presigned()` ([metal.py:108](../ringfence/metal.py#L108)) takes a bound, unrevoked, unspent, unexpired credential
  that covers the shortfall, and moves it into the run directory. A retry reuses that same credential. If nothing
  covers the shortfall, it raises an error and the run falls back.

**Live receipts** (testnet; `scripts/proof_device_signed.py`, server run with no Harbour owner key):

| | Result | Transaction |
|---|---|---|
| Harbour's device binds 0.05 USDZ, one pull, payee = settlement | bound `0xd6c188fa…8bbc` | [0xf4b07dfa…1a4a](https://testnet.metalntwx.com/tx/0xf4b07dfaf655f3ee92076585fd5e56b41f57125d45f62da0e66ae82ae4261a4a) |
| 1. Server pulls the shortfall | **paid** | [0x65c108fb…63bf](https://testnet.metalntwx.com/tx/0x65c108fbd62681b4ba788cad3cf56e3ed29063e80f8177bdaccce2a08d2463bf) |
| 2. Same credential, new payment id | **refused** `mandate_budget_spent` | [0x9ff764b4…1468](https://testnet.metalntwx.com/tx/0x9ff764b4879ad69b1a21031d2eca28fc87e8e4fb88eb982b9dbe6d8085021468) |
| 3. Pull to a lookalike of the settlement wallet | **refused** `mandate_payee_not_listed` | [0x598bb65d…c703](https://testnet.metalntwx.com/tx/0x598bb65db1c032762020dc6a6039af57a1b0a5382225b82ad0fa13146e4ec703) |
| 4. Server writes its own mandate on Harbour's account and binds it with the only funded key it has | **bind reverted**; status `bound no` | none (reverted in simulation) |

Test: `test_device_signed_mode_never_binds_here_and_a_retry_cannot_pull_twice`.

**Residual: blind signing.** The device is only as good as what it shows. At Bybit (21 Feb 2025, about $1.46bn), the
signers approved a transaction that the Safe UI displayed as routine, while different data went to the Ledger
([CertiK](https://www.certik.com/blog/bybit-incident-technical-analysis),
[Chainalysis](https://www.chainalysis.com/blog/bybit-exchange-hack-february-2025-crypto-security-dprk/)). That's why
the payee is typed on the device and never taken from the server, and why the terms are read back from the signed
credential rather than echoed from the request. This is not a claim that Ringfence would have stopped Bybit. The
attack class there was a different one.

## H4: the ledger can be rewritten by whoever holds it (open)

`Ledger.reset()` ([ledger.py:220](../ringfence/ledger.py#L220)) drops the append-only triggers and deletes every row.
The hash chain has no external anchor, so an owner of the disk can recompute it. **Not fixed.** The fix would be to
publish each run's head hash somewhere the server can't rewrite (Airwallex transfer metadata, or a Metal payment id).
That touches the frozen executor, so it's deferred.

## H5: the bank-name check fails open (found in our own fix)

`name_match()` ([beneficiaries.py:164](../ringfence/beneficiaries.py#L164)) blocks only `NOT_MATCHED`. `UNAVAILABLE`,
`INVALID` and `PARTIAL` pass, because the sandbox calls every non-test account `INVALID`, so a strict check would block
every live demo. It's marked `shortcut:` and should block in production.

## Also proven

- **A transfer that bypasses the ledger.** An inline-beneficiary transfer goes through under the scoped key with no
  ledger row (`860b3fa0-ddc5-4791-b92e-24f057e293fd`, CANCELLED). Proof flags it, because it compares Airwallex's
  transfer list against the ledger, not the other way round.
- **Detection runs on the compromised host.** Every check above runs on the server it's meant to distrust. Proof is
  strong only because it re-reads Airwallex and the chain. Two controls the server can't switch off need the web app:
  "API-initiated transfers require approval", and an IP allow-list on the scoped key.

## Side effects of these probes

- Northwind's live Proof shows FAIL. It lists the probe transfers (`09f8222a…`, `23bddced…`, `860b3fa0…`), which are
  real transfers outside the ledger. The FAIL clears on a world reset.
- 0.05 testnet USDZ stays in our own settlement wallet locally. The local settlement address is a bare key with no
  Metal account, so `recycle()` can't sign a return mandate for it.
