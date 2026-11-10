# Findings: how an AI payroll agent on Airwallex can be led to pay the wrong person

Before building Ringfence, we built a reference agent the way Airwallex's docs, SDK and MCP suggest, and tried to make it pay the wrong person.
Below are the five findings that can cost a company real money. Each one was proven live on the Airwallex sandbox, or in Airwallex's published code. Each one became a rule in Ringfence and was retested against the live app.

**Scope.** Airwallex sandbox only, on our own accounts, with amounts of GBP 5 or less. Every test transfer was cancelled or reversed, and every throwaway payee was deleted.

| # | Finding | Severity | What the reference agent did | What Ringfence does |
|---|---|---|---|---|
| [F1](#f1-approval-swap) | Approval swap | High | paid the swapped account ..9901, 3 of 3 runs | approved bank details pinned → HELD |
| [F2](#f2-bank-change-from-an-email) | Bank change from an email | High | paid the account in the fake email, 5 of 5 runs | quarantined until a phone callback |
| [F3](#f3-the-sdk-shares-one-login) | The SDK shares one login | High | client A's payment on client B's login | one login per client, set by code |
| [F5](#f5-batch-payroll) | Batch payroll | Medium | batch booked to ..9901, can't cancel | no batches, bank details in each payment |
| [F4](#f4-a-retry-pays-twice) | A retry pays twice | Medium | GBP 2 moved for GBP 1 owed | request ID fixed before the first try → pays once |
| [✓](#what-airwallex-got-right) | Airwallex account isolation | Held | 12 of 12 cross-account calls refused | Ringfence builds on it |

---

## F1. Approval swap

**What happens.** A person approves a payroll run. The approval records the payee's ID, not the bank account behind it. Between approval and release, the bank account on that payee is changed. The agent releases, and the money goes to the new account. No alert is raised, and the payee stays changed, so later runs pay it too.

**Why it hurts.** It defeats the human approval step. The approver signed off on the right person, and the money still goes to an attacker.

**Proof.** Live, 10 Nov. Transfer `f94984f9-77c7-4f9c-996b-d326f36f34c7` (Northwind, `P261110-4S793UI`), GBP 2.00 sent to account 99999901. It was cancelled afterwards by our test cleanup. Reproduce with `scripts/breakit.py approval`. Airwallex sends no webhook for a changed beneficiary: [silent_divert](bench/probes/silent_divert.out.txt).

![F1: GBP 2.00 left Northwind for the swapped account](docs/img/findings/f1.png)

**Ringfence.** Each payee's approved bank details are pinned, and they are sent inside the payment itself instead of a payee ID. Before release, Ringfence re-reads each payee from Airwallex. If the account changed, the run is held and has to be approved again as a bank change. After creation, each transfer is read back and cancelled if it points anywhere else.

## F2. Bank change from an email

**What happens.** A fake invoice email arrives with "new bank details" for a contractor. The agent reads it, updates the payee, and pays.

**Why it hurts.** This is the most common payroll fraud, and an AI agent that reads email falls for it every time.

**Proof.** Live, 9 Nov. Transfer `45528e1d-4929-4779-9dc0-1b29bf48c70e` (Kestrel, `P261109-3IKTZJ5`), GBP 1.00 to the account in the fake email, cancelled afterwards. 5 of 5 runs paid it: [agent_bec_repeat](bench/probes/agent_bec_repeat.out.txt).

![F2: Kestrel paid the account from the fake email](docs/img/findings/f2.png)

**Ringfence.** Emails and invoices are untrusted. A bank change found in one is quarantined. It is not used until an approver confirms it by phone callback and records the call's reference.

## F3. The SDK shares one login

**What happens.** The official Node SDK holds one login per process. A platform serving several clients from one process sends client A's payment out on client B's login.

**Why it hurts.** One client's payroll is paid from another client's money.

**Proof.** Found in the published SDK code and checked offline against it: [sdk_singleton_check](bench/probes/sdk_singleton_check.out.txt), [node_sdk_batch_binding](bench/probes/node_sdk_batch_binding.out.txt).

**Ringfence.** Each employer has its own login, bound by code (`x-login-as`). The model never chooses it. The release gate checks again that the run, every line, the token and the mandate all belong to the same employer.

## F5. Batch payroll

**What happens.** A batch transfer pays whoever the payee is at the moment of submit. The reviewer sees payee names, not bank details. Once booked, the platform cannot cancel it: the cancel call returns `401 "Admin permissions required"`.

**Why it hurts.** A whole payroll can go to a swapped account, with no way to stop it.

**Proof.** Live, 10 Nov. Reproduce with `scripts/breakit.py batch`. See [batch probe](bench/probes/batch-status-empty-wrong-binding-resubmit.out.txt).

**Ringfence.** No batches. Each payment carries its own bank details, which were checked at approval.

## F4. A retry pays twice

**What happens.** The agent sends a payment, and the reply is lost on the network. It tries again with a new request ID, and Airwallex makes a second payment. There is no cancel endpoint for it.

**Why it hurts.** Every network blip can double a payment, and the money cannot be pulled back.

**Proof.** Live, 10 Nov, with `scripts/breakit.py retry`. The screenshot is a separate run of the same retry: two GBP 1.00 transfers from Northwind (request IDs `PRB-snap-94650-ca1` and `-ca2`) for one GBP 1.00 owed. Both were reversed afterwards.

![F4: two GBP 1.00 payments for one owed](docs/img/findings/f4.png)

**Ringfence.** Each payment's request ID is fixed and saved before the first attempt. After a timeout, Ringfence never sends again. It looks the payment up by that ID and adopts it if it exists.

---

## What Airwallex got right

Each employer's login is locked to its own account. We made 12 cross-account calls with one employer's token against another employer's account, and all 12 returned `401 credentials_invalid`. Ringfence builds on this: [scripts/recon_isolation.py](scripts/recon_isolation.py).

![Separate Airwallex accounts per employer](docs/img/findings/iso.png)

## Reproduce

Set the sandbox environment variables (see the [README](README.md)), then run `uv run python scripts/breakit.py`. It runs all the live tests, or you can name one: `approval`, `batch` or `retry`.
It writes only to the two employer accounts, at GBP 2 or less, then cancels or reverses every transfer and deletes every payee it created.
