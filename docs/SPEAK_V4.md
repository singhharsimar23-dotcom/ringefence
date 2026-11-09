# What you say (v4: Airwallex's own advice, broken live)

One Loom: Screen + Camera, medium bubble bottom left, 1080p. Save as `var/loom_v4.mp4`.
Talk it like you're showing a friend something you're proud of. If you fumble, pause and redo that paragraph; Claude cuts the bad take.
About 4:50 with the pauses, about 625 spoken words. Hard cap 5:00. If you run long, don't rush: Claude tightens silences in the edit.
The old script, `docs/SPEAK.md`, stays as the fallback.

## How to read the marks

| Mark | What you do |
|---|---|
| **bold** | Lean on that word. Louder or slower, not both. |
| `/` | A tiny beat, half a second. Like a comma, but you actually stop. |
| `//` | A real pause, one full second. Let it land. |
| *(italic)* | How to say the next part. |
| new line | New thought. Take a breath if you need one. |
| [footage] | What's on screen. Don't read it out. |

The rule: **slow down on numbers and on the last words of a section.** Speed up on lists and stories.
The voice stays simple. The footage shows the real thing: terminal, ids, docs, code.

---

## 1 · Open (0:00–0:20)
*(warm, smile, look at the camera)*

Hi, I'm Harsimar, / and I built **Ringfence**. //

*(conversational)*
It's an AI agent / that runs payroll / for **lots** of companies at once.
And I had **one** question: / *(slower)* how do I make sure it **never** pays the **wrong person**? //

[footage: full face. Bam: **"never the wrong person"**]

---

