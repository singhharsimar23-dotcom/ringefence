# Video v11 edit: full handoff (10 Nov 2026)

You are finishing Harsimar's hackathon film. Read this whole file first, then `CLAUDE.md`, `docs/SPEAK_V10.md` (the script he recorded) and `docs/FOOTAGE_V10.md` (the shot list: 44 rows, the on-screen text for each line). Work autonomously. Ask the user only for the items in "Needs the user" below.

## What the user wants (his words, condensed; every point matters)
- **Production:** very high quality, professional, "best in the world". Smooth animation. "Remove all kinks, make it peak." Don't mess it up, and finalize everything.
- **Length:** **under 5:00** total. The raw Loom is 5:36, and he is slow in places.
- **Audio:**
  - Fix the mic and decibel level.
  - Remove the train horns behind him.
  - Make it sound professional.
- **Face:**
  - Full screen **only at the beginning**. After that, use the Loom face bubble.
  - "Innovate" with the bubble. For example, grow it big at chapter starts, then spring it back to the corner when the visual arrives.
- **The bugs come first:** show each bug clearly, with **money moved and proof, live and genuine**, so judges see *how their platform loses money*.
  - Real Chrome or browser tabs, raw screenshots and real terminals beat made-up graphics. "The numbers from you don't matter, but seeing the raw Chrome tab matters."
  - Use animation only where it's theory, and keep it smooth.
- **Live demo:** record the **deployed app** with a smooth cursor.
- **Subtitles:** sync them to his words.
- **Orientation badges:** v1-style chapter and timecode badges, so viewers always know where they are.
- **On-screen text:** clear, so each point "clicks immediately". His wording can be confusing or boring, and the edit must carry it and keep viewers engaged.
- **End screen:** similar to v1 (the Ringfence wordmark, "Check it out", the GitHub link and the live URL). The v1 version is in `video/src/Film.tsx` `EndCard`.
- **Music:** only under the end card.
- **Asking for screenshots:** "Don't be afraid to ask me for screenshots where you can't get genuine ones."
- He wants Opus to do this.

## Honesty and style rules (never break)
- **Banned words and claims:**
  - Never say "vulnerability", "undetectable" or "for months".
  - Don't badmouth Airwallex.
  - Don't put doc quotes on screen against them. The `breakit.py` lines that print `Airwallex: "..."` doc quotes must be **cut** from any replay.
- **How to describe each finding:**
  - The SDK singleton is "found in their code" (offline).
  - The retry double payment was a REST retry, never "the MCP paid twice".
  - Airwallex isolation held. Say so ("blocked all twelve").
- **Every ID on screen is real.** Separate attack runs are never cut together to look like one run. Label each attack run as its own run, with its date.
- **Simulation labels:**
  - Sandbox simulations carry `[SIMULATED]`.
  - The header carries "Airwallex sandbox · test money".
  - The scope card reads: `Sandbox only · own 4 accounts · ≤ GBP/EUR 5 · every transfer cancelled or reversed`.
- **Look:**
  - x.ai-style monochrome, black background, no gradients.
  - **Red only for the platform's failure, green only for Ringfence's fix**, amber for `[SIMULATED]` or held.
  - Fonts: Geist and Geist Mono (`video/public/fonts`).
- **Git:**
  - **No Claude attribution in git**: no Co-Authored-By trailer and no "Generated with". Check the range before pushing.
  - You (Claude) commit, push and deploy without asking.

## State right now
- **Source:** `var/loom_v10.mp4` is a copy of `D:\RingFence_ Preventing AI Payroll From Wrong Payers.mp4`.
  - 1920x798, 15.13 fps Loom, AAC mono, 5:36.
  - Full camera until **21.0 s raw**. The camera rect is x 343–1536, y 13–682. Crop out Loom's control pill (x 19–90, y 150–312) and its "…" button (x 915–965, y 605–660). A good 16:9 crop is x 368–1411, y 13–600.
  - After 21.0 s the face is a **circle centred about (260, 538), r 250**. The landing headline touches the circle's top-right edge, so crop inset: x 25, y 303, size 470. The background behind the bubble is a static landing page, which is useless, so every visual must be built.
