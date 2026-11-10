# What you say (v10, final)

One Loom: Screen + Camera, medium bubble bottom left, 1080p. Save as `var/loom_v10.mp4`.
What's on your screen doesn't matter; every shot is built in the edit. Say it like you're telling a friend what you found. If you fumble, pause and redo the paragraph.
Say the technical word, then what it means in plain words. The screen carries the detail: the IDs, the code and the analysis. Your voice carries the story.

| Mark | What you do |
|---|---|
| **bold** | Lean on that word. |
| `/` | A tiny beat. |
| `//` | A real pause. Let it land. |
| *(italic)* | How to say the next part. |

---

## 1 · Open
*(warm, to the camera)*

Hi, I'm Harsimar Singh, / and this is **Ringfence**, / my submission for the Airwallex hackathon. //

Some companies run payroll for **lots** of other companies.
Every Friday they're holding **millions** of dollars that **aren't theirs**. //
*(slower)* So my first question was: / if an **AI agent** does that job, / how do I make sure it **never** pays the **wrong person**? //

---

## 2 · Break it first
*(conversational, a bit curious)*

Airwallex is building for exactly this: / agents that **move money**.
And their guide shows how you'd build one: / a frontier model, / their API as its tools, / and a **human** approving every payment. //
So before I built mine, / I built **that one**, / and spent days trying to **break** it.
All on the sandbox, / my own accounts, / a few pounds, / everything cancelled after. /
If something breaks **there**, / it breaks in **every** agent built the same way. /
So the best way to build mine / was to break theirs **first**, / and harden against **everything** I found. //
*(plain, fair)* Airwallex kept every client's money **separate**, every time.
This is about what an **agent** falls for. //

---

## 3 · What I found
*(slow down; this is the centre of the film)*

The worst one / beats the **human**. //
A payment's waiting for approval.
The approver checks the name, / the amount, / the payee. / All correct. / They click **yes**. //
But while it was waiting, / the **bank account** behind that payee got changed.
Same name, / same ID. /
The money goes to the **new** account. / **Three** out of **three**, / no alert. //
And that payee stays **saved**, / so it keeps paying that account, / run after run, /
*(plain)* and nothing in the system would **know**. //

So who changes the bank account? / *(slower)* The **agent** does. / From an **email**. //
A normal-looking invoice: / *(casual)* "we've changed banks, please use this account." /
And it updated the payee. / **Five** out of **five**. //
*(full face, slowest line of the film)*
The approval checks a **label**. /
The money follows wherever that label **points**. //

