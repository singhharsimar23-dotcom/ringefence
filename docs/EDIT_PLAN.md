# Edit plan: "Glass Box"

Source: `var/loom.mp4` (5:13, Harsimar's voice). Output: 1920x1080, 30 fps, about 4:53.
Times below are times in the original recording; the edit shortens pauses longer than 0.4 s to 0.4 s (saves about 21 s) and drops the closing "Bye".

## The idea

Most demo videos show a UI and say "trust me". Ringfence is a glass box: every claim in the voice has a real artifact behind it (a transfer ID, an API response, an on-chain transaction, a hash, a test result). The film's job is to open the box on every sentence.

Four devices carry it, used the same way every time so the viewer learns the grammar fast:

1. **Camera on our own capture (Screen Studio grade).** We drive the browser, so we know the exact pixel box of every element at every moment. Zooms land on the exact element, not a guess: 1.6-1.8x, spring easing (response 0.55 s), camera still for at least 1.2 s on the target, motion blur only while travelling, a drawn 1.6x cursor with a click ripple. At most 3 zooms a minute in the demo. Waits never play in real time: speed-ramped up to 8x with a motion streak, or skipped.
2. **X-ray.** On the key moments the UI slides left and the real wire traffic underneath it slides in on the right: the HTTP request, the response, the ledger entry. All real, captured from the run. This is where the engineers see depth.
3. **Receipts.** A small stamp in the bottom-right corner each time something real happens: `LIVE · AIRWALLEX · 1796e54e…`, `ON CHAIN · METAL · 0x814f…`, `[SIMULATED]`. Mono, accent dot, 1.5 s.
4. **Decision type.** When the voice states a decision, it lands as premium type: Inter 800, 96-140 px, tracking -0.03em, white on black, mask-up reveal 0.45 s, words staggered 40 ms, landing 1-2 frames before the word is said. 1-6 words, never a sentence.

Palette: black, white, grey, one accent (the site's blue, oklch 76% .13 258). Red only for refusals. No gradients, no glow, no bounce.

Subtitles: the whole way, bottom centre, Inter 500 38 px white at 85%, soft shadow, no box, at most 42 characters per line and one line, 5-7 words per chunk, broken at pauses, shown 0.15 s early. Hidden while decision type shows the same words. ASR errors fixed (court -> code, air wallets -> Airwallex), wording kept as spoken.

Face: your original footage, untouched, only where a person matters (about 22 s in total). Everything else is the demo.

## Tempo

| Act | Original time | Shot length | Music |
|---|---|---|---|
| 1 Problem | 0:00-0:42 | 3-4 s | low pulse |
| 2 Demo | 0:42-1:33 | 2.5-3 s | pulse under voice |
| 3 Metal | 1:33-2:53 | 2-3 s, one slow hero moment | builds |
| 4 Proof + engineers | 2:54-4:21 | 2 s, X-ray holds 3-4 s | full |
| 5 Break it | 4:21-4:53 | 1-1.5 s, cut on every number | fastest |
| 6 Close | 4:54-5:10 | face, then hard cut to black | music holds, end card |

## Shot list

| Time | Voice | Picture |
|---|---|---|
| 0:01.8 | "Hi, I am Harsimar and I build Ringfence." | **Face** (original, full camera). Lower third: `Harsimar · Ringfence` in mono. |
| 0:05.6 | "Some companies run a lot of payrolls…" | Black. Three account tiles assemble (Northwind, Kestrel, Harbour) with real `acct_` IDs, a bureau box above them. |
| 0:08.5 | "…holding millions of dollars that aren't theirs." | Balances count up in each tile (real sandbox balances); `NOT OURS` stamps across the bureau box. |
| 0:13.8 | "it goes wrong in two ways" | Type: `Two ways it goes wrong.` |
| 0:16 | "client's money pays another client's staff" | An animated payment arrow leaves Kestrel's tile and lands on a Harbour employee. Red. |
| 0:19 | "hey, I changed the bank" | The real sample email (`demo/samples/email_bank_change.txt`) as a document; highlighter sweeps the bank line. Arrow to `SCAMMER`. |
| 0:25 | "give that job to an AI agent" | An `AGENT` node drops in above all three tiles, wired to everything. |
| 0:27 | "how do I make sure that it never pays the wrong person?" | **Face** (original, full camera). |
| 0:33 | "The agent suggests, my code decides…" | Decision type, three beats: `AGENT suggests.` / `CODE decides.` / `AIRWALLEX isolates.` Then the architecture builds: agent -> proposal -> gate -> one token per client -> Airwallex. |
| 0:42.7 | "Let me show you." | Hard cut into the app (live capture). |
| 0:43.9 | "three clients" | Three lanes, a push-in sweep across them as each name is said. |
| 0:48 | "I hit run…reads all their timesheets" | Cursor clicks Run (zoom 1.8x on the button), then a speed ramp; the agent's reads fly into each lane (the timeline entries). |
| 0:52.8 | "Kestrel had a normal week, so it just pays them" | Zoom on Kestrel lane going to PAID. Receipt `LIVE · AIRWALLEX` with the real transfer ID. |
| 0:55.9 | "Those are real Airwallex transfers" | **X-ray 1:** the real `POST /transfers/create` request (request_id highlighted) and its `201 SCHEDULED` response, then `PAID`. |
| 0:59 | "Northwind changed some pay rates…" | Zoom on Northwind's diff: old rate struck, new rate in amber, `Needs approval`. |
| 1:04 | "wait for the finance person" | Type: `A person signs.` |
| 1:07.5 | "Harbour, this is the interesting one" | Harbour lane, slow push. |
| 1:09.7 | "don't have enough Australian dollars" | `AUD 1,240.17 short` punches in at 1.15x. |
| 1:12 | "works out exactly what's missing…before the deadline" | The funding request card: amount, reference, act-by time, with a countdown ticking. |
| 1:20.5 | "a trap I set on purpose" | Type: `The trap.` |
| 1:23 | "$50,000 lands in Kestrel account" | The scenario fires; Kestrel balance counts +50,000 (`[SIMULATED]` receipt). Harbour stays amber. |
| 1:27 | "a lazy system would just use it" | Ghost animation: the 50,000 slides toward Harbour, then hits a wall and stops. |
| 1:29.8 | "that's Kestrel's money, so mine won't touch it" | **X-ray 2:** the funding check, per tenant, real values: `harbour.AUD available 0 < need 1,240.17` next to `never: sum(balances)`. |
| 1:33.7 | "So how does Harbour get funded?" | Harbour lane, empty. Beat drops out. |
| 1:35.4 | "this is the part I'm most proud of" | **Face** (original). |
| 1:37.4 | "You probably saw Binance last week, over $6 billion gone" | Evidence wall: 2-3 real news screenshots stacked with slight offsets on black, paper-white, outlet and date visible. Highlighter on "$6.3 billion". |
| 1:43.5 | "fake job interview…attackers inside the system" | Highlighter moves down the article to those sentences. |
| 1:49 | "money just kept flowing for almost four hours" | A timeline bar draws from 0 to 4h with a counter racing in billions. |
| 1:54.5 | "what if the wallet itself had a limit that no stolen key could get around?" | Black. Type, slow: `A limit no stolen key can get around.` |
| 2:01 | "That's what I built on Metal" | Metal mark, then the mandate as a signed document. |
| 2:03.5 | "signs a rule onto the blockchain" | The real bind transaction ID types on. Receipt `ON CHAIN · METAL`. |
| 2:08.4 | "exactly one payment… exactly what's missing… only into our account… next hour" | The four mandate terms land one per phrase, each with its real value: `max 1 pull`, `cap = shortfall (real USDZ value from the run)`, `payee 0x…(platform)`, `expires +3600 s`. |
| 2:18 | "I press the button and it pulls exactly that" | App capture: zoom on the Metal button press, speed ramp, block turns green. |
| 2:20 | "a real transaction on Metal's testnet" | The public explorer page for the pull tx, scrolled to the transfer. Receipt. |
| 2:23.3 | "Then I tried to cheat" | Type: `Then I cheated.` |
| 2:24.9 | "one coin more…the blockchain refused" | Overpull: `cap + 1` in red, `mandate_cap_exceeded` slams in, then the on-chain refusal tx in the explorer. |
| 2:28 | "a fake wallet that almost looks identical" | The two addresses stacked, characters align; matching ends light white, differing middle lights red, one character at a time. |
| 2:32.7 | "My code catches it and the blockchain refuses it anyway" | Two locks close in sequence: `RINGFENCE` then `METAL`, then `mandate_payee_not_listed` with its tx. |
| 2:37.4 | "Even if someone stole my keys tomorrow…" | Slow hero: the mandate document, tilted UI shot (the one tilt in the film), keys icon taken away. |
| 2:43 | "not $6 billion, not one coin more" | `$6,300,000,000` struck through; beside it the real pull amount. Silence 0.4 s, then the beat returns. |
| 2:47 | "The money lands, Harbour signs off, and everyone's paid" | App: Harbour approve (hold button fills), three lanes go green in sequence. |
| 2:50.7 | "Not one cent went where it shouldn't" | Type: `0 cents crossed.` |
| 2:54 | "This is the real Airwallex dashboard…" | Your Airwallex screenshots as a stack, each pushed in, accent box on the same IDs shown earlier in the app. |
| 2:59.7 | "one client's login on another client's account…blocked" | **X-ray 3:** the real request with Kestrel's token and `x-on-behalf-of: harbour`, response `401 credentials_invalid`, then the 12-direction grid fills (`12 / 12`). |
| 3:05.8 | "a quick one for the engineers. Four decisions matter." | Type: `4 decisions.` A thin index 1-4 appears top-left and stays through this act. |
| 3:09 | "One, the model is never trusted…" | Diagram: model output enters a box labelled `untrusted`; code reprices; the model's number is struck and the code's number replaces it (real priced run). |
| 3:19.5 | "I'll prove that in a second" | Small type: `proof in 60 s →` |
| 3:22 | "Client money is never pooled…" | Three separate balance columns; a `SUM()` tries to form across them and is refused. |
| 3:26 | "Each client has its own Airwallex credential" | Four keys, four locks; real `acct_` IDs; `x-login-as`. |
| 3:37.5 | "Three, exactly once…" | **X-ray 4, the deep one:** sequence diagram, Ringfence <-> Airwallex. The request goes out, the reply is cut (a red scissor on the wire), the retry is a `GET ?request_id=` not a POST, the original transfer is adopted. Then the real `400 duplicate_request_id` response with `details.id` highlighted. |
| 3:49 | "nothing is final until it reconciles…bounce back" | A transfer's state strip: `SCHEDULED -> SENT -> PAID -> FAILED`, the last step real (from the probes), and the ledger reopening the line. |
| 3:57.7 | "Four, a bank change from an email…never happens" | The sample bank-change email; the new details drop into a `QUARANTINE` box; the old details stay lit `in force`. |
| 4:03 | "a different person has to confirm it by phone" | Two different approver badges; the same person is refused. |
| 4:08 | "approval signs a hash of the exact batch…" | The approval card; the batch hash. One amount changes by 1 cent: the hash flips red, `release refused`. |
| 4:15 | "MCP server with no approve tool" | The real MCP tool list as it appears in Claude, with a visible gap where `approve` would be. |
| 4:19 | "A human always signs." | Type: `A human signs.` |
| 4:21.7 | "Then I tried really hard to break it." | Black for 6 frames. Beat drops. |
| 4:23.7 | "a test agent that does whatever it's told…28 attack" | Terminal: the real Gauntlet run, attack names scrolling fast, each turning `FOOLED` then `BLOCKED BY CODE`. Counter to 28. |
| 4:28.5 | "still didn't send one dollar" | `28 fooled · $0 moved`. |
| 4:33.7 | "Claude didn't fall for it" | `Claude: 0 / 28`. |
| 4:35.3 | "20 payment at once…cut off some of the replies" | The storm diagram: 20 arrows fire at once, 3 replies cut, 3 transfers with real IDs, `1 / 1 / 1`. |
| 4:44.6 | "tampered 200 times, caught all 200" | Real ledger blocks; one byte flips; every later block goes red. `200 / 200`. |
| 4:49.5 | "500 random runs, 420 tests" | Real `pytest` output racing, ending on `420 passed`. One cut per number. |
| 4:52.4 | "I think you get the point." | **Face** (original). |
| 4:54.7 | "But don't take my word for it. The demo's live." | Try it page: cursor clicks Red-team me, the agent attacks itself, result lands. Fast cuts. |
| 5:01.9 | "So back to my question…never pays the wrong person?" | **Face** (original). |
| 5:08.2 | "That's Ringfence." | Hard cut to black on the word. White `Ringfence`. |
| 5:09.9 | "Thanks for watching." | Under it, mono: the final ledger head hash, then the URL. Music resolves. Hold 3 s. Out. |

Spoken slips the picture corrects without changing your words: "into their own account" (2:42) shows `payee: Ringfence settlement address only`; "after it marks fail" (3:55) shows `PAID -> FAILED`.

## Content layer for fintech judges (added 6 Nov)

The voice is plain on purpose; the picture carries the depth. Each control gets named once, in the words a payments veteran already uses, as a small mono tag under the decision type. One tag per decision, never a paragraph.

| Moment | Tag |
|---|---|
| Client money is never pooled | `client-money segregation · enforced by Airwallex auth, not by our code` |
| Harbour is short | `per-employer shortfall · act-by before the payroll cut-off` |
| Metal mandate | `VRP-style mandate: 1 pull · cap = shortfall · 1 payee · 1 h · enforced by the chain` |
| Exactly once | `idempotency key · reconcile before retry · never re-POST` |
| Nothing final until it reconciles | `a return after PAID reopens the line` |
| Bank change | `out-of-band callback · four eyes` |
| Hash-bound approval | `what you sign is what is paid` |
| MCP, no approve tool | `separation of duties: the agent holds no approve tool` |

Three additions to the shot list:

1. **Cold open, 5 s, before "Hi".** Three real outcomes, one line each: `401 credentials_invalid` (Kestrel's key on Harbour's account), `1 · 1 · 1 transfers` (20 releases, 3 lost replies), `refused on-chain` (one coin over the mandate). Then "Every ID in this film comes from a live run." It states the film's promise before the face.
2. **Blast radius, on "even if someone stole my keys".** Two columns. A hot wallet: no limit, 4 hours, $6.3bn. Harbour's mandate: one pull, capped at the shortfall (real USDZ), one hour. The same stolen key; the difference is where the limit lives.
3. **Playground, on "the demo's live".** "Your payroll, your own sandbox world, deleted in 30 minutes": the composer, then Red-team me attacking itself. It shows judges they can run their own payroll on it, not watch a fixed demo.

Length: cold open 5 s + voice 287.7 s + end card 5.5 s = 4:58.

## How it is built

- `scripts/capture.py`: one live run on the public site, recording 1920x1080 at 2x DPR, with the pixel box of every element it touches saved per frame (that is what makes the zooms exact). It also records the real HTTP traffic for the X-rays.
- `video/scenes/*.html`: the motion graphics, in the site's own CSS and Inter, animated with GSAP, filled with real data from `/api/ledger`, `/api/state`, `docs/gauntlet/results.json` and the run's own HTTP traces. Rendered frame by frame (seek, screenshot) so timing is exact.
- `video/edit.py`: reads `var/edit/words.json` (word timings from faster-whisper) and the shot list above, then composites frame by frame in Python (zoom and pan with subpixel warps, motion blur on travel, receipts, subtitles) and pipes to ffmpeg.
- Sound: voice cleaned (high-pass 80 Hz, de-noise, gentle compression), -16 LUFS; music ducked 12 dB under voice (attack 20 ms, release 500 ms); a few quiet sound hits on reveals only; master -14 LUFS, -1 dBTP.