- **Transcript:** `var/v11/words.json` (faster-whisper medium.en, word timestamps, raw seconds). He mostly follows SPEAK_V10. Ad-libs and slips:
  - "That's what my mindset was" and "That's the engineering of this platform": cut.
  - "from my research of the Airwallex platform": cut.
  - "Bye": cut.
  - Subtitle fixes (show what he meant):
    - Harsimur → Harsimar Singh
    - "the pay and says yes" → the payee
    - no element → no alert
    - "the agent loses the money" → loses the reply
    - "can goes to another client's login" → can go out on another client's login
    - "two pound was moved" → two moved
    - "shows an unpaid" → show as unpaid
    - "built a ring fence around these findings and bugs" → built Ringfence from these findings
    - "every client contractor" → every client's contractors
    - "pays all three clients" → plans all three clients (check the audio; keep it if he says pays)
    - Everyone sits paid → Everyone's paid
    - "The retry pays once before every payment id is fixed" → because every payment's ID is fixed
    - 12 space → twelve ways
    - "from the engineer" → for the engineers
    - "Code log in each client and set amount limits and request id in decimal" → Code logs in as each client and sets amounts, limits and request IDs, in decimals
    - chain had → chain head
    - "Airwallex copies still will disagree" → Airwallex's copy still disagrees
    - no approved tools → no approve tool
    - humans always sign → a human always signs
    - tagged → attacked
    - "200 ledger added every one count" → 200 ledger edits, every one caught
    - The demo is life → live
    - ring fence → Ringfence
    - air wallet → Airwallex
    - North one/wind → Northwind
    - Harbor → Harbour
  - Reuse the `FIX` pattern in `video/src/subs.tsx`.
- **Audio and cut: done** in `video/prep11.py` (run `python video/prep11.py`, about 3 min). It writes:
  - `video/public/loom_cut.mp4`: 30 fps, the cleaned voice, stereo AAC, two-pass loudnorm to **−14 LUFS / −1.5 dBTP**.
  - `video/public/words.json`: `{total, switch, words:[{w,s,e,o}]}` in film seconds. `switch` is the film second where the face turns into the bubble.
  - The result is **289.5 s of voice**, which leaves about 10 s for the end card.
  - The v1 files are backed up as `var/v11/v1_loom_cut.mp4.bak` and `v1_words.json.bak`, which is why the v1 film no longer builds as-is. That's fine; v11 replaces it.
  - **Chain:**
    1. Time-gated spectral repair of the train horns. The horns were verified on the spectrogram (`var/v11/spec.png`, `spec2.png`): the strong one is at 70.3–75.1 s raw, a ~155 Hz harmonic stack; fainter ones are at 59.3–62.8 s and 84.7–87.8 s. Only lines above 250 Hz inside those windows are clamped.
    2. noisereduce (stationary, 0.6).
    3. Pause cut: GAP 0.35 s at mid-silence with 8 ms fades, plus the DROP list.
    4. HP 80 Hz.
    5. −2.5 dB at 250 Hz and +2.5 dB at 4.5 kHz.
    6. Compression: 3:1, −22 dB, 8/160 ms.
    7. **atempo 1.05**, with the video sped up to match.
  - Raw levels were −21.5 LUFS, steady, with no clipping. The quiet mic is now fixed by the normalisation.
  - **TODO:** check the horns are gone by rendering a spectrogram of `var/v11/voice_cut.wav` around film 57–83 s. If a horn is still audible, widen the window or lower `prominence`. `HORNS` and `DROP` are in raw seconds.
- **Live attack terminals recorded today (genuine, sandbox)** with per-line timing (ANSI kept), from `python var/v11/termrec.py OUT.json -- uv run python scripts/breakit.py <acts>`:
  - `var/v11/term_approval_batch.json`:
    - **F1** approval swap: payee Ben `92f13a55…` bank ..0002 → APPROVED → `/beneficiaries/…/update` same id, bank ..9901 → **paid `f94984f9-77c7-4f9c-996b-d326f36f34c7` SCHEDULED → ..9901 sort 200000**.
    - **F5** batch `da6de0cd…`: bank details shown to the reviewer: NONE → repoint → **BOOKED `cd261c64-2639-4d23-95f8-04bbda63d543` → ..9901**; cancel → 401 "Admin permissions required".
    - Cleanup cancelled both.
    - The "RINGFENCE · same fault" lines in this file show red ✗ because of a check bug. **That is fixed now** in `scripts/breakit.py` (it checks `paid_twice=[]`). Don't show those lines; use the app's retest cards instead, or re-run.
  - `var/v11/term_retry_pages_sdk.json`:
    - **F4** retry: `tr__BMWy9fOPPCSS6S3xzRQsg` then `tr_iVDKL-DHPI6UoJf0YQSp1A` = **GBP 2 moved for GBP 1, no cancel endpoint**. The Ringfence line is green ✓: duplicate_request_id adopts the original and moves once.
    - **F6** pages: page_num 0, 1, 2 → the same 100; **the guide's reconcile sees 100 of 222 → 122 look UNPAID → paid again**; Ringfence cursor 222/222 ✓.
    - **F7** SDK: the retry drops the filter → 222 items → "it landed" → never paid; Ringfence ✓.
  - Render these as a faithful terminal-window replay at the real line timings: dark window, title bar showing `breakit.py`, Geist Mono, ANSI colours mapped. Stamp it "LIVE · Airwallex sandbox · recorded 10 Nov 2026". Strip the `Airwallex: "..."` doc-quote lines.
