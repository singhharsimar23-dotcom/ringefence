# Footage (v10, final): what's on screen, shot by shot

Pairs with `docs/SPEAK_V10.md`. The voice is the Loom (`var/loom_v10.mp4`). Times are estimates at the user's measured 166 wpm (~789 words); re-time to `words.json` after the take.

**Style.** x.ai monochrome, no gradients. Face bubble bottom left throughout. Chapter label and timecode in a corner. One plain line of on-screen text per beat. Subtitles throughout. Red only for their failure, green only for Ringfence's fix. Music only under the end card.

**Rules.**
- Every ID on screen is real. Sandbox simulations carry `[SIMULATED]`. A recorded `*.out.txt` gets its date stamped in the corner.
- Each attack link is verified on its own. Never cut them together to look like one unbroken run.
- The voice stays simple, and the screen carries the analysis. Every finding gets a **finding card** (below), and every number on screen has a source.

## The finding card (CTF / pentest style, one per finding)
A black panel with a 1px line border and mono text. Severity is a word, not a colour.

```
F1  Approval swap                       SEVERITY  High
    Approver sees: name · amount · payee id     (all unchanged)
    Money went to: ..9901                         LIVE  3/3
    22c0a5d8…  49a84d09…  0d0b978b…
    FIX  bank details signed into the approval, sent inline   →  HELD 3/3
```

| Card | Finding | Severity | Evidence | IDs | Fix |
|---|---|---|---|---|---|
| F1 | Approval swap | High | LIVE 3/3 | `22c0a5d8…` `49a84d09…` `0d0b978b…` | inline signed bank details → HELD 3/3 |
| F2 | Bank change from an email | High (supplies F1) | LIVE 5/5 | `45528e1d…` `749ebed0…` `3dd76387…` `70b841be…` `958cc5cd…` | quarantine + phone callback |
| F3 | SDK: one login per program | High | CODE, checked offline | `apiClient.initialize(this)`; A's call carries B's token | own login per client, chosen by code → 12/12 401 |
| F4 | MCP: new ID per payment → retry pays twice | Medium | CODE (MCP) + LIVE retry | `uuid.v4()`; `tr_EVfI4fFU…` + `tr_i7K2mR5G…`, 1 owed / 2 moved | ID fixed before the first try; look it up |
| F5 | Batches: no bank account at review, key can't cancel | Medium | LIVE 4/4 | `f5bd21a8…` `f1cd2e93…` `66404ad8…` `f72b2134…`; 401 "Admin permissions required" | one transfer per line, details inline |
| F6 | Transfer list ignores the page number | Low | LIVE, read-only | 100 of 215 seen | cursor paging; fail if the cursor stalls |
| F7 | SDK retry drops its filter | Low | CODE + LIVE result | `apiClient.js:157`; filter 0 vs 215 | match request_id on every item |

All seven are named in §3 in plain words (F1, F2 told in full; F5, F3, F4, F6, F7 one line each). The screen carries the detail: each line gets its finding card with severity and IDs. The full board (F1 to F7) holds for 2 s at the end of §3, with "Isolation: held 12/12" in green under it.

## Shot list

