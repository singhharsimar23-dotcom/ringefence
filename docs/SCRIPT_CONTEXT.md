# Deep context for the next agent working on the Ringfence video script

Read this before you touch `docs/SPEAK_V5.md`. It is the "why", so you don't re-open decisions that are already
settled with reasons. The script is `SPEAK_V5.md` (word-for-word). `DEMO_PLAN.md` is the short tone map.
`AIRWALLEX_GAPS.md` is the full evidence file (every transfer id). `DISCLOSURE_AIRWALLEX.md` is the private note to
Airwallex. `FINAL_FINDINGS_AND_DEMO_HANDOFF.md` is the older long handoff (superseded in tone by this file, still
good for detail).

---

## 1. What this is, in one breath

Ringfence is a multi-employer **payroll agent** built on the Airwallex sandbox for the Agentic Banking Hackathon
(Kit 06). It runs payroll for several companies at once, each on its own Airwallex account, and its one promise is:
**an AI agent that never pays the wrong person.** The architecture rule that makes that true: **the LLM proposes,
the code decides.** The model never chooses an amount, a destination, a payer, a limit, or a request_id. Code does.

The video is a Loom, screen + camera, **hard cap 5:00**, ~640 spoken words, delivered like showing a friend.

## 2. What the judges score — this governs everything

Four axes: **finance value, Airwallex relevance, agent behaviour/controls, technical execution.** The rubric arc
they want: **goal → plan → new information → revised decision → final balance.** This is NOT a bug bounty. The
judges reward the *product* moving money safely. The bugs score only as the *motivation* for the control layer —
never on their own. If the film leads with bugs, it answers a question the rubric doesn't ask and loses points even
though the research is strong. Target ratio: **~70% product, ~30% the gap that explains why the control exists.**

## 3. The central thesis — memorise this, everything orbits it

> **Airwallex's controls bind *pointers*. The money follows the *content* behind the pointer.**
> A beneficiary id, a request id, an account chosen per call — all pointers. Every gap we found is a place where the
> pointer stayed the same and the content behind it changed. **Ringfence binds the content.**

The on-camera one-liner form (this is the emotional peak, §7 of the script):
> **"The check reads a label. The money follows what it points to."**

The hero example that proves the thesis live: you put a human on every payment (exactly what Airwallex's AgentOS
guidance recommends). The approver sees the right name, the right amount, says yes. While it waits, the payee's
bank account is edited **in place — same id**. Right id, right amount, a human approved — money goes to a different
bank account. **3 of 3.** Nothing on the platform flags it (no `beneficiary.updated` event, no `updated_at`/version
on the payee object). This is the API form of the real-world Storm-2755 "payroll pirate" attack (Microsoft,
9 Apr 2026).

## 4. The honesty ceiling — DO NOT cross these lines

The user's hardest, most repeated instruction: **do not exaggerate, do not bend the narrative to fit a severity we
don't have.** We lost points of credibility every time a claim outran its receipt, and clawed them back by
correcting ourselves. Hold this line.

