# Footage script (v8): what's on screen, shot by shot

Pairs with `docs/SPEAK_V8.md`. The voice is the Loom (`var/loom_v8.mp4`). Every visual is a real capture with motion graphics over it.

**Style.** x.ai monochrome, no gradients. Face bubble bottom left throughout. Chapter + timecode in the corner. One plain line of text per beat; subtitles throughout. Red = their failure, green = Ringfence's fix; no other colour. Music only into the end card.

**Rule.** Every ID on screen is real and was live on the sandbox. Sandbox simulations carry `[SIMULATED]`. If a capture can't be re-shot on the day, use the recorded `*.out.txt` with its date in the corner. Each attack link is verified on its own — never cut them to look like one unbroken run.

## Shot list

| § | ~Time | Voice cue | On screen | Source | On-screen text |
|---|---|---|---|---|---|
| 1 | 0:00 | "Hi, I'm Harsimar" | Full face. Landing hero fades in behind. | camera | Ringfence |
| 1 | 0:12 | "millions… aren't theirs" | Three client tiles (Northwind, Kestrel, Harbour) under one operator. | landing `#how` | Not their money |
| 2 | 0:25 | "the way Airwallex's own guide shows… a human approving" | The setup: model + Airwallex tools + an approval step highlighted. | `bench/market_agent.py`, terminal | Set up like a careful company |
| 2 | 0:38 | "Put a human in the loop" | The approval step glows. A little "human ✓" stamp. | edit | The control everyone trusts |
| 3 | 0:48 | "A payment waits… name, amount, currency, payee" | The approval card, each field ticking green. | app / BENCH approval | Looks correct |
| 3 | 1:00 | "I change the bank account behind that payee" | Split: the card's fields unchanged, beside the API call changing the account. | `breakit.py approval` terminal | Same ID. New account. |
| 3 | 1:12 | "says yes… three out of three… here's the transfer ID" | Approver clicks yes; dashboard `22c0a5d8…` → ..9901 in red; the 3 IDs stack. | sandbox dashboard + BENCH row | 3 / 3 · no alert |
| 3 | 1:20 | "it doesn't stop… a whole payday… until the real person says I wasn't paid" | The saved payee card stays; a little calendar ticks future runs, each arrow landing on the red account; then one "unpaid" flag from the contractor. | edit over app payee view | Pays every run · no system flag |
| 3 | 1:26 | "The agent itself. From an email." | The invoice text types on; agent moves the payee. | `agent_bec_repeat.out.txt` DOC | Just an email |
| 3 | 1:34 | "five times out of five" | Five lines tick: `PAID THE MULE … ..9901`. | `agent_bec_repeat.out.txt` | 5 / 5 |
| 3 | 1:44 | "the approval checks a label" | Full face. Motion graphic: a label with an arrow; the arrow swings to a new account. | camera + edit | It checks a label |
| 4 | 1:56 | "Batches… four out of four… can't cancel" | Batch preview, no bank column; 4 IDs; `401 Admin permissions required`. | BENCH batch section | 4 / 4 · can't cancel |
| 4 | 2:08 | "their SDK keeps one connection… found it in their code" | SDK source: one module singleton; A's call carries B's token. | `sdk_singleton_check.out.txt` + `dist/client/apiClient.js` | Wrong client's login |
| 5 | 2:20 | "Ringfence. The agent suggests, my code decides" | Live app, the three clients; hit run. | app | Agent suggests · code decides |
| 5 | 2:30 | "Kestrel pays… Northwind waits" | Kestrel SCHEDULED; Northwind diff view. | app | Paid / Waiting |
| 5 | 2:42 | "approval signs the exact bank details… held, three out of three" | The same swap on Ringfence goes HELD; race variant CANCELLED. | app approval-swap card | Held 3 / 3 |
| 5 | 2:52 | "quarantine… confirmed by phone" | Bank-change email → quarantine pill → callback. | app | Quarantined |
| 5 | 3:00 | "own login… blocked all twelve" | 12 × 401 `credentials_invalid` grid. | `GAUNTLET.md` §4 | 12 / 12 blocked |
| 5 | 3:08 | "fifty thousand… won't touch it… everyone gets paid" | `[SIMULATED]` 50k lands in Kestrel; Harbour stays held; then all paid. | app | [SIMULATED] · not Harbour's |
| 6 | 3:20 | "the same shape… the money followed" | Full face. The findings collapse into one line: label → money. | camera + `#found` punch | It trusts a label |
| 6 | 3:32 | "code decides… never pay twice" | Pillars, one line each: no money tool · pinned details · fixed ID · own login · ledger. | landing `#how` | Code decides |
| 6 | 3:42 | "it turns red" | A transfer's metadata shows `rf_seq`/`rf_hash`; tamper → Proof row red. | app Proof tab | Rewritten → red |
| 6 | 3:50 | "MCP server, no approve tool" | MCP tool list, no approve. | `mcp_server.py` / UI line | A human signs |
| 7 | 3:56 | "thirty-six hostile documents" | Gauntlet grid: obedient 28/28 obeyed, 0 moved. | landing Gauntlet | 36 · 0 moved |
| 7 | 4:06 | "Twelve… Twenty… Two hundred" | Quick cuts: isolation 12, storm 20→20, ledger 200/200. | `GAUNTLET.md` | — |
| 7 | 4:14 | "Four hundred and fifty tests" | `pytest -q` final line. | terminal | the day's number |
| 8 | 4:20 | "Metal mandate… second pull refused… wrong address refused" | Mandate card; refusal tx with decoded caption. | Metal CLI, VM device mode | Refused on chain |
| 9 | 4:32 | "sandbox, not production" | Full face. | camera | — |
| 9 | 4:40 | "Try to make it pay the wrong person" | Playground: paste / Attack-itself buttons. | app Try-it | Try it |
| 9 | 4:48 | "That's Ringfence" | Full face, hold. Then black: Thank you · Adiós · नमस्ते. End card: repo + live URL. | edit | Ringfence |

## Capture checklist (shoot day, in order)
1. `uv run pytest -q`: grab the final line.
2. App, fresh world, full-screen:
   - the Northwind / Kestrel / Harbour run;
   - the approval-swap card (HELD) and its race variant (CANCELLED);
   - the bank-change quarantine;
   - the tamper card turning the Proof stamp row red.
3. Sandbox dashboard: open and box each ID: `22c0a5d8…`, `45528e1d…`, the batch IDs.
4. Terminal runs (credit note: Opus only where needed):
   - `RF_N=5 uv run python bench/probes/agent_bec_repeat.py` (Sonnet, cheap);
   - `scripts/breakit.py approval batch` for the their-side cards;
   - the live SDK read-only run if it exists.
5. Metal on the VM: bind → pull → second pull refused → poison refused. Write the tx set into `facts.json`.
6. Landing `/#found`, scrolled slowly, top to bottom.

**If a step fails on the day:** use the recorded output, stamp its date, say nothing new about it.