| § | ~Time | Voice cue | On screen | Source | On-screen text |
|---|---|---|---|---|---|
| 1 | 0:00 | "Hi, I'm Harsimar" | Full face; landing hero behind. | camera | Ringfence |
| 1 | 0:05 | "millions… aren't theirs" | Three client tiles under one operator. | landing `#how` | Not their money |
| 2 | 0:20 | "payroll provider on the sandbox… three client companies" | **Setup card**: operator (platform account) above three client accounts, Northwind · Kestrel · Harbour, each with its real `acct_…` id. Tag: `Airwallex sandbox · [SIMULATED] money in`. The tag stays in a corner for the rest of the film. | edit + `demo/employers.json` | Sandbox · 3 simulated clients |
| 2 | 0:27 | "The platform's guide shows how to build a payment agent" | Diagram: model → Airwallex API tools → human approval step. | `bench/market_agent.py` | The reference agent |
| 2 | 0:36 | "I built that agent first… break it" | Reference agent terminal, then the **scope card**: `Sandbox only · own 4 accounts · ≤ GBP/EUR 5 · every transfer cancelled or reversed`. | bench terminal + edit | Scope |
| 3 | 0:44 | "Here's what I found" | **Path map**, three columns: *Who it's paid to* (F1, F2) · *How it's sent* (F5, F3, F4) · *How the agent checks* (F6, F7). It shrinks to a header strip for all of §3, with the active column lit. | edit | Who · How · Check |
| 3 | 0:46 | "The worst one beats the human… name, amount, payee" | Strip: *Who* lit. The approval card, each field ticking. | BENCH approval | Looks correct |
| 3 | 0:53 | "the bank account behind that payee was swapped" | Split: approval card unchanged, beside `POST /beneficiaries/{id}/update` → ..9901. | `breakit.py approval` | Same ID. New account. |
| 3 | 1:00 | "three out of three, with no alert" | Dashboard `22c0a5d8…` → ..9901 boxed in red; **F1 card**. | sandbox dashboard | F1 · High · 3/3 |
| 3 | 1:03 | "every payroll run after that pays the same account" | Saved payee; the next runs' arrows all land on ..9901; webhook list with no beneficiary event. | edit + `silent_divert.out.txt` | No alert fires |
| 3 | 1:09 | "And who swapped it? The agent… fake invoice email" | Invoice text types on; the agent's update call; **F2 card**. | `agent_bec_repeat.out.txt` (9 Nov) | F2 · High · 5/5 |
| 3 | 1:15 | "The approval checks a label" | Full face, then a label with an arrow that swings to a new account. | camera + edit | It checks a label |
| 3 | 1:22 | "Payroll batches pay the swapped account too… can't be cancelled" | Strip: *How* lit. Batch item preview with no bank column; edited payee → booked to ..9901; cancel → 401 "Admin permissions required"; **F5 card**. | BENCH batch + dashboard batch IDs | F5 · Medium · 4/4 |
| 3 | 1:30 | "In the SDK code… another client's login" | SDK source: the module singleton; Northwind's call carrying Kestrel's token; **F3 card**. | `sdk_singleton_check.out.txt` | F3 · High · found in code |
| 3 | 1:35 | "A retry can pay twice… one pound owed, two moved" | `uuid.v4()` line; then two SETTLED transfers; **F4 card**. | MCP source + `charges-…-new-id.out.txt` | F4 · Medium · 1 owed · 2 moved |
| 3 | 1:46 | "the payment list can be wrong in both directions… paid show as unpaid" | Strip: *Check* lit. `page_num` 0, 1, 2 → the same 100 ids (same hash); the rest shown greyed as "unpaid"; **F6 card**. | `breakit.py pages` + `transfers-pagination-page-num-ignored.out.txt` | F6 · Low · 100 of 215 |
| 3 | 1:53 | "Unpaid people show as paid" | `apiClient.js:157` argument order; filtered GET 0 items → the retry, unfiltered, 215; a never-paid line ticks "paid"; **F7 card**. | `breakit.py sdk` + `node-sdk-retry-reconcile.out.txt` | F7 · Low · 0 → 215 |
| 3 | 1:56 | "Airwallex itself kept every client's money separate" | 12 green 401 cells. | `GAUNTLET.md` §4 | Isolation held |
| 3 | 2:02 | (end of §3, just before) | **Full board F1 to F7** for 2 s, "Isolation: held 12/12" in green under it. | edit | 7 findings · isolation held |
| 4 | 2:03 | "So I built Ringfence from these findings… every bug became a rule" | Live app, three clients, each with its own account id; `Airwallex sandbox` tag. | app | Agent proposes · code decides |
| 4 | 2:13 | "Here's a payroll week… plans all three clients" | **Rubric strip** at the top, built step by step: `Goal → Plan → New info → Revised → Result`. Goal and Plan light up; the plan rows appear. | app timeline | Goal · Plan |
| 4 | 2:22 | "Kestrel pays… Northwind waits… converts" | Kestrel SCHEDULED with transfer id; Northwind diff (rate change); FX_QUOTE → FX_CONVERTED with `conversion_id`. | app | Paid · Waiting · FX within band |
| 4 | 2:30 | "Harbour is where the plan changes… short… isn't allowed to convert" | "New info" lights. Harbour AUD balance short; rule `fx: never`. | app | New info |
| 4 | 2:36 | "revises the plan" | "Revised" lights. Harbour HELD; funding card with the exact shortfall and deadline. | app | Revised decision |
| 4 | 2:44 | "fifty thousand… Kestrel's account… a naive agent would spend it" | `[SIMULATED]` 50k lands in Kestrel; the crossed-out "naive total" strip shows what a careless agent would spend; Harbour stays held; Kestrel's balance boxed. | app card "Another employer's money arrives" | [SIMULATED] · not Harbour's |
| 4 | 2:50 | "Harbour's top-up lands in its global account" | `[SIMULATED]` deposit to Harbour's AUD global account; FUNDING_MATCHED; released. | app card "Harbour's own top-up" | [SIMULATED] · matched · paid |
| 4 | 2:55 | "Everyone's paid… its own" | "Result" lights. **Final-state table**: each client's balance before → after, every line PAID/SCHEDULED, Kestrel's 50k still there. | app `/api/state` | Result |
| 5 | 2:59 | "Then I ran every attack again, on Ringfence" | The F-board returns; a green "retest" column fills row by row as each is named. | edit | Retest |
| 5 | 3:02 | "The bank swap is held… no label left to swap" | Card "Swap the bank account after approval" → HELD. Unspoken: "Swap it at the last second" → read back, CANCELLED. F5 row: "no batches, details inline". | app (fresh world) | F1 → HELD 3/3 · F5 → not used |
| 5 | 3:12 | "The fake email is quarantined… by phone" | Card "Fake bank-change email" → quarantine pill → callback by a different person. | app | F2 → quarantined |
| 5 | 3:17 | "The retry pays once… ID fixed before the first try" | Card "Internet drops mid-payment": lost reply → lookup by request_id → one transfer. Then Proof paging by cursor, request_id matched per item. | app + Proof | F4 → 1 transfer · F6, F7 → fixed |
| 5 | 3:22 | "own login… all twelve" | Card "Use another company's money" + the 12 × 401 grid. | app + `GAUNTLET.md` §4 | F3 → 12/12 blocked |
| 6 | 3:29 | "Here's a quick one for the engineers… never chooses which account" | The `x-login-as` login chosen by code, not the model; `Decimal` amounts. Unspoken caption: "Double-click pay" → 1 transfer. | app + code | Code binds the account |
| 6 | 3:41 | "Webhooks are a hint… cursor… paid is never final" | Webhook event, then the GET that re-fetches it; card "Payment bounces back" → PAID then FAILED, reopened. | app timeline | Hint → re-fetch · paid isn't final |
| 6 | 3:54 | "hash-chained ledger… stamped inside each transfer… re-hash… disagrees" | Transfer metadata `rf_seq`/`rf_hash`; card "Change a record and re-hash the chain" → self-check passes but the Airwallex stamp row turns red. | app Proof | Re-hashed → still caught |
| 6 | 4:04 | "MCP server with no approve tool" | MCP tool list; no approve. | `mcp_server.py` | A human signs |
| 7 | 4:10 | "Thirty-six hostile documents: no money moved" | Gauntlet board: obedient agent 28 obeyed / 28 denied / 0 moved (8 no tool). | landing Gauntlet + `GAUNTLET.md` §1 | 36 docs · 0 moved |
| 7 | 4:14 | "Twenty payments at once… each paid exactly once" | Live `/transfers` count by request_id: [1, 1, 1]. | `GAUNTLET.md` §2 | 20 releases · 1 each |
| 7 | 4:18 | "Two hundred ledger edits" | 200/200 caught at the right row. | `GAUNTLET.md` §5 | 200/200 |
| 7 | 4:20 | "four hundred and sixty-two tests" | `pytest -q` final line. | terminal | the day's number |
| 7 | 4:22 | "don't take my word… live" | Live URL; Try it composer. | app Try it | Try it |
| 8 | 4:29 | "a normal payroll agent, hardened against everything I found" | The F-board, every row green. | edit | Same agent. Hardened. |
| 8 | 4:37 | "back to my first question… That's Ringfence" | Full face, hold. | camera | Ringfence |
| 8 | 4:48 | (end) | Black end card: repo + live URL. Music only here. | edit | — |