- **No Sev-1. No cross-tenant break.** Tenant isolation held *every single time* (cross-account token + `x-on-behalf-of`
  → 401 `credentials_invalid`; paying to another employer's beneficiary id → 400 `validation_failed`). Say this
  out loud on camera — it buys credibility and it's true.
- **What else held, and we must say so to be fair:** amount is bound, payer is bound, FX quote+expiry is bound,
  single transfers snapshot their destination at create, a cancelled transfer refunds to the penny, no value
  creation (negative amounts rejected). Airwallex itself never loses money — only the *employer's* money can go to
  the wrong destination.
- **The only live-proven money-*loss* bug is the docs double-charge** (#3 / Finding 1): following Airwallex's own
  error-table advice ("retry with a new request_id") moved GBP 2 for a GBP 1 payable, instantly, no cancel.
- **The repoint (3/3) is a *detection/hardening* gap, not a bypass.** It needs write access to the payee (the
  account's own credentials). AND — a correction we made against ourselves — `/transfers` items DO carry a
  `beneficiary.bank_details` snapshot, so a snapshot-diffing reconciler CAN detect the change after the fact. The
  real gap is the lack of anything *proactive* (no event, no audit field) and that the in-flight approval shows only
  the id. **Never say the repoint is "undetectable" or "silent for months."** Say "nothing proactively flags it;
  the first alarm is the employee saying 'I wasn't paid.'"
- **The SDK singleton (#0/#16) is offline-verified only.** We proved *which token the SDK attaches* (B's token on
  A's call) with `bench/probes/sdk_singleton_check.js` — no network call. We did NOT fire a completed cross-account
  payment. Say "verified offline" if you mention it at all; it's not a video beat.
- **The MCP wrong-payer claim did NOT reproduce (0/17).** Opus 5.5 always passed the right account explicitly.
  **There is no video line for a wrong payer from the MCP.** The MCP's *code* facts (no idempotency, dropped error
  details) stand; the behavioural claim does not.
- **The AI prompt-injection beat is honest-small:** a plain agent paid a fake "our bank details changed" invoice
  **1 of 5**. The other 4 it refused. That's a *good* model — and that's exactly the point: "usually" is not a
  control. Never inflate to "the AI always falls for it."
- **Things never tested live — do not claim:** batches under the native approval policy, APPROVAL_REJECTED/RECALLED
  resubmit, cancel-while-IN_APPROVAL, the Haiku arm, the strict-name-match flag against live Airwallex, the
  market-agent `dupamt`/`late` faults (never ran — Anthropic credit ran out).
- **Never call anything a "vulnerability" on camera.** The words are "gap", "flags", "leaks". We are not attacking
  Airwallex; we built the safe layer on their rails.

## 5. The findings, ranked, with real status (the full menu to draw script beats from)

From `AIRWALLEX_GAPS.md` (live, 3–6 Nov) and the 9 Nov package-review pass. "Shown live" = reproduced on sandbox.

| # | Gap | Status | In the video? |
|---|---|---|---|
| 1 | **Approval binds a beneficiary id; the id is repointed in place while approval waits** | CONFIRMED 3/3 | **YES — hero beat (§6)** |
| 2 | Batch payroll pays the payee as-at-submit; batch preview shows no bank details; API key can't cancel a batch | CONFIRMED 4/4 | Flash only (fifteen-findings) |
| 3 | Docs say: on duplicate request_id, retry with a **new** one → live double funding | CONFIRMED live double pay | Flash / optional |
| 4 | `GET /transfers` ignores `page_num` (guide says use it); reconcile reported 99/199 unpaid, 66 real | CONFIRMED, 2 verifiers | Flash |
| 5 | Node SDK auto-retry swaps args, drops a GET's query+headers (request_id, x-on-behalf-of) | CONFIRMED, 2 verifiers | Flash |
| 6 | Official MCP: new request_id per call, strips error details, payer is an optional per-call arg | Code CONFIRMED; payer trial **0/17 (not reproduced)** | Code facts only |
| 7 | Airwallex Pay (wallet): PAID in ~2s, no cancel, snapshot has no bank_details | CONFIRMED | Flash |
| 8–11 | duplicate_request_id ignores payload; dedupe per-account; PAID→FAILED is real; can't cancel right after create | CONFIRMED | Supporting |
| 12–15 | double terminal event; fail-open `GET /beneficiaries/{id}` (200 empty); `?company_name=` ignored; empty batch-items list | FACT, LOSS NOT SHOWN | Footnotes |
| 0/16 | Node SDK process-global singleton → wrong payer token | **Verified OFFLINE only** | Not a beat; one line max |
| 17 | MCP create_transfer no idempotency + dropped error details | Code CONFIRMED | Flash |
| 18 | MCP create_payment_link non-atomic / model-chosen email; get_fx_quote mislabelled readOnly | Code CONFIRMED | Not shown |
| 19 | Ignored-filter family wider than company_name (unknown `?status=` ignored, 15 vs 15) | CONFIRMED | Flash |

**For the script: ONE hero (#1, the repoint). Everything else flashes on screen as "fifteen findings, each with a
receipt" for ~2 seconds.** The user's rule: resist listing them; the hero is one sentence.

## 6. How Ringfence fixes each — the "fix" half of every beat

- **Repoint (#1,2):** approved bank details are sent **inline** with each transfer (not a beneficiary_id), so a
  repointed id can't redirect it. Backstop: pin a fingerprint of the bank details at approval, re-read live at
  release, **hold on drift (3/3 HELD)**; after create, compare each transfer's own snapshot to the pin and
  **cancel a mismatch (3/3 CANCELLED)**.
- **Double-pay / duplicate (#3,8,9):** request_ids are **deterministic** per run/tenant/contractor/attempt — never
  a new id on retry. Both error spellings (`duplicate_request_id`+`details.id` and the CA `request_id_duplicate`+
  `details.source_id`) are normalised. Every adopt-by-request_id verifies payee+amount+currency and holds on mismatch.
- **Pagination (#4):** Proof pages `/transfers` with the real cursor and fails if the cursor stalls.
- **Wallet (#7):** wallet destinations are fingerprinted (`dest_fp`), fail closed on unknown.
- **PAID-not-final (#10,12):** PAID lines polled while the run lives; a late return keeps a HELD run held; status
  never moves backwards.
- **Fail-open read (#13):** an empty 200 on a payee read holds the run by name instead of crashing.
- **Prompt-injected invoice:** a bank-detail change read from a document is **quarantined** until a *different*
  person confirms by phone. The agent can't move money at all — it only proposes.
- **Tamper-proof books:** hash-chained ledger; each transfer carries the ledger head (`metadata.rf_seq`/`rf_hash`),
  which Airwallex stores and returns, and **Proof turns red** if the local ledger no longer matches.

## 7. Why we shifted the narrative — the full history, so you don't undo it

The script went through four big reframes. Each was a deliberate correction to a specific failure mode. Do not
revert any of these without the user's say-so.

1. **v1–v4 → v5: product-first flip.** v4 gave the product 50 seconds and the gaps 2.5 minutes — it played like a
   bug hunt and fought the rubric. **v5 flips to ~2:25 product, ~1:45 gap+fix.** One hero break (the repoint), not
   four. Reason: the judges score the product; the bugs are only the *why*.
2. **De-exaggeration pass.** Severities had been inflated (Highs), and we'd claimed the repoint was "silent for
   months" / "undetectable" / "sandbox behaves like production." All corrected to honest Medium/Low with a
   "shown live?" column and caveats. We also corrected our *own* overstatement (the transfer snapshot DOES exist, so
   the reconciler isn't blind). Reason: the user caught the exaggeration and it was killing credibility. **This is
   the single most important standing constraint — see §4.**
3. **Two-thank-yous split.** The bugs earn a private *thank-you* from Airwallex's **security team** (for the real
   SDK/MCP/docs fixes, #2/#3/#5/#8). They do NOT earn thank-yous from the **hackathon judges** — judges reward the
   product. So: send the disclosure privately for the thank-you; win the hackathon with the product, using the
   on-theme bugs only as the reason the control layer is needed.
4. **"Brag → finding" reframe (latest, this is the current tone law).** The user's exact ask: *"turn the bug hunt
   to make our platform strong… we know how things go wrong, we fixed it, we built our platform; in demo we show
   failure, fix it, then show our demo working."* Then the refinement: *"be careful we don't make a bug report — it
   has to be abstract, we brag about what we did but that leads to our finding, that is the goal."* So the order is
   **product (the brag) → the gap we noticed while building (abstract, one sentence) → the control that closes it.**
   Lead every finding with the product reason it matters, then the finding — never the reverse. Never recite the list.

## 8. Current script shape (`SPEAK_V5.md`) — what each section does

- **§1 Open (0:15):** "an AI agent that runs payroll for lots of companies — how do I make sure it never pays the
  wrong person?"
- **§2 The run (0:15–1:15):** 3 clients, own accounts, agent suggests/code decides. Kestrel pays (real transfers),
  Northwind waits+shows what changed, Harbour short AUD 1,240.17 + deadline. Twist: $50k lands in Kestrel, not
  touched for Harbour, Harbour stays HELD. **(the brag)**
- **§3 Harbour funds itself (1:15–1:55):** Binance framing (attackers inside the signer) → Harbour signs a Metal
  blockchain rule: one pull, exact amount, our account only, next hour. +1 coin → REFUSED, lookalike → REFUSED.
- **§4 Revised decision + proof (1:55–2:40):** Harbour paid; real Airwallex dashboard same IDs; cross-login 401;
  tamper → Proof red → restore → green.
- **§5 The question (2:40–3:10):** plain agent + fake "bank details changed" invoice → paid the attacker 1 of 5.
  "A good model. But 'usually' isn't a control."
- **§6 Add a human (3:10–3:55):** the hero repoint. Right id, right amount, human said yes, wrong account, 3/3.
  Nothing flags it; first alarm is "I wasn't paid."
- **§7 How did we miss it (3:55–4:15):** the peak. Every piece is reasonable; nobody owns the gap between them.
  **"The check reads a label. The money follows what it points to."**
- **§8 Ringfence holds (4:15–4:45):** quarantine + bind-the-account-not-the-id. Then "to be fair, the walls held;
  amount/payer/FX bound." "Fifteen findings, each with a receipt," + 8b "Airwallex has them first" (only if
  disclosure sent).
- **§9 Close (4:45–4:55):** "It's live. Try to break it. The agent suggests, my code decides. That's Ringfence."

Each spoken claim has a receipt row in the §Stress-test table at the bottom of `SPEAK_V5.md` — **use it. Do not add
a claim without a receipt.** The table also records the exact wording guards (e.g. say "agent guidance" not
"approval screen"; say "built the usual way = ours, not Airwallex's"; never say "for months").

## 9. Delivery / tone rules (keep the human voice, no AI slop)

- Marks in the script: **bold** = lean/emphasis · `/` = half-second beat · `//` = full pause · *(italic)* = how to
  say it · [footage] = not read. Slow on numbers and section-ending words.
- No slop words, no "in today's world", no triplets-for-rhythm, no "vulnerability/exploit". Short, concrete, spoken.
- Humility where it's honest ("once in five", "a good model", "to be fair, the walls held") is what makes the brag
  land. Keep it.

## 10. Hard facts / numbers to keep exact (verify on a fresh run before recording)

- Harbour short: **AUD 1,240.17** (read it off screen if the live number differs).
- Repoint: **3/3** to account ending **..9901**. Batch: **4/4**.
- AI invoice: **1 of 5** paid; 4 refused.
- Double-pay: **GBP 2 for a GBP 1 payable** (CA transfer).
- Reconcile: **99 of 199** reported unpaid, **66** real debits.
- MCP payer trial: **0/17** wrong payer (do NOT make a line of it).
- Binance: "over six billion dollars, attackers inside the signer" — **re-check the figure and date.**
- Test count: ~**446–450** offline tests pass (use the number from the current run).

## 11. Logistics before recording (user-owned, not the agent's)

Disclosure (`DISCLOSURE_AIRWALLEX.md`) has `[12 Nov]` and `[contact]` placeholders — fill before sending; send
before the video/repo goes public. Check airwallex.com for a security channel. Script line 8b ("Airwallex has them
first") is spoken **only if the disclosure was actually sent.** Do one full dry run of the app so §2/§4 screens
load. Small amounts (GBP/EUR ≤5), cancel every transfer and delete every test payee after. Pre-record anything with
a short settle window and the "who's unpaid" page count (live numbers have grown). Submission closes 15 Nov (Slack
extension); plan to submit 13 Nov.

## 12. Open questions a script editor could improve (not yet decided)

- §3 (Metal/Binance): is it earning its ~40s, or does it dilute the Airwallex-payroll thesis? It's the one part not
  about Airwallex. Candidate to trim if the film runs long (the script's own "if over 5:00" note cuts here second).
- Whether to keep the double-pay (#3) as a spoken micro-beat or leave it in the flash — it's the only *live* money
  loss, which is rhetorically strong, but adds a second "bug" voice against the one-hero rule.
- The order of §5 (AI invoice) vs §6 (repoint): both are "the question". §5 motivates "the model isn't a control",
  §6 proves "even a human isn't, if the control binds the wrong thing." Current order builds correctly — don't swap.
