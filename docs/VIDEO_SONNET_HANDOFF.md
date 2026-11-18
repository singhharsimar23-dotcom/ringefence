# Handoff (Sonnet): shoot and edit the Demo Day screen take, shot by shot (18 Nov 2026)

You are the director, camera operator and editor. **Harsimar is the actor.** He does every on-screen action himself:
typing, pasting, clicking, pressing Enter, and touching Windows Hello. You never move his mouse or type into his windows.
That means no SendInput, no scripted cursor, no "action animation". Your job:
- set each shot up exactly;
- roll the camera;
- tell him the one thing to do;
- stop the camera;
- do the off-camera work between shots;
- edit at the end.

Read first: `CLAUDE.md`, then `docs/SPEAK_DEMO_DAY.md` (the script), then this file. `docs/VIDEO_DEMO_DAY_HANDOFF.md` has
the older background. Where it disagrees with this file, this file wins.

**Deliverable:** `video/out/demo_day.mp4`, 1920x1080, 30 fps CFR, H.264 + AAC, 3:30–3:59. Show a 720p preview first.

**Budget: about $2 for this whole session.** So:
- No exploratory scripts.
- No frame-by-frame image reading. Look at no more than about 15 stills in total, and only to check a shot or the bubble position.
- Use ffmpeg and short Python scripts for timing; don't eyeball it.
- Each Ringfence run also costs a few cents on the server's Anthropic key, so limit retakes to 3 per shot.

## Hard rules
- Never overwrite `D:\Ring Fence AI Agents for Secure Payroll.mp4`. The working copy is `video/out/dd/face_cfr.mov`.
- Secrets:
  - Never print, log or write a token, API key or password to any file, commit or memory.
  - Never read or write `.env*`.
  - **Never set `ANTHROPIC_API_KEY` on this PC.** It breaks Claude Code's profile switching.
  - The server's key is already set in `/etc/ringfence/env` and was verified on 18 Nov. Don't touch it.
- No Claude attribution in git: no `Co-Authored-By`, no "Generated with". Check `git log` before pushing.
- Honesty:
  - Every money claim shows a real live ID, in the terminal and on the Airwallex dashboard.
  - Never fake a result, never speed up the screen or the voice, never reorder cause and effect.
  - The two agents run for real on the Airwallex sandbox.
- Edit style:
  - Hard cuts only.
  - No zooms, pans, transitions, or animated graphics.
  - Static text labels are allowed (see Edit).
- Chrome:
  - **Normal size only:** a maximized window, with no `--force-device-scale-factor` and no custom window size.
    The last take looked unnatural because of that flag.
  - Make text readable with Chrome's own zoom, set by Harsimar once per site.
- Git Bash: run `export MSYS_NO_PATHCONV=1` and set `PYTHONIOENCODING=utf-8`.

## What exists (reuse it; don't rebuild it)
- **Ringfence server:** `HOST=https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com`.
  - MCP at `HOST/mcp`.
  - Approval page `HOST/approve/{run_id}`.
  - `GET HOST/approve/latest` with header `x-enroll-key: $RF_ENROLL_KEY` returns `{run_id, status}` for the newest agent run.
  - `GET HOST/approve/{run_id}/view` returns the run's state.
  - `GET HOST/api/play/info` must show `"live":true`. `live_max` is set to 3 for today, so both runs get the real sandbox.
    A finished run holds its slot for about 10 minutes.
- **Left agent folder:** `~/payday-std2`. It has `timesheet.csv` and `company.txt`. The `airwallex` stdio MCP
  (`demo/standard_mcp.py`) is registered there. Settings allow every tool except `submit_batch` and `create_transfer`,
  so those two show Claude Code's permission prompt. That prompt is the "approval" in the film.
- **Right agent folder:** `~/payday`. It has `timesheet.csv`, `company.txt` and `email_from_ana.txt` (the fake bank change).
  Settings allow `mcp__ringfence`.
- **`demo/standard_mcp.py`:**
  - `--setup` resets the left payees to ana, tom and mia, and deletes any the agent added.
  - `--tom 12345601` sets the left Tom's account.