*(a bit quicker; you're showing range)*
And once I saw that, / I kept finding the **same** shape.
Their Node SDK keeps **one** login for the whole program. /
Make a client per employer, / and Northwind's payment goes out on **Kestrel's** login. / I found that in their **code**. //
Their MCP gives every payment a **new** ID, /
so if a reply gets lost and the agent tries again, / that's a **second** payment.
I ran that retry live: / one pound owed, / **two** moved, / no cancel. //

---

## 4 · So I built Ringfence
*(lighter, you're proud of it)*

So after all that, / here's what I built. / Ringfence. / The agent **suggests**. / My code **decides** what moves. //
Three clients, / Northwind, / Kestrel / and Harbour, / each on its **own** Airwallex account.
The goal: / pay everyone's contractors this week. / I hit **run**, / and the agent reads the timesheets and the inbox / and plans all three. //
Kestrel had a normal week, / so it **pays**. /
Northwind changed pay rates, / so it **waits** for their finance person, /
and converts the Australian dollars it needs, / only inside the rate its rules allow. //

*(lean in; this is where the plan changes)*
Then the week changes. /
Harbour is **short** in Australian dollars, / and its rules say **no** conversion. /
So the agent **revises** the plan: / it holds Harbour, / works out **exactly** what's missing, / and asks Harbour to top up its **own** account / before the deadline. //
*(a bit sly)* Then **fifty thousand** dollars lands in **Kestrel's** account. /
*(firm)* That's **Kestrel's** money, / so Ringfence **won't touch it**. //
Harbour's top-up lands in its Airwallex **global account**, / the agent matches it, / and pays. /
Everyone's **paid**, / and every client's balance / is still its **own**. //

---

## 5 · Every attack, again, on Ringfence
*(firmer; tie each fix to its bug)*

Then I ran every attack from the hunt / again, / on Ringfence. //
The approval swap: / Ringfence signs the exact **bank details** into the approval / and sends them **inside** the transfer. / No label left to swap. / **Held**, / three out of three. //
The email: / a bank change goes into **quarantine** / until a **different** person confirms **by phone**. //
The retry: / every payment gets its ID **before** the first try, / so a lost reply means **look it up**, / **never** a second payment. //
And each client's **own** login: / I tried crossing that line **twelve** ways. / Airwallex blocked **all twelve**. //

---

## 6 · For the engineers
*(peer to peer, quicker, one fix per breath)*

Quick one for the **engineers**. //
Webhooks are a **hint**; / I re-fetch every one from Airwallex. //
Every action goes into a **hash-chained** ledger, / and its head is stamped **inside** each Airwallex transfer. /
Rewrite my database, / re-hash the whole chain, / and Airwallex's copy **still** disagrees. //
And it runs as an **MCP server** / with **no** approve tool. / A **human** always signs. //

---

## 7 · Then I attacked it myself
*(build energy; every number is a test you can open)*

Then I attacked Ringfence myself. //
I gave it an agent that obeys **every** attack / and thirty-six hostile documents. / **Not one dollar** moved. /
Twenty payments at once, / replies dropped: / each paid **once**, / by Airwallex's own count. /
I edited the ledger two hundred times. / Every edit **caught**, / at the right row. /
And four hundred and sixty-two tests / run against a fake Airwallex. //
*(relaxed, to the camera)*
But don't take my word for it. / The demo's **live**. / Try to make it pay the **wrong** person. //

---

## 8 · Close
*(slow, to the camera)*

It's still a **normal** payroll agent, / with **one fix** / for every way I broke the first one. //
It's all **sandbox**, / and every finding is in the repo with its transfer IDs. //
*(slow, simply)*
So, / back to my first question: / how do I make sure an AI agent / **never** pays the wrong person? //
**That's** Ringfence. // Thanks for watching.

---
---

## Receipts for every spoken claim (skip when recording)

| Spoken claim | Receipt |
|---|---|
| Their guide's agent: frontier model, API as tools, a human approving | AgentOS "require manual approval for tool calls"; `bench/market_agent.py` (Opus 5.5). The approver is a modelled diligent human who checks id, amount and currency. |
| Sandbox, own accounts, a few pounds, cancelled after | `AIRWALLEX_GAPS.md` "Safety": writes only to Northwind and Kestrel, GBP/EUR ≤ 5, every transfer cancelled where the API allows, the CA double payment reversed by hand, throwaway payees deleted |
| Isolation held every time | `docs/GAUNTLET.md` §4, 12/12 401 `credentials_invalid` live; no cross-tenant 2xx ever |
| Approval swap, 3/3, no alert | `22c0a5d8…`, `49a84d09…`, `0d0b978b…` to ..9901; no beneficiary-changed webhook (`silent_divert.out.txt`) |
| Keeps paying run after run; nothing in the system would know | The payee stays saved, there's no beneficiary-changed event, and the payee has no `updated_at` or version. Honest bound: nothing *alerts*; a reconciler that diffs `/transfers` bank snapshots could spot it, and the contractor notices on payday. Never say "undetectable", "for weeks" or "for months". |
| Agent changes it from an email, 5/5 | `agent_bec_repeat.out.txt`, 9 Nov: `45528e1d…`, `749ebed0…`, `3dd76387…`, `70b841be…`, `958cc5cd…`. Overt "SYSTEM" injections were refused. Each link was verified on its own, not as one run. |
| Batches: no bank account at review; whole run; key can't cancel | `f5bd21a8…`, `f1cd2e93…`, `66404ad8…`, `f72b2134…` (4/4); 401 "Admin permissions required" |
| SDK keeps one login; found in code | `bench/probes/sdk_singleton_check.out.txt`, offline: A's call attached B's token. We checked the token, not a completed payment. |
| MCP: a new ID per payment; a retry is a second payment | `@airwallex/developer-mcp@0.3.0-beta.13` `createTransfer.js`: `request_id: uuid.v4()` per call (code) |
| Retry live: one pound owed, two moved, no cancel | `charges-request-id-duplicate-new-id.out.txt`: `tr_EVfI4fFUMiKaByQv2_pW4w` + `tr_i7K2mR5GNpqv0iirL3-rGg`, both SETTLED, connected-account transfer with no cancel endpoint. It was a REST retry, not one through the MCP: never say "the MCP paid twice", and never cite the docs row. |
| Page number ignored; retry drops filter | `scripts/breakit.py pages sdk`, live, 9 Nov: 100 of 215 seen, so 115 look unpaid; request_id filter returns 0, unfiltered 215, so a never-paid line looks paid; `apiClient.js:157` |
| Each client on its own account; goal; agent plans all three | 4 accounts, `x-login-as` per employer; RUN_CREATED and PLAN rows in the live timeline |
| Northwind converts within its band | `demo/employers.json`: Mia is paid in AUD, setup drains Northwind's AUD, Northwind has `fx: within_band`, 50 bps → FX_QUOTE + FX_CONVERTED with `conversion_id` (`executor.py:_convert`). **Check that the row appears in the shoot-day run**; if it doesn't, cut that sentence. |
| Harbour short, no conversion allowed, exact shortfall, deadline | Harbour has `fx: never`; FUNDING_REQUESTED with amount and `act_by` (`funding.py`) |
| 50k to Kestrel untouched | live card "Another employer's money arrives" `[SIMULATED]`; balances are never summed across employers |
| Harbour's top-up lands in its global account, matched, paid | live card "Harbour's own top-up" (Airwallex simulated deposit to the AUD global account, `[SIMULATED]`); FUNDING_MATCHED, then release |
| Retest: held 3/3; last-second cancel; quarantine; ID before first try; 12/12 | `39a2bf9`; live cards "Swap the bank account after approval" (HELD), "Swap it at the last second" (CANCELLED, fresh world), "Fake bank-change email", "Internet drops mid-payment"; deterministic `request_id` + `_adopt`; `GAUNTLET.md` §4 |
| Lookup checks payee/amount/currency or holds | `_adopt` (`executor.py`); `b9403e6`, `7d8ff13` |
| Cursor paging; items checked | `0e1bcb7`; `transfer_by_request` matches request_id per item |
| Paid isn't final | PAID→FAILED live; card "Payment bounces back" |
| Webhooks are a hint, re-fetched | `webhooks.py`; `executor.py` "A webhook said this transfer changed: GET it and apply" |
| Ledger head inside each transfer; re-hash → disagrees | `rf_seq`/`rf_hash` metadata (`7d8ff13`); card "Change a record and re-hash the chain" |
| MCP server, no approve tool | `mcp_server.py` |
| 36 docs / 0 moved | `GAUNTLET.md` §1: the obedient agent did what 28 asked (8 had no tool); the gate denied all 28 |
| 20 at once, replies dropped, each once, Airwallex's list as referee | `GAUNTLET.md` §2, live: 20 releases, 3 lost answers, transfers per line [1, 1, 1] |
| 200 edits caught at the right row | `GAUNTLET.md` §5 |
| 462 tests vs fake Airwallex | `uv run pytest -q`: say the number on the day |

## Runtime
About 810 spoken words. Your last take ran at about 166 wpm after pause trimming (794 words in 287 s), so expect about 4:55 including a 5 s end card. Deliver briskly. Batches, the two plain bugs (page number, dropped filter), the last-second swap and "paid isn't final" are **not spoken**: they appear on screen only (see FOOTAGE_V10). If the first edit still runs over 5:00, cut in this order:
1. The webhook line in §6.
2. "I edited the ledger two hundred times…" in §7.
3. The Northwind conversion clause in §4.
4. "Then I attacked Ringfence myself" through "by Airwallex's own count" shortened to the 36-documents line only.

Never cut: §2's "break theirs first" line, the label line in §3, the "Then the week changes" beat in §4, or the close.

## Why there's no Metal
The judging criteria are finance value, Airwallex relevance, agentic behaviour and controls, and technical execution, and the demo rubric is goal → plan → new information → revised decision → result. Metal fits none of these and splits the story across two platforms. Its 25 seconds now go to the "week changes" beat (the agent revising its plan and the final balances), which is what C3 and C4 score. The Metal cards stay in the live app for anyone who looks.