## 2 · The demo (0:20–1:10)
*(lighter, quicker, you're showing it off)*

Three clients: / Northwind, / Kestrel, / and Harbour Foods. /
Each one gets its **own** Airwallex account. /
The agent **suggests**. / My code **decides**. //

I hit **run**.
Kestrel had a normal week, / so it **pays** them. / **Real** Airwallex transfers. /
Northwind changed some pay rates, / so it **waits** for a human. //

*(lean in a little)*
Harbour is **short** on Australian dollars.
So instead of **guessing**, / the agent works out **exactly** what's missing. //

*(a bit sly)*
And here's a **trap**. /
**Fifty thousand dollars** lands in **Kestrel's** account.
*(firm, slower)* That's **Kestrel's** money. / So mine **won't touch it**. //

[footage: the live app run. Bam: "3 employers · 3 Airwallex accounts", "201 SCHEDULED", "held for a human",
"short AUD 1,240.17", "USD 50,000 [SIMULATED] → not touched"]

---

## 3 · Metal (1:10–2:05)
*(drop your voice, slower, this is the serious part)*

So how does Harbour get funded? //

You probably saw **Binance**.
*(slow)* Over **six billion dollars**. / **Gone**. //
It started with a **fake job interview**, / and ended with attackers **inside** the system that **signs** the payments. /
And the money kept **flowing** / for almost **four hours**. //

*(look at the camera)*
So I asked: / what if the wallet **itself** had a limit / that **no stolen key** could get around? //

*(pick the pace back up)*
Harbour signs a rule onto **Metal's** blockchain.
*(count these off)*
**One** payment. / For **exactly** what's missing. / Only into **our** account. / Only for the **next hour**. //

I pull it. / **Real** transaction. /
*(playful)* Then I ask for **one coin more**. / **Refused**. /
A wallet that looks **almost identical**. / **Refused**. //

*(slow, every word)*
Steal my keys **tomorrow**, / and the most you get / is **that one payment**, / into our **own** account. //

[footage: real explorer tabs tx_bind → tx_pull → tx_over → tx_poison. Bam: "1 pull · 85.72 USDZ · 1 h",
"+1 coin → REFUSED", "lookalike → REFUSED"]

---

## 4 · Now Airwallex (2:05–2:20)
*(shift, curious, a little quieter)*

But most payroll doesn't run on a blockchain. / It runs on banks, / on **Airwallex**. //
Binance was beaten at the step that **signs**. /
*(slower)* On Airwallex, / that step is the **approval**. /
So I tested **Airwallex's own advice**. / Live. //

[footage: full face, then Airwallex docs screenshot. Bam: **"Airwallex's own advice. Live sandbox."**]

---

## 5 · Their best agent (2:20–2:40)
*(fair, matter-of-fact)*

First, I built the **best** agent their guidance describes. /
A **frontier** model. / A **human** approving every payment. //
*(give it credit)*
And it's **good**. / Lost replies, / restarts, / double clicks: / **never** paid twice.
It even caught a **fake HR note** / telling it to pay a new account. //

[footage: bench results table, green rows. Bam: "15 faults · 0 double payments"]

---

## 6 · Break one: the approval (2:40–3:15)
*(lean in, slower)*

Then I changed **one** thing. /
The human sees Ben, / two pounds, / and **approves**. /
While it waits, / someone edits Ben's bank. / *(beat)* **Same ID**. //

*(slow, let each one land)*
The right ID. / The right amount. / A human said **yes**. /
And the money went to **someone else**. //
Three times out of **three**. //
*(flat)* On Airwallex's **instant** rail, / that's final in **two seconds**. / No recall. //

*(lighter)*
Ringfence approves the **bank account**, / not the ID. /
It changed? / **Held.** / Nothing moves. //

[footage: `breakit.py approval` terminal, red ✗ "paid … → ..9901", then the green Ringfence line.
Bam: "approved ✓ · paid ..9901 ✗ · 3/3", then green "HELD · 0 moved"]

---

## 7 · Break two: payroll batches (3:15–3:45)
*(building)*

Next, / the batch API / Airwallex pitches for **payroll runs**. //
The batch shows the reviewer / *(beat)* **no bank account**. / None. //
Edit the payee, / submit, / and it pays the **edited** account. / **Four** out of **four**. //
*(flat, deadpan)* And cancel it? / "Admin permissions required." //

Ringfence sends the approved bank details **with** the payment. / There's nothing left to **swap**. //

[footage: `breakit.py batch` terminal, "bank details shown to reviewer: NONE", red BOOKED → ..9901, red 401.
Bam: "no bank shown · 4/4 to ..9901 · can't cancel"]

---

## 8 · Break three: the docs (3:45–4:10)
*(quicker, a bit incredulous)*

A payment's reply gets **lost**. /
Airwallex's own error table says: / retry with a **new** ID. //
So I did. /
*(slow)* **Two** pounds moved / for a **one**-pound payment. / **Settled**. / No cancel. //

Ringfence **never** makes a new ID. / Same ID, / finds the original, / moves it **once**. //

[footage: docs screenshot "Retry the request with a new request_id", then `breakit.py retry`.
Bam: "GBP 2 for GBP 1 · SETTLED", then green "moved once"]

---

## 9 · Break four: who's been paid? (4:10–4:30)
*(steady, no drama, the numbers do the work)*

Then the job that checks / **who's been paid**. /
Airwallex's payouts guide says: / page through with `page_num`. /
The API **ignores** it. / Page one, / page two: / the **same** hundred payments. //
*(slow)* On Northwind's real history, / **ninety-nine** of a hundred and ninety-nine / looked **unpaid**. /
Pay them again, / and **sixty-six** people are paid **twice**. //

Ringfence reads the real cursor, / and won't sign off on a partial list. //

[footage: guide screenshot "page_num, page_size", then the recorded `bench/probes/transfers-pagination-page-num-ignored.out.txt`
(not a live run: live counts have grown and wouldn't match the voice). Bam: "page_num ignored · 99 of 199 'unpaid' · 66 paid twice"]

*(matter-of-fact, quicker)*
**Fifteen** findings, / each with a **receipt**. / Including the one we **couldn't** reproduce. //

[footage: 2-second scroll of docs/AIRWALLEX_GAPS.md summary table, status column visible, the "not reproduced" #6 row on screen]

---

## 10 · Why ours is different (4:30–4:50)
*(slow, to the camera, this is the point)*

Every one of these / is the **same** mistake. //
The check looks at a **label**: / an ID. /
The money follows what the label **points to**. //
Ringfence checks **the thing itself**. //

*(fair, warm)*
And to be fair to Airwallex: / their walls between accounts **held**. / Every single time.
One client can **never** touch another client's money. //

[footage: the 401 `credentials_invalid` terminal shot. Bam: **"Airwallex checks the label. Ringfence checks the account."**]

---

## 11 · Close (4:50–5:00)
*(relaxed, to the camera)*

It's **live**. / Try to break it yourself. //
*(slow, calm, no sell)*
How do I make sure an AI agent / **never** pays the wrong person? //
*(beat, then simply)*
**That's** Ringfence. //

[footage: end card: Ringfence · "Check it out" · github.com/singhharsimar23-dotcom/ringefence · live URL. Small music build.]

---

## Stress test (Claude's checklist before the edit; don't read this out)

| Spoken claim | Receipt | Status |
|---|---|---|
| Binance, over six billion, fake job interview, about four hours | Old film's evidence screenshots | Same wording as v3, minus "last week". Re-check the date is still right. |
| Ringfence would have stopped Binance | Not said. Line 3 says only "the most you get is that one payment" | OK (honesty rule) |
| "15 faults · 0 double payments", fake HR note caught | `docs/BENCH.md`: lost, restart, double, reexport, repoint 3/3 each; inject 3/3 refused | OK. 15 counts lost, restart, reexport, double, repoint; inject is the HR note. |
| Approval: 3/3 to someone else | `22c0a5d8…`, `49a84d09…`, `0d0b978b…` | OK |
| Ringfence holds it | `ringfence-approval-*.json`, 3/3 HELD | OK |
| Batch shows no bank, 4/4, "Admin permissions required" | `f5bd21a8…`, `f1cd2e93…`, `66404ad8…`, `f72b2134…`; `batch_draft.out.txt` | OK |
| Ringfence sends the details with the payment | Commit `39a2bf9` (inline sends) | **Needs one live receipt** from `breakit.py batch` before the edit |
| Docs say new ID; GBP 2 for GBP 1, settled, no cancel | `tr_iJL2nwzW…`, `tr_EVfI4fFU…`, `tr_i7K2mR5G…`; docs row quoted verbatim | OK |
| Instant rail final in two seconds, no recall | `sibling-wallet-repoint-airwallex-pay.out.txt`: PAID in 2.11 s, cancel 400 `update_unsupported` | OK. In-place switch to a wallet is refused, so the line doesn't claim the repoint works there. |
| page_num ignored; 99 of 199 unpaid; 66 paid twice | `transfers-pagination-page-num-ignored.out.txt`; 2 verifiers | OK. Show the recorded output, not a live run. |
| Ringfence won't sign off on a partial list | Commit `0e1bcb7` (Proof fails on a stalled cursor) | OK |
| "Fifteen findings, each with a transfer ID" | `AIRWALLEX_GAPS.md` | OK ("receipt", not "transfer ID": some rest on read-only output) |
| "The one we couldn't reproduce" | #6, official MCP payer, 0/17 | OK. This is the rigour signal. |
| Walls between accounts held | 401 `credentials_invalid`; 400 on a cross-tenant beneficiary id | OK |
| Not called a vulnerability | The script says "mistake" and "advice" only | OK |

**Cut from v3, and why:**
- The four-decisions panels, batch hash and MCP tool list were explainers. The breaks prove the same points with receipts.
- The gauntlet numbers (28 attacks, 200/200, 500 runs) are crowded out. Put them back as one Bam over section 9 if there's room.
- SDK retry (#5), PAID→FAILED (#10), payload-blind dedupe (#8), cancel lag (#11): real, but each needs a fault or a long explanation to land. They're covered by the "fifteen findings" flash. Pagination is in, as section 9, because it has the hardest number.
- #6 (MCP payer) isn't claimed: 0/17. #12–15 aren't spoken: loss not shown.
- If the Loom runs over 5:00, cut section 9's "Fifteen findings" line first, then section 5's HR-note line.