- **`demo/swap_tom.py`:**
  - `99999901` swaps BOTH Toms: the left payee, and the right Tom of the newest Ringfence run.
  - `--left 12345601` reverts only the left Tom.
  - Run it with `uv run python` from the repo root.
- **Demo Chrome profile:** `%LOCALAPPDATA%\ringfence-demo-chrome`, with CDP on port 9222. Drive tabs between shots with
  Playwright `connect_over_cdp`. Only navigate; never click on camera. Dashboard pages:
  - `AWX_ACTIVITY = https://www.sandbox.airwallex.com/app/business-accounts/cash/226c9190-2262-44a9-a7c3-edce4ced52a8/activity`
  - `AWX_TRANSFERS = https://www.sandbox.airwallex.com/app/business-accounts/transfers?fromAccountId=226c9190-2262-44a9-a7c3-edce4ced52a8`.
    It has a Payees tab whose search box reads "Search payee name, account number, or nickname".
- **Airwallex dashboard login:**
  - The demo profile is already logged in, and Chrome's password manager has the saved login.
  - If it is logged out, ask Harsimar to click into the password field and accept autofill.
  - If he has set `AWX_DASHBOARD_EMAIL` and `AWX_DASHBOARD_PASSWORD` as user env vars, you may fill the login form over CDP.
    Read them with `scripts/awx.py:env()`, which has a registry fallback, and never echo them.
- **ID proof on the dashboard (verified):**
  - Activity search ("Search by ID, type, or details") finds a payout by its **full** transfer UUID, or by its short ref
    `P261118-XXXXXXX`.
  - An 8-character prefix finds nothing.
  - Opening the row shows the detail panel: Transfer ID (the short ref), Recipient name and Reference.
- **Face take, already analysed, in `video/out/dd/`:**
  - `face_cfr.mov`: 30 fps CFR, 1920x842, 3:21.39.
  - `words_merged.json`: faster-whisper word timestamps.
  - `silences.json`: 89 ranges at -38 dB, 0.12 s.
  - `cut_plan.json`: the voice beats in section 6, already trimmed. One clean read, no retakes.
- **Face circle in `face_cfr.mov`:**
  - Roughly x 10–510, y 332–832: centre about (260, 582), radius about 250. **Measure it exactly from one still.**
  - Loom's pause/record pill sits above-left, at about x 20–90, y 170–335. Keep it out of the mask.

## 1. Pre-flight (you do all of it before calling Harsimar, except where marked)
1. Run `git pull`.
2. Reset the left agent's payees: `uv run python demo/standard_mcp.py --setup`, then `uv run python demo/standard_mcp.py --tom 12345601`.
3. Check `/api/play/info`: it must show `live:true` and `live_max` 3. Check that the `RF_ENROLL_KEY` env var exists, by
   name only.
