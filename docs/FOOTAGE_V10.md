# Footage (v10, final): what's on screen, shot by shot

Pairs with `docs/SPEAK_V10.md`. The voice is the Loom (`var/loom_v10.mp4`). Times are estimates at the user's measured pace (166 wpm); re-time to `words.json` after the take.

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

F5 to F7 are **not spoken**. They appear on screen during "I kept finding the same shape" (F5) and as a fast board during §3's end and §6 (F6, F7). The full board (F1 to F7) holds for 2 s at the end of §3, with the line "Isolation: held 12/12" in green under it.

## Shot list

| § | ~Time | Voice cue | On screen | Source | On-screen text |
|---|---|---|---|---|---|
| 1 | 0:00 | "Hi, I'm Harsimar" | Full face; landing hero behind. | camera | Ringfence |
| 1 | 0:08 | "millions… aren't theirs" | Three client tiles under one operator. | landing `#how` | Not their money |
| 2 | 0:20 | "their guide shows how you'd build one" | Diagram: model → Airwallex API tools → human approval step. | `bench/market_agent.py` | The reference agent |
| 2 | 0:32 | "built that one… break it" | Terminal of the reference agent running. | bench terminal | Target: the reference agent |
| 2 | 0:38 | "All on the sandbox, my own accounts…" | **Scope card**: `Sandbox only · own 4 accounts · ≤ GBP/EUR 5 · every transfer cancelled or reversed`. | edit | Scope |
| 2 | 0:50 | "Airwallex kept every client's money separate" | 12 green 401 cells. | `GAUNTLET.md` §4 | Isolation held |
| 3 | 0:59 | "beats the human… name, amount, payee" | The approval card, each field ticking. | BENCH approval | Looks correct |
| 3 | 1:08 | "bank account behind that payee got changed" | Split: approval card unchanged, beside `POST /beneficiaries/{id}/update` → ..9901. | `breakit.py approval` | Same ID. New account. |
| 3 | 1:15 | "three out of three, no alert" | Dashboard `22c0a5d8…` → ..9901 boxed in red; **F1 card**. | sandbox dashboard | F1 · High · 3/3 |
| 3 | 1:20 | "keeps paying that account, run after run" | Saved payee; next runs' arrows all land on ..9901; webhook list with no beneficiary event. | edit + `silent_divert.out.txt` | No alert fires |
| 3 | 1:27 | "The agent does. From an email." | Invoice text types on; the agent's update call; **F2 card**. | `agent_bec_repeat.out.txt` (9 Nov) | F2 · 5/5 |
| 3 | 1:40 | "The approval checks a label" | Full face, then a label with an arrow that swings to a new account. | camera + edit | It checks a label |
| 3 | 1:47 | "I kept finding the same shape" | **F5 card** flashes (batch preview with no bank column, 401). | BENCH batch | F5 · 4/4 |
| 3 | 1:52 | "one login for the whole program" | SDK source: the module singleton; A's call carrying B's token; **F3 card**. | `sdk_singleton_check.out.txt` | F3 · found in code |
| 3 | 2:00 | "a new ID… one pound owed, two moved" | `uuid.v4()` line; then two SETTLED transfers; **F4 card**. | MCP source + `charges-…-new-id.out.txt` | F4 · 1 owed · 2 moved |
| 3 | 2:07 | (end of §3) | **Full board F1 to F7** for 2 s; F6 and F7 enter here. | edit | 7 findings · isolation held |
| 4 | 2:09 | "here's what I built. Ringfence." | Live app, three clients, each with its own account id. | app | Agent suggests · code decides |
| 4 | 2:20 | "the goal… plans all three" | **Rubric strip** at the top of the frame, built step by step: `Goal → Plan → New info → Revised → Result`. Goal and Plan light up; the agent's plan rows appear. | app timeline | Goal · Plan |
| 4 | 2:30 | "Kestrel pays… Northwind waits… converts" | Kestrel SCHEDULED with transfer id; Northwind diff (rate change); FX_QUOTE → FX_CONVERTED with `conversion_id`. | app | Paid · Waiting · FX within band |
| 4 | 2:42 | "Then the week changes… Harbour short… no conversion" | Rubric "New info" lights. Harbour AUD balance short; rule `fx: never`; funding card with the exact shortfall and deadline. | app | New info |
| 4 | 2:52 | "revises the plan" | Rubric "Revised" lights. Harbour HELD, funding requested. | app | Revised decision |
| 4 | 2:58 | "fifty thousand… Kestrel's money" | `[SIMULATED]` 50k lands in Kestrel; Harbour stays held; Kestrel's balance boxed. | app card "Another employer's money arrives" | [SIMULATED] · not Harbour's |
| 4 | 3:05 | "top-up lands in its global account… pays" | `[SIMULATED]` deposit to Harbour's AUD global account; FUNDING_MATCHED; released. | app card "Harbour's own top-up" | Matched · paid |
| 4 | 3:10 | "Everyone's paid… its own" | Rubric "Result" lights. **Final-state table**: each employer's balance before → after, every line PAID/SCHEDULED, Kestrel's 50k still there. | app `/api/state` | Result |
| 5 | 3:10 | "every attack from the hunt, again, on Ringfence" | The F-board returns; each row flips to a green "retest" column as it's named. | edit | Retest |
| 5 | 3:16 | "approval swap… held" | Card "Swap the bank account after approval" → HELD. Then, unspoken, "Swap it at the last second" → transfer read back, CANCELLED. | app (fresh world) | F1 → HELD 3/3 · race → CANCELLED |
| 5 | 3:26 | "quarantine… by phone" | Card "Fake bank-change email" → quarantine pill → callback by a different person. | app | F2 → quarantined |
| 5 | 3:33 | "ID before the first try… never a second payment" | Card "Internet drops mid-payment": lost reply → lookup by request_id → one transfer. | app | F4 → 1 transfer |
| 5 | 3:40 | "own login… all twelve" | Card "Use another company's money" + the 12 × 401 grid. | app + `GAUNTLET.md` §4 | F3 → 12/12 blocked |
| 6 | 3:43 | "Quick one for the engineers" | Fast cuts of live cards, one per line. Unspoken on-screen captions: "Double-click pay" → 1 transfer; "Payment bounces back" → paid isn't final, reopened; Proof paging by cursor (F6, F7 → fixed). | app | For engineers |
| 6 | 3:47 | "Webhooks are a hint" | Webhook event, then the GET that re-fetches it. | app timeline | Hint → re-fetch |
| 6 | 3:52 | "hash-chained ledger… stamped inside each transfer… re-hash… disagrees" | Transfer metadata `rf_seq`/`rf_hash`; card "Change a record and re-hash the chain" → self-check passes but the Airwallex stamp row turns red. | app Proof | Re-hashed → still caught |
| 6 | 4:00 | "MCP server with no approve tool" | MCP tool list; no approve. | `mcp_server.py` | A human signs |
| 7 | 4:04 | "agent that obeys every attack… thirty-six" | Gauntlet board: obedient agent 28 obeyed / 28 denied / 0 moved (8 no tool); Claude 0 obeyed. | landing Gauntlet + `GAUNTLET.md` §1 | 36 docs · 0 moved |
| 7 | 4:12 | "Twenty payments at once… Airwallex's own count" | Live `/transfers` count by request_id: [1, 1, 1]. | `GAUNTLET.md` §2 | 20 releases · 1 each |
| 7 | 4:18 | "edited the ledger two hundred times" | 200/200 caught at the right row. | `GAUNTLET.md` §5 | 200/200 |
| 7 | 4:22 | "four hundred and sixty-two tests" | `pytest -q` final line. | terminal | the day's number |
| 7 | 4:27 | "don't take my word… live" | Live URL; Try it composer. | app Try it | Try it |
| 8 | 4:33 | "normal payroll agent… one fix for every way" | The F-board, every row green. | edit | Same agent. Hardened. |
| 8 | 4:40 | "back to my first question… That's Ringfence" | Full face, hold. | camera | Ringfence |
| 8 | 4:52 | (end) | Black end card: repo + live URL. Music only here. | edit | — |

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