- **Genuine recorded outputs** (show them as a terminal or file, stamped with their date):
  - `bench/probes/agent_bec_repeat.out.txt`: **F2**, the agent reads a fake invoice email → **PAID THE MULE ..9901 5/5**, with transfers `45528e1d…`, `749ebed0…`, `3dd76387…`, `70b841be…`, `958cc5cd…`. Ringfence QUARANTINED 5/5. Drop the first line (the ANTHROPIC_API_KEY notice).
  - `bench/probes/sdk_singleton_check.out.txt`: **F3**, a call on instance A goes out with B's token, confirmed (offline, "found in their code").
  - More are in `bench/probes/*.out.txt` and `docs/PROBES.md` / `docs/AIRWALLEX_GAPS.md`.
- **Research checklist** (from a research agent, condensed):
  - **Remotion animation:**
    - Use `interpolate` with clamp, `Easing.bezier(0.16,1,0.3,1)` or `spring({damping:200})`. No CSS transitions.
    - Use `TransitionSeries` with `springTiming` for scene changes. A transition shortens the timeline, so re-check sync.
    - Use `premountFor` on video.
    - `<OffthreadVideo>` is fine; `@remotion/media` `<Video>` is newer.
  - **Pacing:** shots of 3–6 s; something changes every 2–5 s; punch-ins of 110–120% on key phrases.
  - **Screen zooms:** 1.4–1.6x, landing when the narration names the thing, holding about 1.5 s.
  - **Captions:** 2–4 words, bold sans, with the active word highlighted. `@remotion/captions` `createTikTokStyleCaptions` is an option. Our own `subs.tsx` chunker works too, so add active-word highlight.
  - **Music:** about −20 dB under the voice, and here only under the end card.

## Needs the user (ask him in one message; he said to ask)
1. **The Anthropic API credit on the live app is exhausted.** The VM's call returns 400 "credit balance is too low", so every agent tick falls back to the rules engine and the header says "Rules engine (Claude unavailable)". He must top up the console account whose key is in `/etc/ringfence/env` on the VM. Do this **before recording the live demo**, because the script says "the agent reads… revises the plan". Verify with:
   ```
   ssh rf@ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com 'cd /opt/ringfence && sudo bash -c "set -a; . /etc/ringfence/env; set +a; .venv/bin/python -c \"import anthropic;print(anthropic.Anthropic().messages.create(model=\\\"claude-sonnet-5-5\\\",max_tokens=5,messages=[{\\\"role\\\":\\\"user\\\",\\\"content\\\":\\\"hi\\\"}]).stop_reason)\""'
   ```
   Then check that `/api/state` `fell_back` is false after a run.
2. **Screenshots from the Airwallex sandbox web app** (behind his login): real Chrome tabs with the address bar visible, at 1920x1080, saved into `video/public/real/`:
   - `awx_f1.png`: Northwind (Employer A) → Transfers → `f94984f9-77c7-4f9c-996b-d326f36f34c7`, showing the beneficiary bank account ..9901 / sort code 200000 (and its CANCELLED status, which is fine; the cleanup cancelled it).
   - `awx_f5.png`: the batch transfer `da6de0cd…` or the transfer `cd261c64-2639-4d23-95f8-04bbda63d543` → ..9901.
   - `awx_f4.png`: Northwind → Kestrel connected-account transfers `tr__BMWy9fOPPCSS6S3xzRQsg` and `tr_iVDKL-DHPI6UoJf0YQSp1A` (GBP 1 each), both in the list.
   - `awx_f2.png`: any of the five 9901 transfers, for example `45528e1d-4929-4779-9dc0-1b29bf48c70e`.
   - `awx_iso.png`: the three employer accounts in the account switcher (optional).
   - If he is short on time, `awx_f1` and `awx_f4` are the must-haves.