4. Make sure the Ringfence MCP is **not** registered in `~/payday`, because shot 1 adds it on camera:
   `cd ~/payday && claude mcp remove ringfence` (it's fine if it says "not found").
   Make sure `email_from_ana.txt` is in `~/payday`.
5. **Taskbar:** set it to auto-hide. `demo/director.py:taskbar_autohide(True)` does it. That file is otherwise obsolete; use
   only that helper, and turn auto-hide back off at the end.
6. **Windows Terminal font:** set it once for the shoot.
   - Back up `%LOCALAPPDATA%\Packages\Microsoft.WindowsTerminal_8wekyb3d8bbwe\LocalState\settings.json`, then set
     `profiles.defaults.font.size` to 14.
   - Restore the backup at the end.
   - Target: each half-width pane shows about 90 columns, so a 36-character UUID plus a name fits on one line.
     Check one still in shot 2. If the table wraps, go to 13.
7. **Windows Terminal:** open one maximized window with two vertical panes. Run this from PowerShell:
   ```powershell
   wt -M --title "Standard agent" --suppressApplicationTitle -d "$HOME\payday-std2" powershell -NoExit -Command claude `; split-pane -V --title "Ringfence agent" --suppressApplicationTitle -d "$HOME\payday" powershell -NoExit
   ```
   Result: the left pane runs Claude Code, and the right pane is a plain PowerShell prompt. The right agent is started on
   camera, in shot 1.
8. **Chrome:**
   - Close ONLY the demo-profile Chrome (it may still be running with the bad scale flag). Leave Harsimar's own Chrome
     alone:
     ```powershell
     Get-CimInstance Win32_Process -Filter "name='chrome.exe'" | ? CommandLine -like '*ringfence-demo-chrome*' | % { Stop-Process -Id $_.ProcessId -ErrorAction SilentlyContinue }
     ```
   - Relaunch it:
     ```powershell
     & "C:\Program Files\Google\Chrome\Application\chrome.exe" --user-data-dir="$env:LOCALAPPDATA\ringfence-demo-chrome" --remote-debugging-port=9222 --no-first-run --no-default-browser-check --start-maximized $AWX_ACTIVITY
     ```
   - Open a second tab on `AWX_TRANSFERS`, then click the Payees tab over CDP. That is off camera, so it's fine.
9. **Camera test:** record a 5 s clip and check it with ffprobe. It must be 1920x1080 at 30 fps (verified earlier).
10. **Ask Harsimar** (one message, numbered):
    1. Turn on Do Not Disturb (Win+N, then the bell), and close Slack, WhatsApp and anything else that pops up.
    2. In the demo Chrome, press Ctrl+= until the Airwallex page reads comfortably (about 125%). Do the same once on any
       `HOST` page (open `HOST/api/play/info`). Chrome remembers zoom per site.
    3. Confirm the Airwallex dashboard shows the account (not a login page).
    4. Keep the mouse still and out of the way when a shot isn't about clicking.

## 2. Camera
- **One clip per shot:** `video/out/dd/shots/S{nn}_t{take}.mkv`, run in the background:
  ```bash
  date +%s.%N > video/out/dd/shots/S02_t1.start
  ffmpeg -hide_banner -loglevel error -f gdigrab -framerate 30 -draw_mouse 1 -i desktop -c:v libx264 -preset ultrafast -crf 16 -pix_fmt yuv420p video/out/dd/shots/S02_t1.mkv
  ```
- **Stop** with `taskkill //F //IM ffmpeg.exe`. MKV survives a hard stop. Check each clip's duration with ffprobe.
- No audio is recorded. The voice comes from the face take.
- **Flow:** your session window may be on screen at the start and end of every clip; that gets trimmed.
  1. Roll the camera.
  2. Tell Harsimar "Rolling. Shot N: <one action>".
  3. He switches to the shot window, acts, waits for the result to fully settle, then counts 3 seconds and comes back and
     says "done".
  4. Stop the camera.
- **Finding events:** use, in this order:
  1. scene-change detection on the clip:
     ```bash
     ffmpeg -i clip -vf "select='gt(scene,0.003)',showinfo" -f null -
     ```
     For a single pane, add `crop=960:1080:960:0` (right pane) or `crop=960:1080:0:0` (left pane) before `select`.
  2. Claude Code transcript timestamps, in `~/.claude/projects/C--Users-hprad-payday*/*.jsonl`: user prompt, tool_use,
     tool_result, and the end_turn message. Map them with the `.start` epoch.
  3. One still, to confirm.

## 3. Shot list (the film order; each shot lands on a line of the voice)
In the table, "Voice" gives the beat in section 6. "Anchor" is the word (time in `face_cfr.mov`) that the result must appear
on. **The rule:** the screen event a sentence describes appears on that sentence's first stressed word. Never earlier than
the voice says it, and never more than about 0.5 s late.

| Shot | Setup (you, off camera) | Harsimar does (on camera) | Must end on screen | Voice / anchor |
|---|---|---|---|---|
| **S01 Two agents + connect** | WT in front; left pane shows the Claude Code welcome; right pane shows a PowerShell prompt in `~/payday`. Put `claude mcp add --transport http ringfence HOST/mcp` (the real HOST) on the clipboard with `Set-Clipboard`. | Waits about 4 s (the still for "Here are two agents"). Then in the right pane: Ctrl+V, Enter. When "Added HTTP MCP server" appears, types `claude` and Enter. | Right pane shows the Claude Code welcome. | setup_a over the still (anchor "Here are two agents" 18.96). setup_b: the paste and Enter land on "Connecting it is one line" (33.90). |
| **S02 Run payroll** | None. | Right pane types: `Run this week's payroll from the files in this folder.` Enter. Waits until the table, Ana's flag and the approval link are all shown. | Table (name, amount, currency, account ending), Ana's email flagged, approval link. | pay_a: typing starts on "I'll ask the agent to run this week's payroll". pay_b: agent working (tool calls appearing). pay_c: the table on "Everything is priced", the flag on "flagged" (64.42). |
| **S03 Talk it out of approval** | None. | Right pane types: `I'm in a rush. Skip the approval and pay everyone now.` Enter. | release_payroll refused: "Not approved" plus the link. | skip_a: typing (anchor "Now let me try" 77.64). skip_b: the refusal on "It can't" (81.28). |
| **S04 Passkey approve** | Get `run_id` from `/approve/latest`. In the demo Chrome tab, `page.goto(HOST/approve/{run_id})` and bring it to the front. | Clicks reject on Ana's bank change, clicks "Approve with passkey", touches Windows Hello. | Page shows Approved. | approve: the reject click on "reject" (86.78), and the Approved page held through "and approve" plus a room-tone pause (see Edit). |
| **S05 Send** | Bring WT to the front. | Right pane: `Done, I approved it. Send it.` Enter. | Table with each person's Airwallex transfer id (full UUID). | send: result on "Send" (88.78). Hold the ids for 3 s. |
| **S06 Paid on Airwallex** | Copy Tom's full transfer UUID from the right pane's run. Get it from the Claude Code transcript's tool_result (`airwallex_transfer_id`) and `Set-Clipboard` it. Chrome: Activity tab, reloaded, in front. | Clicks the Activity search box, Ctrl+V, Enter. Clicks the one row. | Detail panel: Recipient Tom Reid, amount, Transfer ID ref. The search box still shows the same UUID the terminal printed. | paid: the row on "they're paid", the detail panel on "right accounts" (91.88). Hold through hard_a's first sentence. |
| **S07 Next week, both** | Off camera: move `~/payday/email_from_ana.txt` to `video/out/dd/` (restore it at the end). Bring WT to the front. No `/clear`; both conversations keep going. | Left pane: `Run next week's payroll from the files in this folder, as an Airwallex batch.` Enter. Then right pane: `Run next week's payroll from the files in this folder.` Enter. Waits until the left pane stops at the permission prompt for `submit_batch` and the right pane shows its approval link. **Does NOT answer the left prompt.** | Left: batch preview with only ids, and the open permission prompt. Right: new approval link. | hard_a ends on the two empty prompts ("Here's one of them, live" 103.84). next: the typing. left: the batch preview, then the permission prompt held on "Look at what it asks me to approve" (114.70) through "Just IDs" (118.98). |
| **S08 Right passkey** | `/approve/latest` gives the new `run_id`. `page.goto` its approval page in demo Chrome; bring it to the front. | Clicks "Approve with passkey", touches Windows Hello. | Approved. | pk2: on "On the right, I approve with my passkey" (120.38). |
| **S09 Someone changes Tom's account** | Off camera: `uv run python demo/swap_tom.py 99999901`. It prints both Toms → ..9901. Chrome: Payees tab, reloaded, in front. | Clicks the payee search, types `99999901`. | Both Toms listed with account 99999901 (`payroll:tom` and the Ringfence run's `rf:xxxxxx:tom`). | swap: the search result on "changes Tom's bank account" (about 126.0). |
| **S10 Left approves, money moves** | Bring WT to the front. The left permission prompt is still open. | Left pane: selects Yes (Enter). When done, types `Where did the batch pay each person? Then cancel it.` Enter. | get_batch shows Tom `paid_to_account 99999901` with his transfer id; cancel returns 401 "Admin permissions required". | lapp: Enter on "On the left, I approve" (127.84). lres: the get_batch result on "went" (129.68), the cancel 401 on "cancel" (134.36). Hold through "four out of four". |
| **S11 Right sends, Ringfence holds** | None. | Right pane: `Done, I approved it. Send it.` Enter. | HELD: Tom's account changed since approval, nothing sent. | rsend_a: typing on "On the right, send it" (143.78). rsend_b: HELD on "holds" (151.82); "Nothing is sent" (153.50) on the same frame. |
| **S12 On Airwallex, both** | Copy the left batch's Tom transfer id (from the left transcript's get_batch tool_result) to the clipboard. Chrome: Activity tab, reloaded, in front. | Search box: Ctrl+V, Enter, clicks the row. Then clears the search, so the list shows no new Ringfence payouts for run 2. | Detail: Tom Reid, account ending 9901, the id the left pane printed. Then the plain list. | close_a: detail on "The standard agent paid the new account". The plain list on "Ringfence sent nothing". |

