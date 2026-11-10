# What you say (v10, final)

One Loom: Screen + Camera, medium bubble bottom left, 1080p. Save as `var/loom_v10.mp4`.
What's on your screen doesn't matter; every shot is built in the edit. Direct and professional, in your normal voice. If you fumble, pause and redo the paragraph.
The screen carries the detail (IDs, code, analysis); your voice carries the story. Everything is a sandbox simulation, and the script says so up front and keeps saying it.

| Mark | What you do |
|---|---|
| **bold** | Lean on that word. |
| `/` | A tiny beat. |
| `//` | A real pause. Let it land. |

---

## 1 · Open

Hi, I'm Harsimar Singh, / and this is **Ringfence**, / my submission for the Airwallex hackathon. //

Some companies run payroll for lots of other companies. / Every Friday they hold millions of dollars / that **aren't theirs**. //
So my question was: / if an AI agent does that job, / how do I make sure it **never pays the wrong person**? //

---

## 2 · The setup

I set up a payroll provider on the Airwallex **sandbox**, / with three **simulated** client companies, / each on its **own** account. //
The platform's guide shows how to build a payment agent, / with a **human** approving every payment. /
I built that agent first, / and spent days trying to **break** it, / with small amounts, / cancelled after. /
If it breaks there, / it breaks in **every** agent built that way. //

---

## 3 · What I found

Here's what I found. //
The worst one beats the **human**. / The approver checks the name, / the amount / and the payee, / and says yes. / But while the payment waited, / the **bank account** behind that payee was swapped. / The money went to the **new** account, / three out of three, / with no alert. /
The payee stays saved, / so every run after that pays it too, / and nothing flags it. //
And who swapped it? / **The agent**, / after reading a fake invoice email. / Five out of five. //
The approval checks a **label**. / The money follows wherever the label **points**. //

I found the same weakness in other places. /
Payroll batches pay the swapped account too, / and an agent can't cancel them. /
In the SDK code, / one client's payment can go out on **another** client's login. /
A retry can pay **twice**. / I ran it: / one pound owed, / **two** moved. /
And the payment list can show paid people as **unpaid**, / and unpaid people as **paid**. //
Airwallex kept every client's money **separate**. / The problem is what an **agent** can be led to do. //

---

## 4 · Ringfence

So I built **Ringfence**, / on the same simulated setup. / The agent **proposes**, / and my code **decides** what money moves. //
The goal is to pay every client's contractors this week. / The agent reads the timesheets and the inbox, / and plans all three. /
Kestrel had a normal week, / so it **pays**. / Northwind changed pay rates, / so it **waits** for approval, / then converts the currency it needs. //
Harbour is where the plan **changes**. / It's short of Australian dollars, / and isn't allowed to convert. / So the agent **revises the plan**: / it holds Harbour, / works out the exact shortfall, / and asks for a top-up before the deadline. //
Meanwhile, / a simulated fifty thousand lands in **Kestrel's** account. / Ringfence won't touch it. / It's not Harbour's money. //
Harbour's simulated top-up lands in its Airwallex global account, / the agent matches it, / and pays. / Everyone's paid, / and **every client's balance is still its own**. //

---

## 5 · Retest

Then I ran every attack again, / on Ringfence. //
The bank swap is **held**, / because Ringfence locks the exact bank details into the approval. /
The fake email is **quarantined**, / until a different person confirms by phone. /
The retry pays **once**, / because every payment's ID is fixed before the first try. /
And each client has its **own** login. / I tried crossing that line twelve ways, / and Airwallex **blocked all twelve**. //

---

## 6 · For the engineers

For the engineers: //
The model never chooses which account it acts on. / Code logs in as each client / and sets amounts, limits and request IDs, / in decimals, never floats. //
Webhooks are a **hint**, / so every one is re-fetched from Airwallex. / Lookups follow the cursor / and check the request ID on every result. / And a paid transfer can still fail later, / so paid is never final. //
Every action goes into a **hash-chained ledger**, / with the chain head stamped inside each Airwallex transfer. / Rewrite my database and re-hash the chain, / and Airwallex's copy **still disagrees**. //
And Ringfence runs as an **MCP server** / with **no approve tool**, / so a human always signs. //

---

## 7 · Testing Ringfence

I also attacked Ringfence directly. / Thirty-six hostile documents: / **no money** moved. / Twenty payments at once, / with replies dropped: / each paid **exactly once**. / Two hundred ledger edits: / every one **caught**. / And four hundred and sixty-two tests. //
But don't take my word for it. / The demo is **live**. / Try to make it pay the wrong person. //

---

## 8 · Close

Ringfence is a normal payroll agent, / **hardened** against everything I found. //
All the findings and proof are in the repo. //
So, / back to my first question: / how do I make sure an AI agent / **never pays the wrong person**? //
**That's Ringfence.** // Thanks for watching.

---
---

## Receipts for every spoken claim (skip when recording)

