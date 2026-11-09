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

Here's the plan. / One: / the agent **everyone** builds, / and what **broke**. / Two: / **mine**, / and why each part is there. //
First, / the setup / **Airwallex's** own guide shows: / a frontier model, / their API as tools, / and a **human** approving every payment. /
Everyone trusts that. / *(slower)* "Put a **human** in the loop." //
So I tried to **beat** the human. //

---

## 3 · Bug one: beating the approval
*(this is the centre of the film; slow, let every step land)*

A payment waits for approval. / A person checks it / and clicks **approve**. //
They see the **name**, / the **amount**, / the **currency**, / the approved **payee**. //
*(slower)*
While it waits, / I change the **bank account** / behind that payee. /
Same name. / Same amount. / Same payee **ID**. /
The approver says **yes**. //
*(each one lands)*
The money goes to the account **I** swapped in. / **Three** out of **three**. /
Here's the transfer ID, / on Airwallex's **own** dashboard. / No alert. //
*(slower — this is the damage)*
And it doesn't **stop**. / The payee stays **saved**, /
so **every** run after / pays the wrong account — / a whole **payday** —
*(plain)* until the real person says / "I **wasn't** paid." //
No system flags it. / Only the person **missing** their money / does. //

*(lean in — the way in)*
Who changes the bank account? / *(slower)* The **agent**. / From an **email**. //
A plain invoice: / *(casual)* "we've changed banks, please use this account." /
It moved the payee. / **Five** out of **five**. //
*(firm, slow)*
So all it takes is an **email**, /
and the **human** / — the one control everyone relies on — / approves anyway. //

*(full face, slowest line of the film)*
The approval / checks a **label**. /
The money / follows wherever that label **points**. //

---