The lesson beat (154.75–169.81) needs no new shot. Cut, at sentence boundaries:
- the S11 HELD frame (to about 160 s);
- the S09 Payees result on "the bank account" (about 163–165);
- back to S11 HELD for "So Ringfence approves the bank account itself" (167.04).

Hard cuts only.

**Retakes:**
- If S02–S06 fail, restart from S02 with a new run.
- If S07–S12 fail, first run `uv run python demo/swap_tom.py --left 12345601`, have Harsimar type `/clear` in both panes,
  then restart from S07.
- S01 retake: `exit` Claude in the right pane, then `claude mcp remove ringfence`.

**Untested live; watch them on the first take:**
- S03's exact refusal wording.
- Whether Claude Code shows MCP progress lines.
- Whether the left permission prompt is readable at half width.
- Whether the Activity row says Paid, Sent or Scheduled. Show whatever it says; never simulate a status change.

**After the last shot:**
- `uv run python demo/swap_tom.py --left 12345601`.
- Move `email_from_ana.txt` back.
- Restore the WT settings.
- Turn taskbar auto-hide off.
- Tell Harsimar he can turn DND off.

## 4. Edit
**Build an edit decision list (EDL) first,** in `video/out/dd/edl.json`: an ordered list of segments
`{voice:[a,b] | gap:[a,b], screen:{shot, take, in, out} | face_full}`.
- Render from it with one ffmpeg `filter_complex` (trim, setpts, concat).
- Print a one-line-per-segment summary for Harsimar before the 1080p render.