| Spoken claim | Receipt |
|---|---|
| Payroll provider on the sandbox; three simulated client companies, each on its own account | `demo/employers.json`; 4 sandbox accounts (platform + Northwind, Kestrel, Harbour), one `x-login-as` login each |
| Reference agent built on the same accounts | `bench/market_agent.py`; its writes went to Northwind and Kestrel only (`AIRWALLEX_GAPS.md` "Safety") |
| Whole path: who it's paid to, how it's sent, how the agent checks | The seven findings group this way: F1, F2 / F5, F3, F4 / F6, F7 |
| Page number ignored → only the first hundred come back, rest look unpaid, a re-pay job pays them again | `AIRWALLEX_GAPS.md` §4: `page_num` 0, 1, 2 return the same 100 ids; a guide-style reconcile on Northwind reported 99 of 199 unpaid, 66 of them live debits a re-pay would pay twice; live re-check `breakit.py pages`: 100 of 215 |
| SDK retry drops the question → never-paid looks paid | `AIRWALLEX_GAPS.md` §5: `apiClient.js:157`; filtered GET 0 items, the retry without the filter 201 items |
| The platform's guide's agent: frontier model, API as tools, a human approving | AgentOS "require manual approval for tool calls"; `bench/market_agent.py` (Opus 5.5). The approver is a modelled diligent human who checks id, amount and currency. |
| Sandbox, own accounts, a few pounds, cancelled after | `AIRWALLEX_GAPS.md` "Safety": writes only to Northwind and Kestrel, GBP/EUR ≤ 5, every transfer cancelled where the API allows, the CA double payment reversed by hand, throwaway payees deleted |
| Isolation held every time | `docs/GAUNTLET.md` §4, 12/12 401 `credentials_invalid` live; no cross-tenant 2xx ever |
| Approval swap, 3/3, no alert | `22c0a5d8…`, `49a84d09…`, `0d0b978b…` to ..9901; no beneficiary-changed webhook (`silent_divert.out.txt`) |
| Keeps paying run after run; nothing in the system would know | The payee stays saved, there's no beneficiary-changed event, and the payee has no `updated_at` or version. Honest bound: nothing *alerts*; a reconciler that diffs `/transfers` bank snapshots could spot it, and the contractor notices on payday. Never say "undetectable", "for weeks" or "for months". |
| Agent changes it from an email, 5/5 | `agent_bec_repeat.out.txt`, 9 Nov: `45528e1d…`, `749ebed0…`, `3dd76387…`, `70b841be…`, `958cc5cd…`. Overt "SYSTEM" injections were refused. Each link was verified on its own, not as one run. |
| Batches: no bank account at review; whole run; key can't cancel | `f5bd21a8…`, `f1cd2e93…`, `66404ad8…`, `f72b2134…` (4/4); 401 "Admin permissions required" |
| SDK keeps one login; found in code | `bench/probes/sdk_singleton_check.out.txt`, offline: A's call attached B's token. We checked the token, not a completed payment. |
| MCP: a new ID per payment; a retry is a second payment | `@airwallex/developer-mcp@0.3.0-beta.13` `createTransfer.js`: `request_id: uuid.v4()` per call (code) |
| Retry live: one pound owed, two moved ("A retry can pay twice. I ran it") | `charges-request-id-duplicate-new-id.out.txt`: `tr_EVfI4fFUMiKaByQv2_pW4w` + `tr_i7K2mR5GNpqv0iirL3-rGg`, both SETTLED, connected-account transfer with no cancel endpoint. It was a REST retry, not one through the MCP: never say "the MCP paid twice", and never cite the docs row. |
| Page number ignored; retry drops filter | `scripts/breakit.py pages sdk`, live, 9 Nov: 100 of 215 seen, so 115 look unpaid; request_id filter returns 0, unfiltered 215, so a never-paid line looks paid; `apiClient.js:157` |
| Each client on its own account; goal; agent plans all three; code (not the model) logs in per client; decimals | 4 accounts, `x-login-as` per employer chosen by the harness; amounts in `Decimal`; RUN_CREATED and PLAN rows in the live timeline |
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
About 713 spoken words: about 4:18 at your measured 166 wpm, plus a 5 s end card, so under 5:00 with room for pauses. The bug section is told in plain words; the screen carries the technical detail (finding cards F1 to F7 with IDs). If the edit still runs over, cut in this order:
1. "Webhooks are a hint… paid is never final" in §6.
2. "Two hundred ledger edits…" in §7.
3. "then converts the currency it needs" in §4.

Never cut: the §2 setup line (simulated clients on the sandbox), the label line in §3, the Harbour beat in §4, or the close.

## Why there's no Metal
The judging criteria are finance value, Airwallex relevance, agentic behaviour and controls, and technical execution, and the demo rubric is goal → plan → new information → revised decision → result. Metal fits none of these and splits the story across two platforms. Its 25 seconds now go to the Harbour beat (the agent revising its plan and the final balances), which is what C3 and C4 score. The Metal cards stay in the live app for anyone who looks.
