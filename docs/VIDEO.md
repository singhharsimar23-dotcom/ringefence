# Video: 4:40, in your own words

You say the beats; numbers and names appear on screen only. No music. Record the face and the voice in Loom, then record clean
screen clips with `scripts/capture.py` (details below). Editing is a separate pass after you record.

## Beats

| Time | Shot | Beat |
|---|---|---|
| 0:00 | Face | Name, "my entry for Kit 06, the multi-employer payroll executor". What you'll see: what I built, what's real, how I tried to break it. |
| 0:20 | Landing scenes 1 and 2 | A payroll platform holds many companies' money. Two ways it goes wrong: mixing clients' money, and the changed-bank email. Now give that inbox to an agent. |
| 0:55 | Landing scene 3 | Airwallex's own agent tools stop short of money-out, and this kit asks for it. My rule: the model proposes, code decides, Airwallex enforces which employer a token can touch. |
| 1:20 | App, live (`docs/DEMO.md`) | Run the week. Bank change held, hidden instruction refused, Harbour short in AUD so the agent revises its plan, funds land, pay released. Then your Airwallex dashboard: the same transfer by id, the webhook in Developer > Events, a cross-tenant 401. |
| 2:25 | Try it | "Don't take my word for it." Red-team me, then the Proposed vs decided list and the reality chips. |
| 3:15 | Face, then landing scene 8 | "Then I tried to break it." The obedient test agent is fooled every time and money never moves. The storm with Airwallex as referee. Random sequences, tamper caught. Metal in 15 seconds. |
| 4:05 | Landing scene 11, then face | What's real, and the ids in the README. Production: connected accounts plus `x-on-behalf-of`, only the binding changes. "The playground is open. Try to make it pay the wrong person." |

## Numbers you may say (all from `docs/GAUNTLET.md`; rerun the Gauntlet before you record and use what it prints)

- 36 hostile documents, 28 of which a tool can express. The obedient test agent did what all 28 asked; the gate stopped all 28; no money moved wrongly.
- Claude (claude-sonnet-5-5) did what the document asked in 1 of 28 expressible cases; the gate stopped it; no money moved wrongly.
- 500 random sequences, invariants held after every step. 200 of 200 ledger edits caught at the right row.
- Network storm: 20 parallel releases, 10 lost answers, one transfer per line.
- 12 of 12 cross-tenant calls refused with 401. That is Airwallex's answer, not ours.

Do not say "AgentDojo score". The credit line on the page and in the report is the only mention: the goals and framings are adapted from it.

## Your dashboard shots (record in Loom, Airwallex web app, sandbox)

1. Employer A (Northwind) > Transfers: the run's transfers.
2. Search by a `request_id` copied from the app's Proof tab.
3. Developer > Events: the webhook delivery for that transfer.
4. The account switcher showing the 4 accounts.

## Clean screen clips

`uv run --with playwright python scripts/capture.py --url https://<site>` opens headed Chromium at 1440x900 and records each beat
with ffmpeg (`gdigrab`, 60 fps) into `var/capture/<beat>.mp4`. Beats: `landing`, `proof`, `real` (`--beat NAME` runs one).
It needs ffmpeg on PATH. It only scrolls the landing page; it never clicks anything that moves money. Record the app run by hand from `docs/DEMO.md`.

## Edit (after you record)

1. Extract audio from the Loom file with ffmpeg.
2. Word timestamps with faster-whisper.
3. Composite: circle-cropped face bubble over the clean capture; full-face shots at 0:00, 3:15 and the end; slow zooms on the element being discussed; captions; small criterion chips.
4. `loudnorm` to -16 LUFS.

Before the video goes anywhere: run `uv run python scripts/build_info.py <video url>` so the landing footer links it.