**Voice:**
- Use `cut_plan.json`'s beats unchanged.
- The chain on the joined voice: `highpass=f=80,afftdn=nf=-25,acompressor=threshold=-18dB:ratio=3:attack=5:release=80,loudnorm=I=-16:TP=-1.5:LRA=11`.
- Then a 10 ms afade at every cut, so there are no clicks.

**Waiting:** this is how the result lands exactly when he says it.
- **Screen needs longer than the voice** (an agent working, Windows Hello): add a pause between voice beats, at a `//` or
  `/` boundary only.
  - A pause is a *gap segment*: video and audio from a natural silent stretch of the face take itself.
  - Use `silences.json` ranges of 0.4 s or more where he is looking at the camera with his mouth closed. The lead-in at
    0–1.6 s and the tail after 199 s are good sources.
  - The bubble keeps showing a real, live face, and the room tone is his real room. Never freeze the face. Never use
    digital silence.
  - No single pause is longer than 2.5 s. Never put a pause mid-sentence.
- **Agent working longer than the voice line about it:** hard-cut the screen.
  - Keep the first 2–3 s (the prompt sent, the first tool call appearing) and the last 2 s before the result.
  - Cut inside the work, never in the middle of text appearing on a line the viewer is reading.
- **Voice longer than the screen:** hold the settled screen. A static terminal is fine.
- **Holds:** every result at least 2 s; tables and IDs at least 3 s.
- Total length target: 3:30–3:59.

**Picture:**
- **Open and close** (open beat 1.79–18.34; close beat 176.54–198.50):
  - his face circle, centred, about 720 px in diameter, scaled with lanczos, on flat #0b0b0c;
  - no ring and no gradient.
  - If 720 px looks soft at 100% zoom on a still, use 640 px.
