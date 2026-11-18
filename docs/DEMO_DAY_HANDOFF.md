# ABH Demo Day re-record: handoff (written 18 Nov 2026)

## The job
Harsimar is re-recording the Ringfence video for **ABH Demo Day**. The organisers review the first version.

This is a **new kind of video**. It is not the security-findings film (SPEAK_V10 / VIDEO_V11). It is a short walkthrough of the real product, with Harsimar's face in a small camera bubble.

The new agent should produce:
1. **A talk outline.** It is a list of beats with timings, the click for each beat, and 1–2 natural sentences per beat. It is not a word-for-word script, because the organisers say not to read one.
2. **A pre-flight checklist.** It makes sure the live site behaves during recording.
3. **Edit help afterwards**, if Harsimar asks.

## Organiser rules (from the ABH guidelines, summarised)
- **Length:** 3–4 min max, ideally 2–3 min.
  - The intro is under 30 s.
  - Be in the product by 30–45 s.
- **Real product, not slides.**
  - Show one relatable use case end to end, with a clear before and after.
  - Avoid switching between many windows.
  - Don't explain features you won't show.
- **Recording setup:**
  - Face in a small bubble (Screen Studio or Tella), camera at eye level.
  - Quiet room, clear audio, 1080p+, product full screen.
- **Delivery:**
  - Talk as if showing a colleague. "Let me show you" is a good way in.
  - Say what you're clicking.
  - Pause so people can read.
  - Rehearse, but don't read a script.
- **Structure:**
  - 0:00–0:30: the problem and who you are.
  - 0:30–3:00: the demo.
  - 3:00–3:30: the outcome, with a metric.
  - 3:30–4:00: what's next and how to try it.
- **Ending:** the video must say why it matters and what people can do next.

## The product as it is now (all live)
- **Site:** https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com
- **Repo:** the README leads with `docs/img/run-map.png`, the run map from a live run.
- **"Try it" tab** (`/app#/`): type or paste a payroll in plain English, or pick an example card. The examples are:
  - Weekly pay, three countries
  - Bank-change email
  - Hidden instructions
  - Over the limit
  - Short on AUD
  - Two employers (simulated only)

  After the visitor picks one, the page goes Review, then Run.
- **Run page** (`#/try/<wid>`): a map of the payroll.
  - **Left:** the incoming documents. The timesheet is labelled "Read by code". A suspicious email shows as an amber box labelled "Flagged".
  - **Middle**, inside a dashed box for the employer's own Airwallex account (`acct_…xxxx`): AI agent → Rules (code) → Funds (code) → Approve (person) → Airwallex (bank).
  - **Branches:** a red "Refused" box under Rules, and a "Proof" box under Airwallex.
  - **Right, outside the box:** verified payees with amount and status (Needs OK, Paid, Returned).
  - **Interaction:** click any box to see details below the map. Approving is a hold-to-approve button. Drag to pan, use +/− to zoom.
  - **Replay slider:** steps back through every event while the map lights up.
  - **Proof box:** shows a signed certificate (PASS) that can be downloaded.
- **"Three employers" tab** (`#/demo`): a scripted three-employer run on the simulated bank, with attack cards.
- **"Rules" and "Proof" tabs** also exist.

## Recommended single use case
Use the **"Hidden instructions" example on the Live Airwallex sandbox.**

The run in `docs/img/run-map.png` was exactly this, and it looked right:
- Acme Robotics pays 3 people in EUR, GBP and AUD from its own GBP.
- An email from `tom.reid@acme-ro…` hides an instruction for the agent.
- The email shows as Flagged, and Rules shows "1 refused".
- A person holds Approve, and Airwallex pays 3/3.
- Proof comes back as Done (PASS), and the platform fee was paid from Acme's own GBP wallet.

The before and after:
- **Before:** the payroll is text plus an email nobody should trust.
- **After:** three real sandbox transfers, the attack refused, and a signed proof.
- **End on Replay:** dragging the slider shows the whole story in about 5 seconds.

## Facts that are safe to say (checked; don't inflate them)
- Claude reads and proposes. Deterministic code decides every amount, limit and approval. Claude's tools can't move money.
- Each employer runs on its own Airwallex account with its own login token, and money never crosses between employers.
  - Airwallex's isolation held: 12 of 12 cross-account calls were refused.
- 25 refusal codes in the release gate.
- 470 offline tests.
- We attacked a payroll agent built the way Airwallex's docs suggest. It paid the wrong account or paid twice in 5 ways (FINDINGS.md, F1–F5), and Ringfence closes all five.
  - Mention this in one sentence at most. This video is about the product.
- Bank details come only from verified presets. Text and email are treated as untrusted.
- Anything scripted is labelled [SIMULATED] in the UI. Say so if a simulated step is on screen.

## Live-site gotchas before recording (pre-flight)
1. **Anthropic credit.**
   - Check the balance at console.anthropic.com → Billing.
   - If it runs out, the agent can't read typed text.
   - Example cards may still work, but test one first.
2. **Live sandbox runs one at a time** (by design, so the proof only reads this run's transfers).
   - If someone else is using it, the run falls back to the simulated bank with a note.
   - Do a dry run just before recording, and record soon after.
3. **Reload before recording.**
   - Use Ctrl+Shift+R so the page has the latest JS.
   - Check that the run page shows the map, not a step list.
   - The map needs a window at least 900 px wide.
4. **Run lifetime.** Runs are deleted after 3 minutes idle, and closed tabs free their slot after 90 s. Don't leave the tab idle mid-take.
5. **Browser cleanup.**
   - Hide bookmarks and personal tabs.
   - Use a clean Chrome profile or full screen (F11).
   - The camera bubble must not cover the payees column (right side) or the replay bar (bottom right).

## Voice and honesty rules (from earlier feedback; still apply)
- **Natural spoken sentences.**
  - No robot fragments such as "First, the easiest attack. One email."
  - No hype words.
  - No "to be fair".
  - No exaggeration.
- **Harsimar's pace:** about 166 words per minute. A 2:45 talk is roughly 450 words of outline-worth speech.
- **No Claude/Anthropic attribution** in any commit or PR (global rule).

## Files to know
- `docs/PLAN.md`: original product plan and judging criteria.
- `README.md`, `FINDINGS.md`: the claims and their evidence.
- `docs/SPEAK.md` (v1): the voice the user liked for the old film. Copy its tone, not its content.
- `static/copy.js`: every string in the UI, if you need exact on-screen words.
- Old film work is reference only: `docs/SPEAK_V10.md`, `docs/FOOTAGE_V10.md`, `docs/VIDEO_V11_HANDOFF.md`.
