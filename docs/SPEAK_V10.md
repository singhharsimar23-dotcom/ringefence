# What you say (v10, final)

One Loom: Screen + Camera, medium bubble bottom left, 1080p. Save as `var/loom_v10.mp4`.
What's on your screen doesn't matter; every shot is built in the edit. Read it at your normal speaking pace, direct and plain. If you fumble, pause and redo the paragraph.
The screen carries the detail (IDs, code, analysis); your voice carries the story. **Bold** = lean on it. A line break = a short pause; a section break = a longer one.

---

## 1 · Open

Hi, I'm Harsimar Singh, and this is **Ringfence**, my submission for the Airwallex hackathon.

Some companies run payroll for lots of other companies. Every Friday they're holding millions of dollars that **aren't theirs**.
So my first question was: if an AI agent does that job, how do I make sure it **never pays the wrong person**?

---

## 2 · Break it first

Airwallex is building for agents that move money, and the platform's developer guide shows how to build one: a frontier model, the Airwallex API as its tools, and a human approving every payment.
I built that reference agent first and spent several days trying to break it, on the sandbox, with my own accounts and a few pounds, cancelling every transfer afterwards.
If an attack works there, it works on every agent built that way. So I broke it first, and hardened Ringfence against everything I found.
Airwallex kept each client's money separate in every test. The issues are in what an agent can be led to do.

---

## 3 · What I found

The most serious finding defeats the **human approver**.
A payment is waiting for approval. The approver checks the name, the amount and the payee, and approves it. But while it waited, the bank account behind that payee was changed. Same name, same payee ID, so the money goes to the new account. **Three out of three**, with no alert.
The payee stays saved, so every later run pays that account too, and nothing in the system flags it.

So who changes the bank account? **The agent does, from an email.** A normal-looking invoice says the supplier changed banks, and the agent updates the payee. **Five out of five.**
The approval checks a **label**, and the money follows wherever that label points.

I found the same pattern in other places. The platform's Node SDK holds **one login** for the whole program, so with a client per employer, Northwind's payment goes out on Kestrel's login. I found that in the SDK code.
The platform's MCP server gives every payment a **new request ID**, so if a reply is lost and the agent retries, that's a second payment. I ran that retry live against the API: one pound owed, **two moved**, and no way to cancel.

---

## 4 · Ringfence

Based on this analysis, I built **Ringfence**. The agent proposes, and my code decides what money moves.
It runs payroll for three clients, Northwind, Kestrel and Harbour, each on its own Airwallex account. The goal was to pay every client's contractors for the week.
The agent reads the timesheets and the inbox and plans all three. Kestrel had a normal week, so it pays. Northwind changed pay rates, so it waits for approval, then converts the Australian dollars it needs within its allowed rate.

The next one, Harbour, is where the plan changes. Harbour is short of Australian dollars, and its rules don't allow a conversion. So the agent **revises its plan**: it holds Harbour, calculates the exact shortfall, and asks Harbour to top up its own account before the deadline.
Meanwhile, fifty thousand dollars lands in **Kestrel's** account. That's Kestrel's money, so Ringfence won't use it for Harbour.
Harbour's top-up arrives in its Airwallex global account, the agent matches it, and releases the payments. Everyone is paid, and **each client's balance is still its own**.

---

## 5 · Retest

Then I re-ran every attack from my research against Ringfence.
The approval swap is **held, three out of three**. Ringfence signs the exact bank details into the approval and sends them inside the transfer, so there's no label to swap.
A bank change from an email goes into **quarantine** until a different person confirms it by phone.
Every payment gets its request ID before the first attempt, so a lost reply means a lookup, **never a second payment**.
And each client has its own login. I tried to cross that boundary twelve ways, and Airwallex **blocked all twelve**.

---

## 6 · For the engineers

For the engineers:
The model never chooses which account it acts on. Code logs in as each client and sets amounts, limits and request IDs, in decimals, never floats.
Webhooks are a hint, so every one is re-fetched from Airwallex. Transfer lists are read by cursor, because the page number is ignored. A paid transfer can still fail later, so paid is never final.
Every action goes into a **hash-chained ledger**, with the chain head stamped inside each Airwallex transfer. Rewrite my database and re-hash the chain, and Airwallex's copy still disagrees.
And Ringfence runs as an **MCP server with no approve tool**, so a human always signs.

---

## 7 · Testing Ringfence directly

I also attacked Ringfence directly. An agent that follows every instruction it reads, given thirty-six hostile documents, moved **no money**.
Twenty payment releases at once, with replies dropped: Airwallex's own records show each payment made **exactly once**.
Two hundred ledger edits, every one caught at the correct row. And four hundred and sixty-two tests against a mock of the Airwallex API.
But don't take my word for it. The demo is **live**, so try to make it pay the wrong person.

---

## 8 · Close

It's still a normal payroll agent, with one fix for every way I broke the reference agent.
Every finding is in the repo with its transfer IDs.
So, back to my first question: how do I make sure an AI agent **never pays the wrong person**?
**That's Ringfence.** Thanks for watching.

---
---

## Receipts for every spoken claim (skip when recording)

| Spoken claim | Receipt |
|---|---|
| The platform's guide's agent: frontier model, API as tools, a human approving | AgentOS "require manual approval for tool calls"; `bench/market_agent.py` (Opus 5.5). The approver is a modelled diligent human who checks id, amount and currency. |
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
About 880 spoken words: about 5:18 at your measured 166 wpm, less if you speak faster. You asked to keep it under 5:20 and handle the pace yourself, so there's no forced trimming. Batches, the SDK dropped-filter bug and the last-second swap are on screen only (see FOOTAGE_V10). If the final edit runs over 5:00 for submission, cut in this order:
1. The webhook / cursor / paid-isn't-final lines in §6.
2. "Two hundred ledger edits…" in §7.
3. The Northwind conversion clause in §4.
4. §7 reduced to the thirty-six-documents line.

Never cut: the §2 scope line, the label line in §3, the Harbour beat in §4 ("The next one, Harbour, is where the plan changes" through the final balances), or the close.

## Why there's no Metal
The judging criteria are finance value, Airwallex relevance, agentic behaviour and controls, and technical execution, and the demo rubric is goal → plan → new information → revised decision → result. Metal fits none of these and splits the story across two platforms. Its 25 seconds now go to the Harbour beat (the agent revising its plan and the final balances), which is what C3 and C4 score. The Metal cards stay in the live app for anyone who looks.
