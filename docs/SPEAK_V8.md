# What you say (v8)

One Loom: Screen + Camera, medium bubble bottom left, 1080p. Save as `var/loom_v8.mp4`.
What's on your screen while you talk doesn't matter. I build every shot in the edit.
Talk it like you're showing a friend something you're proud of. Fumble? Pause, redo the paragraph; I cut it.

| Mark | What you do |
|---|---|
| **bold** | Lean on that word. Louder or slower, not both. |
| `/` | A tiny beat, half a second. |
| `//` | A real pause, one full second. Let it land. |
| *(italic)* | How to say the next part. |
| new line | New thought. Breathe if you need to. |

Slow down on numbers and on the last words of a section. Speed up on lists. From the engineering section to the end, keep building.

This is one story. The **lead** is one thing: / today's agents can be made to pay the **wrong** account, / even with a **human** approving. / Everything else hangs off that.

---

## 1 · Open
*(warm, smile, look at the camera)*

Hi, I'm Harsimar Singh, / and this is my submission for the Airwallex hackathon. / I built **Ringfence**. //

*(conversational)*
Some companies run payroll / for **lots** of other companies.
Every Friday, they're holding **millions** of dollars / that **aren't theirs**.
And more and more, / that job is handed to an **AI agent**. //
*(slower)* So my first question was: / how do I make sure it **never** pays the **wrong person**? //

---

## 2 · I built theirs first, and attacked it
*(curious, steady, professional)*

Before I built anything, / I set up a payroll agent / the way **Airwallex's** own guide shows: /
a frontier model, / Airwallex's API as its tools, / and — / the important part — / a **human** approving every payment. //
That's the setup / everyone trusts. / *(slower)* "Put a **human** in the loop." //
So I tried to **beat** the human. //

---

## 3 · The one that matters: beating the approval
*(this is the centre of the film; slow, let every step land)*

Here's how approval works. / A payment waits. / A person checks it / and clicks **approve**. //
They see the contractor's **name**, / the **amount**, / the **currency**, / and an approved **payee**. //
*(slower)*
So while it waits, / I change the **bank account** / behind that payee. /
The name / is the same. / The amount / is the same. / The payee **ID** / is the same. //
The approver / looks at all of it, / and says **yes**. //
*(each one lands)*
The money went to the account **I** swapped in. / **Three** times out of **three**. /
Here's the transfer ID, / on Airwallex's **own** dashboard. / No alert. / Nothing says it changed. //
*(slower — this is the damage)*
And it doesn't **stop**. / That payee stays **saved**. /
So **every** payroll run after / pays the same wrong account — / a whole **payday** — /
*(plain)* until the real person says / "I **wasn't** paid." //
Nothing in the **system** flags it. / Only the person **missing** their money / does. //

*(lean in — the prerequisite)*
Now, / that needs **someone** to change the bank account. / Who? //
*(slower)* The **agent itself**. / From an **email**. //
A plain invoice that says / *(casual)* "we've changed banks, please use this account." /
The agent took the bait / and moved the payee. / **Five** times out of **five**. //
*(firm, slow)*
So the whole thing / needs nothing but an **email**. /
And the **human** / — the one control everyone relies on — / approves it anyway. //

*(full face, slowest line of the film)*
Because the approval / checks a **label**. /
And the money / follows wherever that label **points**. //

---