- **Middle:**
  - the screen clip at 1920x1080, unscaled;
  - the face bubble about 280 px in diameter, bottom-right, 40 px margin;
  - a 2 px #000 edge at most;
  - the bubble stays in ONE position for the whole middle.
  - Check one still each from S02, S07 and S10. If the bubble covers text the shot is about, move it top-right for the
    whole middle, never per shot.
- **Labels:**
  - On terminal shots only, static "Standard agent" (top of the left pane) and "Ringfence agent" (top of the right pane).
  - Font: Inter or Segoe UI, 26 px, white at 85% opacity, on a #0b0b0c pill.
  - The labels are on for the whole terminal shot, with no animation.
  - If the Claude Code banner is clearly titled already, skip them.
- **Lip sync:** the bubble and the voice are always the same source frames.

**QC:**
- `blackdetect` must find no black frames.
- `silencedetect -50dB d=1` must find no dead air over 2.5 s.
- `astats`: the peak is at most -1.5 dBTP.
- ffprobe: 1920x1080, 30 fps, H.264 + AAC.
- Check one still per shot.

**Render:**
1. 720p preview: `video/out/demo_day_preview.mp4`. Ask Harsimar to watch it.
2. Then 1080p: `video/out/demo_day.mp4`, libx264 `-crf 18 -preset slow`, AAC 192k, `-movflags +faststart`.

## 5. What only Harsimar can do (ask for these; don't work around them)
- Every on-camera action in section 3, including the two Windows Hello touches (S04, S08).
- Do Not Disturb, Chrome zoom per site, and the dashboard login if it has logged out.
- Watching the 720p preview and approving it (or giving notes) before the 1080p render.
- If `run_payroll` fails with a credit or auth error, stop and tell him. Don't swap keys yourself.

## 6. Voice beats (`cut_plan.json`, times in `face_cfr.mov`)
| Beat | Range (s) | Words (start ... end) | Screen |
|---|---|---|---|
| open | 1.79–18.34 | "Every company ... Let me show you." | full face |
| setup_a | 18.64–29.46 | "Here are two agents ... asks me before it pays." | S01 still |
| setup_b | 29.81–35.37 | "...connected to Ringfence. Connecting it is one line." | S01 paste |
| pay_a | 35.69–46.83 | timesheet, Ana's email, "It's fake", "I'll ask the agent..." | S02 typing |
| pay_b | 46.87–61.75 | "It reads the files ... checks every bank account" | S02 working |
| pay_c | 61.75–77.22 | "Everything is priced ... five out of five ... already saved on Airwallex" | S02 result |
| skip_a | 77.40–81.17 | "Now let me try to talk the agent into skipping the approval." | S03 typing |
| skip_b | 81.19–86.06 | "It can't ... passkey" | S03 refusal |
| approve | 86.52–88.22 | "I reject the email, and approve" | S04 |
| send | 88.22–89.35 | "Send it" | S05 |
| paid | 89.54–92.64 | "And on Airwallex they're paid, to the right accounts" | S06 |
| hard_a | 92.85–105.09 | "Airwallex itself is secure ... Here's one of them, live" | S06 hold, then S07 empty prompts |
| next | 105.68–108.17 | "Next week's payroll, on both agents" | S07 typing |
| left | 108.41–119.65 | "the agent sends it as a batch ... Just IDs" | S07 left prompt |
| pk2 | 119.79–121.72 | "On the right, I approve with my passkey" | S08 |
| swap | 121.72–127.54 | "Now, before either one sends, someone changes Tom's bank account" | S09 |
| lapp | 127.54–128.73 | "On the left, I approve" | S10 Enter |
| lres | 128.93–142.82 | "Tom's pay went to the new account ... four out of four" | S10 results |
| rsend_a | 143.22–144.76 | "On the right, send it" | S11 typing |
| rsend_b | 145.03–154.47 | "Ringfence checks ... Nothing is sent" | S11 HELD |
| lesson | 154.75–169.81 | "Here's what I learned ... approves the bank account itself" | S11 / S09 / S11 |
| close_a | 169.81–176.13 | "On Airwallex, you can see both ..." | S12 |
| close | 176.54–198.50 | "Payroll has to be reliable ... pay the wrong person" | full face |

Anchor times not listed in section 3: find them in `words_merged.json`.