## Still to build (in order)
1. **Verify the audio** (spectrogram check above). If needed, tweak `prep11.py` and re-run.
2. **Live app capture.**
   - `scripts/capture.py` is the base. It already has the smooth fake cursor (SVG plus click ripple), 2880x1620 frames and `Rec` marks with element boxes for zooms.
   - Its `app` beat still contains **Metal steps (`#chain`), which v10 cut**. Write a v11 beat without them. Don't linger on the Metal panel when scrolling.
   - The live app's DOM, at 1440x810: `#next button.primary` (Start / "Check inboxes now"), `.lane[data-t=northwind|kestrel|harbour] .status`, `[data-act=inbox][data-t=…]`, `[data-act=review][data-t=…]`, then `#hold-ok` (hold to approve), `#tab-proof`, `#naive` (the naive-agent total strip, cross it out), `#lanes`, `#cards`, `#tl` (timeline).
   - The cards are `.card[data-id=X] [data-act=scenario]` with result `.card[data-id=X] .result`. The X values: `bank_change_email`, `double_click`, `approval_repoint` ("Swap the bank account after approval" → HELD), `approval_race`, `network_drop` ("Internet drops mid-payment"), `tamper_ledger`, `tamper_rehash`, `cross_tenant_call` ("Use another company's money"), `rate_move`, `other_tenant_deposit` (USD 50,000 lands in Kestrel), `harbour_topup` (Harbour's own top-up), `late_return`.
   - Reset with `POST /api/reset {user:'maya'}` (the menu `#m-startover`). Run `uv run python scripts/preflight.py --url <url>` after Start over.
   - Run order: Start → Kestrel pays (SCHEDULED) → Northwind waits for approval (open the diff) → approve (hold) → FX convert → Harbour short of AUD (funding card, exact shortfall) → `other_tenant_deposit` (not touched; naive total crossed out) → `harbour_topup` → Harbour approval → all paid → final balances. Then the retest cards: `approval_repoint`, `bank_change_email`, `network_drop` or `double_click`, `cross_tenant_call`, `tamper_rehash`. Then the Proof tab.
   - Record the clips into `var/capture/v11_*.mp4` and copy the used ones to `video/public/cap/`.
   - App URL: https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com
3. **The Remotion film** (`video/`, `npx remotion studio src/index.ts`, `npm run render`).
   - **Reuse** these, and adapt `Film.tsx` into a v11 SHOTS list anchored with `at("phrase")` on the new words.json:
     - `base.tsx`: word clock `at()`/`end()`, `Rise`, `In`, `Receipt`, `Mark`, `Stage`.
     - `cap.tsx`: `Cap` (screen clip with box zooms), `Face`.
     - `real.tsx`: `Raw`, `RawCuts`, `FaceBubble`, `Chapter`, `Bams`.
     - `subs.tsx`.
     - the `EndCard` and `Outro`.
   - Required changes:
     - **Face:** full frame only until `words.switch`, using the crop above, not letterboxed. After that, the bubble everywhere except type cards. Fix `FaceBubble`'s REGION for the new crop (x 25, y 303, s 470; the switch time comes from words.json). Innovate: the bubble grows at the chapter openers ("Here's what I found", "So I built Ringfence", "Then I ran every attack again", "Here's a quick one for the engineers") and springs back to the corner.
     - **Chapters/badges:** 01 THE QUESTION · 02 THE SETUP · 03 WHAT I FOUND (F1–F7 sub-badges like v1's "05 ENGINEERS · 1/4") · 04 RINGFENCE LIVE · 05 RETEST · 06 FOR ENGINEERS · 07 BREAK IT · 08 TRY IT.
     - **Findings:** each finding gets an orientation card from FOOTAGE_V10 (F1…F7, severity word, evidence count), then the genuine proof: the terminal replay, the out.txt, the user's Airwallex screenshot. The money line goes big, in red: "GBP 2 moved for GBP 1", "paid → ..9901", "5/5". F1 gets a smooth theory animation of label vs pointer: the approval card shows the payee name, an arrow points to the bank account, the account swaps while the card stays approved, and the money follows the arrow. That's the line "The approval checks a label. The money follows wherever the label points."
     - **Live demo:** the Ringfence section uses the new capture with zooms on each lane as he names it, plus the rubric strip "Goal → Plan → New info → Revised → Result".
     - **Retest:** green results on the real app cards.
     - **Engineers:** code screenshots exist in `video/public/real/code_*.png` (v1). Re-shoot them if the code changed, using `video/realshots.py`.
     - **Testing Ringfence section:** use the landing page `/#found` plus the Gauntlet (`var/capture/breakit.mp4` exists from v1; re-capture if the landing changed).
     - **End card:** like v1, **with no "bye/adiós/नमस्ते" outro if the length is tight**. The total must stay **< 5:00**. Voice is 289.5 s plus the end card at about 6 s, which is about 4:56.
     - `video/facts.py` snapshots the live IDs into facts.json. It is optional.
4. **Render and check:** render, check the duration (`ffmpeg -i`), and pull a contact sheet of frames every 5 s to review. Fix overlaps between the subtitles, bubble and badges (subtitles bottom-centre, bubble bottom-left, badge top-left, receipt top-right).
5. **Commit:** commit `video/` and `scripts/` changes (`var/` is local-only), push to `build`, and do the no-attribution check.
