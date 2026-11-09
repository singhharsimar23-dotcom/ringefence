# What you say (v5: product first, then the gap it closes)

One Loom: Screen + Camera, medium bubble bottom left, 1080p. Save as `var/loom_v5.mp4`.
Same delivery as v4: talk it like you're showing a friend. Fumble? Pause, redo the paragraph; Claude cuts it.
About 4:50 with pauses, about 640 spoken words. Hard cap 5:00.
Fallbacks: `docs/SPEAK_V4.md` (breaks-heavy), `docs/SPEAK.md` (v1).

**What changed from v4, and why.** The judges score finance value, Airwallex relevance, agent behaviour and
execution, on goal → plan → new information → revised decision → final balance (`PLAN.md` §1). v4 gave the
product 50 seconds and Airwallex's gaps two and a half minutes. v5 flips that: **~2:25 product, ~1:45 gap +
how we close it.** One hero break (the approval, 3/3), not four. The AI beat is told honestly: it worked
**once in five**, and that's the point.

**Before recording:** the disclosure (`docs/DISCLOSURE_AIRWALLEX.md`) is sent. Line 8b is only said if it was.

Marks: **bold** lean · `/` half-second beat · `//` full pause · *(italic)* how to say it · [footage] not read out.
Slow down on numbers and on the last words of a section.

---

## 1 · Open (0:00–0:15)
*(warm, smile, to the camera)*

Hi, I'm Harsimar, / and I built **Ringfence**: / an AI agent that runs payroll / for **lots** of companies at once. //
*(slower)* My one question: / how do I make sure it **never** pays the **wrong person**? //

[footage: full face. Bam: **"never the wrong person"**]

---

## 2 · The run (0:15–1:15)
*(lighter, quicker, showing it off)*

Three clients: / Northwind, / Kestrel, / Harbour Foods. /
Each has its **own** Airwallex account. / The agent **suggests**. / My code **decides**. //

I hit **run**. / The agent reads every timesheet and email.
Kestrel had a normal week, / so it **pays**. / **Real** Airwallex transfers. /
Northwind changed a pay rate, / so it shows a human **what changed**, / and **waits**. //

*(lean in)*
Harbour is **short**. / Twelve hundred and forty Australian dollars. /
The agent doesn't guess. / It says **exactly** what's missing, / and the **deadline** to fund it. //

*(a bit sly)*
Then, / new information. / **Fifty thousand dollars** lands in **Kestrel's** account.
A lazy system sees money / and pays Harbour with it. /
*(firm, slower)* That's **Kestrel's** money. / Mine **won't touch it**. / Harbour stays **held**. //

[footage: live app run. Bam: "3 employers · 3 Airwallex accounts", "201 SCHEDULED", "waiting · shows what changed",
"short AUD 1,240.17 · fund by …", "USD 50,000 [SIMULATED] → Kestrel only · Harbour HELD"]

---

## 3 · Harbour funds itself (1:15–1:55)
*(drop your voice, serious)*

So how does Harbour pay in, / safely? //
You saw **Binance**: / over **six billion dollars**, / because attackers got **inside** the system that signs. //

*(pick up pace, count off)*
So Harbour signs a rule onto **Metal's** blockchain: / **one** payment, / **exactly** what's missing, / only into **our** account, / only for the **next hour**. //
I pull it. / **Real** transaction. /
*(playful)* One coin **more**? / **Refused**. / A lookalike wallet? / **Refused**. //
*(slow)* Steal my keys tomorrow, / and the most you get / is **that one payment**, / into our **own** account. //

[footage: explorer tabs tx_bind → tx_pull → tx_over → tx_poison. Bam: "1 pull · 1 h", "+1 coin → REFUSED", "lookalike → REFUSED"]

---

## 4 · Revised decision, and proof (1:55–2:40)
*(release, lighter)*

The money lands. / The agent **re-plans**, / and Harbour is **paid**. //

*(confident, matter-of-fact)*
Now prove it. / This is the **real** Airwallex dashboard: / the **same** transfer IDs. /
I tried Northwind's login / on **Kestrel's** account. / Airwallex **blocked** it. /
And if anyone edits **one row** of my ledger, / *(beat)* the proof turns **red**. //

[footage: app shows Harbour PAID; Airwallex web app transfer list; terminal 401 `credentials_invalid`;
tamper card → Proof red → restore → green. Bam: "every debit · its own employer · its own run"]

---

## 5 · The question that kept me up (2:40–3:10)
*(shift, quieter, curious)*

But here's what kept me up. /
A payroll agent's **whole job** / is reading emails and invoices. /
So I sent a plain agent, / built the **usual** way, / a normal-looking invoice: / *(casual voice)* "our bank details changed." //
*(slow)* It paid **the attacker**. / **Once**, / in **five** tries. //
The other four, / it refused, / and asked for a **phone call** to check. //
*(to the camera)* That's a good model. / But "usually" / isn't a **control**. //

[footage: `agent_injection.out.txt` L0 line, "PAID THE MULE … ..9901", then the four refusals.
Bam: "1 of 5 · paid the attacker", then "the model is a filter, not a control"]

---

## 6 · Fine. Add a human. (3:10–3:55)
*(lean in, slower)*

So, / add a human. / That's what Airwallex's agent guidance says. /
I did. / A **strong** model, / a careful approver. /
The approver sees Ben, / two pounds, / and says **yes**. /
While it waits, / Ben's bank account is **edited**. / *(beat)* **Same ID**. //

