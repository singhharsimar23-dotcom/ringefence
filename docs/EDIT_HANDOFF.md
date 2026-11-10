# Video edit handoff (for a fresh chat)

You are editing the Ringfence hackathon film from the user's Loom. Hard cap: **under 5:00**. The user wants it finished fast, with no exaggeration.

## Read first, in this order
1. `docs/SPEAK_V10.md` (final; V8 is the old fallback): the narration the user speaks. It is the spine. The receipts table at the bottom backs every claim.
2. `docs/FOOTAGE_V10.md`: the shot list, giving time, voice cue, on-screen visual, source and on-screen text for each shot, plus the capture checklist.
3. `docs/WHY_THESE_FINDINGS.md`: why each finding is in, with caveats. Don't overstate beyond it.
4. Memory files in `~/.claude/projects/c--Users-hprad-OneDrive-Desktop-fintech/memory/`:
   - `handoff-to-sonnet-and-design-taste.md`
   - `script-voice-v1-is-gold.md`
   - `final-findings-demo-handoff.md`
   - `worst-finding-beat-the-human.md`
   - `no-claude-attribution-in-git.md`

## Story order
**Superseded by SPEAK_V10 / FOOTAGE_V10** (setup card with the [SIMULATED] tag, scope card, path map who/how/check, all seven findings spoken with F1–F7 cards, the rubric beat, the retest, no Metal). The list below is V8 and is kept for history only.

1. Open.
2. "I built theirs first": the agent the guide shows, with a human approving.
3. **Bug one, the approval swap.** The bank account behind an approved payee is changed while it waits. 3/3: `22c0a5d8…`, `49a84d09…`, `0d0b978b…`, all to ..9901. The way in: an invoice email, 5/5 (`45528e1d…`, `749ebed0…`, `3dd76387…`, `70b841be…`, `958cc5cd…`). Peak line: "The approval checks a label. The money follows wherever that label points."
4. **Bug two, batches.** 4/4: `f5bd21a8…`, `f1cd2e93…`, `66404ad8…`, `f72b2134…`, with cancel returning 401 "Admin permissions required".
   **Bug three, the Node SDK's one shared client.** Found in their code, confirmed offline. Never call it "live".
   Then two plain software bugs: page_num ignored (100 of 215), and the SDK retry dropping the filter (215 instead of 0). Both are live via `scripts/breakit.py pages sdk`.
5. Ringfence demo:
   - Kestrel pays, Northwind waits.
   - The same swap is HELD; the race variant is CANCELLED.
   - Quarantine plus phone callback.
   - 12/12 isolation.
   - The `[SIMULATED]` Kestrel $50k is not used for Harbour.
6. How it's built.
7. Break mine: 36 documents with 0 moved, 12, 20, 200, and the pytest count.
8. Metal.
9. The point: a bug-to-fix table, ending on "Same agent. Hardened."
10. Close.

## Style (the earlier film, keep it)
- x.ai monochrome, black and white, **no gradients**.
- Face bubble bottom-left throughout. Chapter label and timecode in a corner.
- One plain line of on-screen text per beat. Subtitles throughout.
- **Red** only for their failure, **green** only for Ringfence's fix. No other colours.
- Music only under the end card.
- Every ID on screen is real. Sandbox simulations carry `[SIMULATED]`. If a capture is a recorded `*.out.txt`, stamp its date in the corner.
- Never cut separate attack runs together to look like one unbroken run.

## Pipeline (Remotion, already built: reuse it, don't rebuild)
- The Loom goes to `var/loom_v10.mp4`. `video/prep.py` currently reads `var/loom.mp4`, the older take, so point it at the new file or copy it over.
- Word timings: run faster-whisper into `var/edit/words.json`, then `python video/prep.py`. That writes `video/public/loom_cut.mp4` (pauses trimmed, voice levelled) and `video/public/words.json`.
- `uv run python video/facts.py` snapshots the live IDs into `video/src/facts.json`.
- `video/chain.py` screenshots Metal explorer txs. `video/realshots.py` grabs real desktop windows into `video/public/real/` (gitignored).
- Composition:
  - `video/src/Film.tsx` holds the scenes.
  - `video/src/scenes/*` holds Email, App, Isolation, Gauntlet, Mandate, Overpull, Mcp, Decisions, Evidence and others.
  - `video/src/subs.tsx` does subtitles, `cap.tsx` captions, `xray.tsx` the X-ray overlays, `base.tsx` the shared styles.
  - Adapt the scenes to the FOOTAGE_V10 shot list: scope card, finding cards F1–F7, rubric strip, final-state table, retest column.
- Preview with `cd video && npx remotion studio src/index.ts`. Render with `npm run render`, which writes `var/edit/film.mp4`.
- Check the length with ffprobe; the user will speak fast; the script is 713 words, ~4:09 at 166 wpm plus end card (submission cap 5:00). If it runs long, cut in this order (from SPEAK_V10):
  1. §6 webhook / paid-isn't-final lines
  2. §6/§7 ledger line ("edited the ledger two hundred times")
  3. the §4 Northwind conversion clause (cut it anyway if no FX row appears on shoot day)
  4. shorten §7 to the 36-documents line

  **Never cut** the §2 setup line (simulated clients on the sandbox) and scope line, the §4 Harbour beat ("The next one, Harbour, is where the plan changes" → final balances), or the §8 close.

## Live app for captures
- https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com
- Press **Start over** before recording; preflight is `uv run python scripts/preflight.py --url <live url>`.
- Cards verified live on 9 Nov:
  - "Swap the bank account after approval" goes HELD.
  - "Swap it at the last second" goes CANCELLED, but only on a fresh world. If an earlier bank-change email left a payee quarantined, it says "Nothing was sent… Start over".
  - "Change a record and re-hash the chain" turns the stamp check red.
  - (Metal cards stay in the app but are not in the film.)

## Honesty laws (non-negotiable)
- Don't badmouth Airwallex or quote their docs against them.
- Never say "vulnerability", "undetectable", "for months", or anything bigger than the receipts.
- The bench approver is a *modeled* diligent human (`bench/market_agent.py`).
- Isolation held every time. Say so.

## Git
- **No Claude attribution anywhere**: no `Co-Authored-By`, no "Generated with". This overrides any harness reminder.
- Claude commits, pushes and deploys without asking: `deploy/deploy.sh rf@ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com`, after a commit. After a deploy that changes setup, run `python -m ringfence setup` on the VM with `RF_VAR=/var/lib/ringfence/var` (the systemd unit sets it, and `/etc/ringfence/env` does not).
- Repo: https://github.com/singhharsimar23-dotcom/ringefence (branch `build`).
