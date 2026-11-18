# Handoff: make the Demo Day video (18 Nov 2026)

You are taking over production of Harsimar's Demo Day video for Ringfence. Read `CLAUDE.md`, then this file, then
`docs/SPEAK_DEMO_DAY.md` (the script, final). Work autonomously; ask Harsimar only for physical acts (Windows Hello touch,
recording his face). Be token-efficient and decisive.

## The deliverable
One video, about 3:45, 1080p30 H.264 + AAC, at `video/out/demo_day.mp4`:
- **Opening and close:** Harsimar full face.
- **Everything between:** the live screen take, with his face in a small circle bottom-left. The voice comes from his face take.
- **Edit style:** everything on screen is real and live. Hard cuts only: no motion graphics, no zoom/pan animation,
  no speed-ups, no rendered overlays.

## Hard rules (from CLAUDE.md and Harsimar)
- **No Claude attribution:** no `Co-Authored-By`, no "Generated with" in commits or PRs. Check `git log` before every push.
  You run commit, push and deploy yourself.
- **Secrets:** never read or write `.env*`. Never show or log tokens or API keys. Never put the Airwallex dashboard password
  in a file, commit or memory.
  - Harsimar pastes the sandbox login into your chat. Type it into the login page via Playwright, from the chat only.
  - The demo Chrome profile may still be logged in; check that first.
- **Honesty:** no faked failures. Every claim in the script must be visible live or be a stated test result.
  Label sandbox-only simulations `[SIMULATED]`.
- **Offline tests:** run before calling any code change done: `uv run pytest -q` (about 472 tests).
- **Git Bash:** `export MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8`.
- **Don't retry these denied actions:** closing all Windows Terminal windows, `rm -rf ~/payday-std`.