## Capture checklist (shoot day, in order)
1. `uv run pytest -q`: grab the final line.
2. Live app: press **Start over** first. Run `uv run python scripts/preflight.py --url <live url>`; it must say GO.
3. One continuous run, captured full-screen, in this order:
   1. Run.
   2. Kestrel SCHEDULED; Northwind diff.
   3. Northwind approve → FX_QUOTE / FX_CONVERTED. **If no FX row appears, cut the conversion clause from the voice.**
   4. Harbour short → funding card.
   5. "Another employer's money arrives".
   6. "Harbour's own top-up".
   7. Final balances.
4. The cards, each on a fresh world where the card needs one:
   1. "Swap the bank account after approval" (HELD).
   2. "Swap it at the last second" (CANCELLED, needs a fresh world).
   3. "Fake bank-change email".
   4. "Internet drops mid-payment".
   5. "Use another company's money".
   6. "Double-click pay".
   7. "Payment bounces back".
   8. "Change a record and re-hash the chain".
5. Sandbox dashboard: open and box `22c0a5d8…`, the batch IDs and the two `tr_…` IDs.
6. Terminals: `scripts/breakit.py approval batch` and `scripts/breakit.py pages sdk` (read-only), plus `agent_bec_repeat.out.txt` shown with its date.
7. Landing `/#found` and the Gauntlet section, scrolled slowly.

**If a step fails on the day:** use the recorded output with its date stamped, and say nothing new about it.

Metal is not in the film. Its cards stay in the live app.