## 4 · And more, quickly
*(a bit faster, you're showing range)*

Bug **two**: / **batches**, / the feature sold **for** payroll. / The preview never shows a bank account, /
so a whole run goes to swapped accounts **at once**. / Four out of four. / My key / **can't cancel** it. //
Bug **three**: / their SDK keeps **one** connection for the whole program, /
so one client's payment / can go out with **another** client's login. / I found that / in their **code**. //
*(quick, plain)* Then two plain software bugs. /
Their transfer list ignores the page number: / I saw a hundred of two hundred and fifteen, / so a hundred and fifteen paid people looked **unpaid**. /
And their SDK's retry drops the filter: / "did it land?" comes back with **everything**. //

---

## 5 · So I built Ringfence
*(lighter, quicker, you're showing it off)*

So, / Ringfence. / The agent **suggests**. / My code **decides**. //
Three clients: / Northwind, / Kestrel, / Harbour. / I hit **run**. //
Kestrel had a normal week, / so it **pays**. / Northwind changed pay rates, / so it **waits**, / and shows **exactly** what changed. //

*(firmer, the fixes — tie them back)*
Same attacks, / on mine. //
The approval **pins** the exact **bank details**, / inside the transfer, / re-checked at release. / No label left to swap. / Same swap: / **held**, / three out of three. /
The email: / a bank change goes to **quarantine**, / until a **different** person confirms by **phone**. / Nothing moved. /
Every client / has its **own** login. / I tried to cross that line **twelve** ways; / Airwallex blocked **all twelve**. //

*(a bit sly — the trap)*
Harbour was short. / Kestrel's **fifty thousand** / sat right there. / Mine **won't touch it**. / Harbour tops up, / everyone gets **paid**. //

---

## 6 · How it's built
*(peer to peer; steady, this is the engineering beat)*

The amount, / the ID, / the bank details, / the client: / **code** decides. / The model only **suggests**. /
Every payment gets its ID **before** the first try, / so a dropped reply means **look it up**, / never pay **twice**. /
Every payment goes into a **hash-chained ledger**, / stamped **inside** Airwallex's own record. / Rewrite my books / and it turns **red**. /
It runs as an **MCP server** / with **no** approve tool. / A **human** always signs. //

---

## 7 · Then I tried to break mine
*(build energy, faster, one number per breath)*

Then I tried **really hard** / to break **mine**. //
An agent that **obeys** every attack, / **thirty-six** hostile documents. / **Not one dollar** moved. //
*(fast, punchy)*
**Twelve** cross-client logins, / all blocked. / **Twenty** payments at once, / each paid **once**. / **Two hundred** ledger edits, / all caught. /
*(stop, half smile, slower)* Four hundred and sixty-two tests. / You get the point. //

---

## 8 · Metal
*(confident, brief)*

The same rules / hold **on chain**. /
Each client has a **Metal** mandate: / the payee, / the cap, / **one** pull. /
A **second** pull / is refused. / A **wrong** address / is refused. / Here are the transactions. //

---

## 9 · The point
*(slow, to the camera; this is what they leave with)*

So, / the point of all this. //
Today's agents are built like the first one I tried: / a model, / the API, / a human approving. //
That's where **I** found: / the approval swap, / batches, / the SDK, / two plain bugs, / and the email that starts it. //
Ringfence does everything a **normal** agent does: / reads the timesheets, / prices the lines, / pays, / reconciles. //
Then it adds what **each bug** told me to add: / pinned bank details, / quarantine and a phone call, / one transfer per line, / one login per client, / one ID per payment, / a ledger that turns **red**. //
Same agent. / **Hardened**. //

---

## 10 · Close
*(relaxed, to the camera; keep it short)*

All of this is **sandbox**, / not production. / Every finding's in the repo, / with its transfer IDs. /
Don't take my word for it. / The demo's **live**. / Try to make it pay the **wrong** person. //
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
| Two plain software bugs: transfer list ignores page_num (100 of 215, 115 look unpaid); SDK retry drops the filter ("did it land" returns everything) | `uv run python scripts/breakit.py pages sdk`, read-only, live, 9 Nov. The retry result is shown over REST (request_id filter returns 0, unfiltered 215); the dropped-filter line is in the SDK source (`apiClient.js`). Never claim we drove the SDK's own retry in production. |
| The point: a normal agent's features + one hardening per bug | Each fix named in §9 maps to a bug: pinned inline bank details ↔ approval swap; quarantine + phone callback ↔ the email; one transfer per line ↔ batch; own login per client ↔ SDK connection; fixed request_id + lookup ↔ retry and paging; red ledger stamp ↔ tamper. |
| Ringfence: approval signs bank details inline; held 3 of 3 | pins (`fd2a4b1`, `90472ea`); inline sends (`39a2bf9`); BENCH held 3/3 |
| Bank change quarantined until a different person confirms by phone | `ringfence/scenarios.py` quarantine; `propose_bank_change` / `confirm_callback`; `tests/test_controls.py` |
| Own login per client; 12 cross-client tries blocked | `x-login-as` per employer; `docs/GAUNTLET.md` §4, live, 12/12 401 `credentials_invalid` |
| Kestrel pays, Northwind waits with a diff; 50k in Kestrel untouched; Harbour tops up | live app; `[SIMULATED]` on deposits; never sum balances across employers |
| ID before the first try; dropped reply → look it up, never twice | deterministic `request_id`; `_adopt`/`_adopt_found` (`ringfence/executor.py`) |
| Hash-chained ledger inside Airwallex's record; rewrite → red | `rf_seq`/`rf_hash` in transfer metadata (`7d8ff13`, `7956e52`) |
| MCP server, no approve tool | `mcp_server.py` |
| 36 documents obeyed, 0 moved; 12 logins; 20 at once each once; 200 edits caught; 462 tests | `docs/GAUNTLET.md` §1,2,4,5; `pytest -q` — say the number on the day |
| Metal: payee + cap + one pull on chain; second pull refused; wrong address refused | Metal device-mode tx set in `facts.json`. `metal.py:poisoned_pull` now refuses ANY address that isn't the mandate's payee (not only lookalikes); the on-chain mandate binds one payee. Keep the half-sentence once the device-mode refusal tx exists; cut it only if that run doesn't produce a tx on shoot day. |

## Runtime: the hard rule
~794 spoken words, about 4:30 of pure speech at 175 wpm. The hackathon cap is a hard **under 5:00**. Deliver briskly and tighten the directed pauses in post (`/` and `//` are performance cues, not fixed dead air). Time the first full edit. Only if it is still over 5:00, apply the cut order below in order.

The structure orients the viewer on purpose: §2 gives a two-step plan (theirs, then mine), §3 to §4 number the bugs, §9 states the point (a normal agent's features plus one hardening per bug). Do not cut §2's plan line or §9.

## Cut order (fallback only, if the edit still runs over 5:00)
1. "Twenty payments at once" and "Two hundred ledger edits" in §7.
2. The ledger / red sentence in §6.
3. The SDK retry-filter line in §4 (keep the page-number bug and the SDK connection bug).
4. The trap lines at the end of §5 (Harbour / Kestrel's fifty thousand).
5. The whole Metal section §8 (separate prize; the film survives without it).

## Notes for the edit (Claude's, skip when recording)
- The spine is one chain: beat the human (approval swap) ← supplied by an email. Everything else is support.
- Landing `/#found`: as each finding is named, cut to its card (their side red, Ringfence side green, transfer IDs visible).
- Full face: the open, "the money follows wherever that label points" (§3), the close.
- Dashboard captures: `22c0a5d8…` for the approval swap, `45528e1d…` for the email, the batch IDs, the 12/12 isolation matrix, the Harbour HELD→paid in the live app.
- Each attack link is independently verified; compose them, don't claim a single end-to-end run.
- Say "I found it in their code" for the SDK line unless a live read-only run lands before the shoot.
- Metal: decode the refusal captions from CLI output (the explorer only shows "unknown method").