*(slow, each one lands)*
Right ID. / Right amount. / A human said **yes**. /
The money went to **someone else**. / **Three** times out of **three**. //
*(flat)* And nothing on the platform **flags** it. / No event. / No change history. /
The first alarm / is Ben saying / *(beat)* "I wasn't paid." //

[footage: `breakit.py approval` red ✗ "paid … → ..9901". Bam: "approved ✓ · paid ..9901 ✗ · 3/3", "no event · no audit field"]

---

## 7 · How did we miss it (3:55–4:15)
*(slow, to the camera, the peak)*

And **every** piece of that / is **reasonable**. /
Approve the ID. / Let people update a payee. / Keep the screen simple. / Let the AI read the mail. //
*(slower)* No one owns the **gap between** them. / That's where the money **leaks**. //

[footage: full face. Bam: **"The check reads a label. The money follows what it points to."**]

---

## 8 · Ringfence holds (4:15–4:45)
*(lighter, firm)*

Same invoice, / **my** agent: / the bank change is **quarantined** / until a **different** person confirms it by **phone**. /
Same edit, / mid-approval: / Ringfence approved the **bank account**, / not the ID. / It changed? / **Held**. / Nothing moves. //

*(fair, warm)*
And to be fair to Airwallex: / the walls between accounts **held**, / every time. / Amount, / payer, / FX: / all bound. //
*(quicker)* **Fifteen** findings, / each with a **receipt**, / including the one we **couldn't** reproduce.
**(8b, only if sent)** / And Airwallex has them **first**. //

[footage: `agent_injection.out.txt` L2 "QUARANTINED" + "FLAGGED"; `ringfence-approval-*.json` "3/3 HELD · 0 moved";
2-second scroll of `AIRWALLEX_GAPS.md` summary table with the #6 "not reproduced" row]

---

## 9 · Close (4:45–4:55)
*(relaxed, to the camera)*

It's **live**. / Try to break it yourself. //
*(slow, calm)* How do I make sure an AI agent / **never** pays the wrong person? //
*(beat)* The agent **suggests**. / My code **decides**. / **That's** Ringfence. //

[footage: end card: Ringfence · repo URL · live URL.]

---

## Stress test (Claude's checklist before the edit; don't read this out)

| Spoken claim | Receipt | Status |
|---|---|---|
| Kestrel paid, real transfers | live app run, 201 SCHEDULED | Capture on the take |
| Northwind shows what changed and waits | approval-as-diff in app | Capture on the take |
| Harbour short AUD 1,240.17 + deadline | `copy.py` "fund by {act_by}" | Capture; read the number off the screen if it differs |
| USD 50k to Kestrel, not touched | `[SIMULATED]` deposit, Harbour HELD | Capture; the `[SIMULATED]` label must be visible |
| Binance, over six billion, attackers inside the signer | Old film's evidence | **Re-check figure and date** before recording |
| Metal: 1 pull, +1 refused, lookalike refused | tx_bind / tx_pull / tx_over / tx_poison | OK (v4 footage) |
| Harbour paid after funding | live app run | Capture on the take |
| Same IDs on the Airwallex dashboard | web app transfer list | Capture |
| Cross-tenant login blocked | 401 `credentials_invalid` | OK |
| Edit one ledger row → proof red | tamper card + `/api/proof`; `tests/test_verify.py` | Capture tamper → red → restore → green |
| Plain agent paid the attacker once in five | `agent_injection` L0 1/2, `agent_blast` 0/1, `agent_blast_subtle` 0/2 | OK. "Built the usual way" = ours, not Airwallex's. Never say "Airwallex's agent". |
| The other four refused, asked for a phone call | refusal text in the `.out.txt` files | **Check the wording** of each refusal before saying "asked for a phone call"; if not all four, say "and some asked for a phone call" |
| Airwallex's agent guidance says add a human | AgentOS "require manual approval" (`AIRWALLEX_GAPS.md` §1) | OK. Say "agent guidance", not "approval screen": the native web-app workflow was not tested |
| Strong model, careful approver, 3/3 to someone else | Gap 1: Opus 5.5 high effort; `22c0a5d8…`, `49a84d09…`, `0d0b978b…` | OK |
| No event, no change history | no beneficiary-changed webhook; payee object has no audit field (`silent_divert.out.txt`) | OK |
| "First alarm is Ben saying I wasn't paid" | follows from the line above | OK. Deliberately **not** "for months" |
| Quarantined until a different person confirms by phone | `agent_injection` L2 QUARANTINED; `propose_bank_change` | OK |
| Mid-approval edit → HELD, nothing moves | `ringfence-approval-*.json` 3/3 HELD | OK |
| Walls held; amount, payer, FX bound | 401/400 cross-tenant; `amount_binding`, `fx_quote_binding` `.out.txt` | OK |
| Fifteen findings, one not reproduced | `AIRWALLEX_GAPS.md`, #6 0/17 | OK |
| "Airwallex has them first" | disclosure sent | **Say only if sent before recording** |
| Not called a vulnerability | script says "gap", "flags", "leaks" | OK |

**Cut from v4, and why:** batch (#2), docs double-charge (#3) and pagination (#4) as hero beats: they're real
but turn the film into a bug hunt; they live in the "fifteen findings" flash. Idempotency substitution (D):
Sev-4, needs the attacker already inside. "15 faults · 0 double payments" bench line: no room.

**If it runs over 5:00:** cut section 7's list of four ("Approve the ID…") to two items, then the Binance
sentence in section 3.