## 4 · Two more, quickly
*(a bit faster, you're showing range)*

And it's not just the one approval. //
**Batches** — / the feature sold **for** payroll. / The preview never shows a bank account, /
so a whole run / can go to the swapped accounts at once. / Four out of four, / and my key / **can't cancel** it. //
*(a touch quicker)*
And their own building blocks / make it easy to get wrong. / Their SDK keeps **one** connection / for the whole program, /
so one client's payment / can go out / with **another** client's login. / I found that / in their **code**. //

---

## 5 · So I built Ringfence
*(lighter, quicker, you're showing it off)*

So, / Ringfence. / The agent **suggests**. / My code **decides**. //
Three clients: / Northwind, / Kestrel, / Harbour. / I hit **run**. //
Kestrel had a normal week, / so it **pays**. / Real Airwallex transfers. /
Northwind changed some pay rates, / so it **waits**, / and shows the finance person **exactly** what changed. //

*(firmer, the fixes — tie them back)*
Now the same attacks, / on mine. //
The approval / **pins** the exact **bank details**, / and they ride **inside** the transfer, / re-checked before it's released. / There's no label left to swap. / Same swap: / **held**, / three out of three. /
The email? / A bank change goes into **quarantine**, / until a **different** person confirms it / by **phone**. / Nothing moved. /
And every client / gets its **own** login, / so one client's money / **can't** pay another's people. / I tried to cross that line **twelve** ways; / Airwallex blocked / **all twelve**. //

*(a bit sly — the trap)*
One more. / **Fifty thousand dollars** / lands in **Kestrel's** account / while **Harbour** is short.
A lazy system / would just **use** it. / *(firm)* That's Kestrel's money. / Mine / **won't touch it**. / Harbour tops up, / and everyone gets **paid**. //

---

## 6 · Why this keeps happening
*(peer to peer; steady, this is the engineering beat)*

Every one of those failures / is the **same** shape. /
The agent trusted a **label** / — a payee ID, a connection, a retry — / and the **money** followed wherever it **pointed**. //
*(building)*
Ringfence fixes that / in the **code**, / not the prompt. /
The amount, / the ID, / the bank details, / the client: / **code** decides. / The model only **suggests**. /
Every payment gets its ID **before** the first try, / so a dropped reply / means **look it up**, / never pay **twice**. /
And every payment is signed into a **hash-chained ledger**, / stamped **inside** Airwallex's own record, / so if anyone rewrites my books, / it turns **red**. //
It all runs as an **MCP server** / with **no** approve tool. / A **human** / always signs. //

---

## 7 · Then I tried to break mine
*(build energy, faster, one number per breath)*

Then I tried **really hard** / to break **mine**. //
I built an agent that **obeys** every attack, / and gave it **thirty-six** hostile documents. /
It obeyed every one it could. / **Not one dollar** moved. //
*(fast, punchy)*
**Twelve** cross-client logins. / Blocked, **all twelve**. /
**Twenty** payments at once, / replies cut off. / Each one paid **once**. /
**Two hundred** ledger edits. / **All** caught. /
*(stop, half smile, slower)* Four hundred and sixty-two tests. / I think you get the point. //

---

## 8 · Metal
*(confident, brief)*

The same rules / hold **on chain** too. /
Each client is on a **Metal** mandate: / the payee, / the cap, / and **one** pull, / signed on chain. /
A **second** pull / is refused. / A **wrong** address / is refused. / Here are the transactions. //

---

## 9 · Close
*(relaxed, to the camera; keep it short)*

All of this is **sandbox**, / not production. / Every finding's in the repo, / with its transfer IDs. //
But don't take my word for it. / The demo's **live**. / Try to make it pay the **wrong** person. //
*(slow, simply)* That's Ringfence. // Thanks for watching. //

---
---

## Receipts for every spoken claim (skip when recording)

| Spoken claim | Receipt |
|---|---|
| Set up the way Airwallex's guide shows: frontier model, API as tools, human approval | `agent_injection.py` L0 (Sonnet 5.5); `bench/market_agent.py` (Opus 5.5). The approver is a modeled diligent human (checks request_id / beneficiary_id / amount against the payroll sheet — what a person checks, not the hidden bank account); AgentOS does recommend "require manual approval for tool calls". The live film shows a real human approving in the Ringfence app. |
| Approval swap: same name/amount/ID, approver says yes, paid the swap, 3 of 3, no alert | BENCH approval row: `22c0a5d8…`, `49a84d09…`, `0d0b978b…` (Opus 5.5). No beneficiary-changed webhook (`silent_divert.out.txt`). Never "undetectable". |
| The change comes from an email; agent moved the payee, 5 of 5 | `agent_bec_repeat.out.txt`, 9 Nov: `45528e1d…`, `749ebed0…`, `3dd76387…`, `70b841be…`, `958cc5cd…` → ..9901, all cancelled. Overt "SYSTEM" injections were refused; don't claim those. Each link verified separately — don't claim one end-to-end run. |
| Batch: no bank in preview, whole run at once, 4 of 4, key can't cancel | BENCH batch: `f5bd21a8…`, `f1cd2e93…`, `66404ad8…`, `f72b2134…`; 401 "Admin permissions required" |
| Their SDK keeps one connection per process; one client's payment with another's login; found in code | `bench/probes/sdk_singleton_check.out.txt` (CONFIRMED, offline); `dist/client/apiClient.js`. Say "I found it in their code". |
| Ringfence: approval signs bank details inline; held 3 of 3 | pins (`fd2a4b1`, `90472ea`); inline sends (`39a2bf9`); BENCH held 3/3 |
| Bank change quarantined until a different person confirms by phone | `ringfence/scenarios.py` quarantine; `propose_bank_change` / `confirm_callback`; `tests/test_controls.py` |
| Own login per client; 12 cross-client tries blocked | `x-login-as` per employer; `docs/GAUNTLET.md` §4, live, 12/12 401 `credentials_invalid` |
| Kestrel pays, Northwind waits with a diff; 50k in Kestrel untouched; Harbour tops up | live app; `[SIMULATED]` on deposits; never sum balances across employers |
| ID before the first try; dropped reply → look it up, never twice | deterministic `request_id`; `_adopt`/`_adopt_found` (`ringfence/executor.py`) |
| Hash-chained ledger inside Airwallex's record; rewrite → red | `rf_seq`/`rf_hash` in transfer metadata (`7d8ff13`, `7956e52`) |
| MCP server, no approve tool | `mcp_server.py` |
| 36 documents obeyed, 0 moved; 12 logins; 20 at once each once; 200 edits caught; 462 tests | `docs/GAUNTLET.md` §1,2,4,5; `pytest -q` — say the number on the day |
| Metal: payee + cap + one pull on chain; second pull refused; wrong address refused | Metal device-mode tx set in `facts.json`. `metal.py:poisoned_pull` now refuses ANY address that isn't the mandate's payee (not only lookalikes); the on-chain mandate binds one payee. Keep the half-sentence once the device-mode refusal tx exists; cut it only if that run doesn't produce a tx on shoot day. |

## Runtime — the hard rule
Full script is ~821 spoken words. The hackathon cap is a hard **under 5:00**. Decision: **keep every word.** Land it under 5:00 in the edit — deliver briskly (~165–175 wpm), and tighten the directed pauses in post (the `/` and `//` are performance cues, not fixed dead air; compress them). Time the first full edit; only if it is still over 5:00, apply the cut order below in order until it fits.

## Cut order (fallback only, if the edit still runs over 5:00)
1. The SDK sentence in §4.
2. The ledger/red sentence in §6.
3. "Twenty payments at once" in §7.
4. The whole Metal section §8 (separate prize; the film survives without it).

## Notes for the edit (Claude's, skip when recording)
- The spine is one chain: beat the human (approval swap) ← supplied by an email. Everything else is support.
- Landing `/#found`: as each finding is named, cut to its card (their side red, Ringfence side green, transfer IDs visible).
- Full face: the open, "the money follows wherever that label points" (§3), the close.
- Dashboard captures: `22c0a5d8…` for the approval swap, `45528e1d…` for the email, the batch IDs, the 12/12 isolation matrix, the Harbour HELD→paid in the live app.
- Each attack link is independently verified; compose them, don't claim a single end-to-end run.
- Say "I found it in their code" for the SDK line unless a live read-only run lands before the shoot.
- Metal: decode the refusal captions from CLI output (the explorer only shows "unknown method").