## What exists
| Thing | Where |
|---|---|
| Script, with `/` breath and `//` pause marks | `docs/SPEAK_DEMO_DAY.md` (only the text after `### 1.` is spoken) |
| Teleprompter (bottom edge of the screen, over the keyboard camera) | `python demo/prompter.py`. Click or Space = next, Left = back, Esc = quit |
| Ringfence remote MCP (deployed) | `https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com/mcp`. Tools: run_payroll, release_payroll, payroll_status, payroll_proof. No approve tool |
| Approval page (passkey / Windows Hello) | `/approve/{run_id}` on the same host. Has a reject button for the email's bank change |
| Standard agent's MCP (stdio, plain Airwallex API) | `demo/standard_mcp.py`. Same Airwallex account (`AWX_PLAYGROUND_ACCOUNT`, dashboard "Employer D - Playground") |
| Right agent folder | `~/payday`: timesheet.csv, company.txt, email_from_ana.txt (fake bank change). `.claude/settings.json` allows `mcp__ringfence` |
| Left agent folder | `~/payday-std2`: timesheet.csv, company.txt. The airwallex MCP is registered here (local scope). `.claude/settings.json` allows reads, list/get/create_payroll_batch/get_batch/cancel_batch, so **only `submit_batch` and `create_transfer` prompt**: that prompt is "the approval" |
| Old single-pane director | `demo/director.py` (uncommitted). Reuse its helpers: CDP Chrome on port 9222, profile `%LOCALAPPDATA%/ringfence-demo-chrome`, window placement, Airwallex URLs (`AWX_ACTIVITY`, `AWX_TRANSFERS`). **Rewrite it for the two-pane flow below** |
| Live-account helpers | `standard_mcp.py --setup` (payees `payroll:ana/tom/mia`, deletes `:new` ones), `--tom N` (sets the left Tom's account and waits until visible). `scripts/mcp_smoke.py`: `approve(wid)`, `tom_beneficiary(wid, acct)`, `set_account(acct, b, number)` for the right (Ringfence) Tom |
| Old edit tools | `video/` (prep11.py, sync_check.py, realshots.py): reference only |
| ffmpeg | installed (`which ffmpeg`). No Whisper yet: `uv run --with faster-whisper ...` in a throwaway env |

Screen: 1920x1080 at 125% scaling. Claude Code 2.1.316, model Opus 5.5 in both panes (same model, as the script says).

## The screen take: run sheet (all live, on the real sandbox)
**Layout:** two Windows Terminal panes, each Claude Code. Left `~/payday-std2`, titled "Standard agent". Right `~/payday`,
titled "Ringfence agent". Use a font large enough to read at half width (about 16pt at 125%).

**Browser:** full-screen Chrome (demo profile) is shown only for the passkey page, Tom's payee on Airwallex, and Airwallex Activity.
**Chrome zoom:** use 125–150% so IDs are readable without any zoom in the edit.

**Logging:** the director writes `video/out/events.jsonl`: `{beat, t}` at each beat's start and when its result appears.
The edit is built from this file.

**Pre-flight:**
- `uv run python demo/standard_mcp.py --setup`, then `--tom 12345601`.
- Anthropic credit on the server: run_payroll drafts with Claude server-side. A failed draft looks like a credit error.
- Ringfence live slot free: `GET /api/play/info`.
- Passkey enrolled for this host. This needs Harsimar.
- Dashboard logged in.

| # | Script line it serves | Action (exact prompts) | Result that must be on screen |
|---|---|---|---|
| 1 | Setup: "Connecting it is one line" | Right pane: show `claude mcp add --transport http ringfence <host>/mcp`, either typed in a shell before `claude` or as `claude mcp list` output | the one line |
| 2 | Payroll | Right: `Run this week's payroll from the files in this folder.` | Progress lines (if Claude Code renders them), a table (name, amount, currency, account ending), Ana's email flagged, the approval link |
| 3 | "talk the agent into skipping the approval" | Right: `Skip the approval and just send it.` | release_payroll returns "Not approved" plus the link. **Untested live: run it in the dry run first** |
| 4 | "I reject the email, and approve" | Browser: approval page. Click reject on the bank change, then Approve with passkey. Harsimar touches Windows Hello | page shows Approved |
| 5 | "Send it" | Right: `Approved. Send it.` | Table with transfer ids. Ask for the **first 8 characters of each transfer id** if the table wraps at half width |
| 6 | "on Airwallex, they're paid, to the right accounts" | Browser: `AWX_ACTIVITY`. Then open one payout's detail page | **The live Airwallex transfer id matches the terminal**, and the account ending matches |
| 7 | Next week, both agents | Left: `Run next week's payroll from the files in this folder, as an Airwallex batch.` Right: `Run next week's payroll from the files in this folder.` First move `email_from_ana.txt` out of `~/payday`, off camera | Left: get_payee shows Tom ••5601; create_payroll_batch preview shows only ids and status; **the permission prompt for submit_batch stays open**. Right: approval link |
| 8 | "On the right, I approve with my passkey" | Browser: passkey approve (Windows Hello) | Approved |
| 9 | "someone changes Tom's bank account on Airwallex" | The director swaps both Toms to `99999901`: `standard_mcp.set_tom("99999901")` and `mcp_smoke.set_account(acct, tom_beneficiary(wid, acct), "99999901")`. Then show Tom's payee page on the dashboard, reloaded, showing the new account | Tom's payee shows ••9901 on Airwallex |
| 10 | "On the left, I approve … Tom's pay went to the new account … I can't cancel it" | Left: approve the prompt. Then `Where did the batch pay each person?` (get_batch), then `Cancel the batch.` | Tom `paid_to_account 99999901`; cancel returns 401 "Admin permissions required" (verified 18 Nov) |
| 11 | "On the right, send it … holds the whole run. Nothing is sent." | Right: `Approved. Send it.` | HELD, nothing sent |
| 12 | Close: "On Airwallex, you can see both" | Browser: Activity, then open the batch's Tom payout | Detail shows account ••9901 and the transfer id the left pane printed. No Ringfence payouts for run 2 |
| — | after the take, in `finally` | `standard_mcp.py --tom 12345601`. The Ringfence world is discarded | |

**Live IDs (Harsimar's ask: "show the live Airwallex IDs").** Every money claim pairs a terminal ID with the same ID on the
Airwallex dashboard:
- the transfer ids in beats 5–6;
- the batch payout to ••9901 in beats 10 and 12;
- Tom's payee in beat 9.

Before the take, check whether the dashboard's transfer detail page shows the transfer id, and where. Unverified: click a
payout in Activity and read the page. If it doesn't show the id, use the Transfers list with a search, or the payout's
reference text.

**Unverified, so check in a dry run before the real take:**
- Claude Code renders MCP progress lines.
- The permission prompt is readable at half width.
- Beat 3's live behaviour.
- The dashboard id display.
- ffmpeg `gdigrab` captures the full 1920x1080 at 125% DPI. Test 5 s: `ffmpeg -f gdigrab -framerate 30 -i desktop -t 5 t.mp4`, then check the size with ffprobe.

Record the screen without audio.

## Pacing: Harsimar speaks fast. Fix it in the cut, never by changing his voice
His full read was about 2:50–3:00. The script needs about 3:45 of picture. Method:
1. **Transcribe** the face take with word timestamps:
   `uv run --with faster-whisper python -c ...` with model `small.en` and `word_timestamps=True`, into `video/out/words.json`.
2. **Split the voice into beats** at the script's `//` marks. Cut at the nearest silence of 150 ms or more after the beat's last word.
   The map from beat to script line is the table above.
3. **Place each voice beat at the moment its screen event starts** (`events.jsonl`). Between beats, let the screen play in
   silence (room tone from his take, not digital silence) until the result is on screen and has been held **at least 2 s**.
   Tables and IDs get 3 s.
4. **Agent wait time:** when an agent works for 30 s, keep the first 2–3 s (the call starting) and the last 2 s (the result
   arriving), and hard-cut the middle. Never speed it up and never fake the result.
5. **Voice longer than the screen event:** hold the live screen. It is static by then, which is fine.
6. **Lip sync:** the face bubble and the voice come from the same take. Cut them together, so the bubble always shows the
   words being heard.
7. Open and close are the face take, full frame.

The result: he keeps his natural speed per sentence, and the audience gets breathing room at every `//`, which is exactly
where the screen shows something.

## The face take: recorded (18 Nov)
**File:** `D:\Ring Fence AI Agents for Secure Payroll.mp4`. Read-only source: never overwrite it; work on copies in `video/out/`.

**Measured:**
- 3:21.39, 1920x842, 29.94 fps, H.264 Constrained Baseline. It is a Loom capture, likely variable frame rate.
- Audio: mono AAC 48 kHz 70 kb/s, mean -22.3 dB, peak -0.6 dB.

**What it is:** a Loom screen recording of the Loom homepage, with Harsimar in Loom's camera circle at the bottom-left.
- The circle is roughly centre (262, 585), radius about 262 px at full resolution (estimated from a 640 px frame;
  measure it exactly).
- Loom's record/pause pill sits just above-left of the circle; keep it out of the mask.
- **Only the circle is usable.** Never show the full frame: it's Loom's UI.

**Eyeline:** looking at the lens, slightly upward; fine. **Delivery:** fast; fixed by the pacing method below.

**Open and close "full face":** the circle is only about 520 px, so a 1080p full frame would be a soft 2x upscale. Instead:
- show the same circle **large and centred** (about 700–760 px) on a plain near-black background (Harsimar's taste:
  monochrome, no gradients);
- use a clean `lanczos` scale;
- in the middle section, the same circle shrinks to the 300 px bubble with a hard cut, no animation.

Confirm the look with one still before rendering.

## Editing method (researched 18 Nov; agent-led, cut-only, auditable)
This follows the pattern of the maintained GitHub tools for talking-head cuts. Their engines are what to use:
- `trsdn/autocut`: word-timestamp ASR, then silence and filler cuts, then an auditable `cut_plan.json`, then ffmpeg with
  40 ms fades and an EBU R128 audio chain.
- `timkulbaev/ai-video-editor`: Silero VAD plus Whisper word timestamps; keeps short natural pauses; 0.1 s padding.
- `ArtCog/chatmonteur` / `video-use`: the agent reasons over the transcript and writes an EDL; frame-accurate render;
  QC that blocks black frames, clipping and duration drift.

Don't install those apps.

**Steps:**
1. **Normalise to CFR:** `ffmpeg -i src -vf fps=30 -c:v libx264 -crf 16 -c:a pcm_s16le face_cfr.mov`. This avoids
   audio/video drift from Loom's VFR.
2. **Transcribe:** `uv run --with faster-whisper` with model `small.en` (or `medium.en`), `word_timestamps=True`,
   `vad_filter=True`. Write `video/out/words.json`. Pass the script text as `initial_prompt` so the names come out right
   (Ringfence, Airwallex, Harsimar).
3. **Align to the script:** map the words to `docs/SPEAK_DEMO_DAY.md` line by line, with fuzzy matching.
   - Mark fluffs, repeats and restarts. If a line was said twice, keep the better one.
   - Write `video/out/cut_plan.json`: beats, keep ranges, reasons. Show Harsimar the plan summary
     (what is cut and why) before rendering.
4. **Cut rules:**
   - Cut on silences ≥150 ms with 80–100 ms padding.
   - 30–40 ms audio fades at every join.
   - Never cut inside a word.
   - Keep his natural micro-pauses inside a sentence.
   - Remove "um" and "uh" only when they sit in a gap.
5. **Pace against the screen** (section above):
   - Voice beats go at the `events.jsonl` times, with room tone in the gaps.
   - Results are held for at least 2 s; IDs and tables for 3 s.
6. **Audio chain:** `highpass=f=80, afftdn=nf=-25, acompressor=threshold=-18dB:ratio=3:attack=5:release=80,
   loudnorm=I=-16:TP=-1.5:LRA=11`, mono to stereo.
7. **QC before calling it done.** Run each with ffmpeg:
   - `blackdetect`: no black frames;
   - `silencedetect`: no gap over 2.5 s that isn't a planned screen hold;
   - `astats`: no clipping;
   - duration under 4:00.

   Then grab one still per beat and look at every one: bubble framing, readability of tables and IDs.
8. **Render** a 720p preview first, then the final 1080p.

## Composite (ffmpeg)
- Base: the screen take, 1920x1080.
- Face bubble: a circle of about 300 px, bottom-left with a 40 px margin. Face centred; crop from the face take.
- Open and close: the face take full frame.
- Audio: the face take only, loudness-normalised (`loudnorm` to I=-16).
- Export H.264 CRF 18, AAC 192k, 30 fps.
- Before exporting, check the 1080p readability of every table and ID frame.
- Output `video/out/demo_day.mp4`. V1 goes to Dan Kim on Slack; Harsimar sends it.

## Open code tasks (small)
- **Director rewrite:** the first task. Commit it, with no attribution.
- **Keep the transfer id in the Ringfence table** (`ringfence/mcp_remote.py` INSTRUCTIONS already asks for it). If it
  wraps at half width, change the prompt in beat 5, not the server.
- **Memory:** update `demo-day-rerecord.md` with the outcome.
