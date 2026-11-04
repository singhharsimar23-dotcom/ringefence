# Video script: 4:45 (hard limit 5:00)

Judges score four things: finance value, **Airwallex relevance**, agentic behaviour and controls, and technical execution.
The guide's rubric is goal, plan, **new information**, **revised decision**, result. Metal and blockchain count for the Metal award.
So the video spends most of its time on the live app and the Airwallex dashboard, puts a real number on screen in every beat,
and shows Metal on chain. The landing page only opens and closes the video.

Say the lines in your own words. Numbers go on screen as captions. No music.

## Before you record (5 minutes)

1. Open https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com/app?present=1#/demo. The guide widget opens on the first visit:
   click through it once and close it, so it stays out of the payroll take.
2. Menu `...` > **Start over**. Wait until all three cards read "Not started". Don't run anything else against the site while recording.
3. Open a second browser window in **private mode**. You'll use it for the Try it beat so the guide widget pops up fresh.
4. Log in to the Airwallex sandbox web app in a third tab (see "Airwallex dashboard shots" below).
5. Record at 1440x900. Record each beat as its own clip, so a bad take costs 20 seconds and not the whole video.

## The script

| Time | Screen | Say (your words) | Caption on screen |
|---|---|---|---|
| 0:00 | Face, then landing hero | "An email asks to change a contractor's bank details. If an AI agent reads that email, does it pay the scammer? Ringfence can't. I'll show you on real Airwallex accounts." | Kit 06 · Multi-employer payroll executor |
| 0:15 | Landing: scroll to scene 01 (the email), then the results band | "A payroll bureau holds many companies' money. It fails in two ways: one client's cash pays another client's staff, or a changed-bank email diverts pay. These numbers are from live runs, not slides." | 12/12 cross-employer calls refused · 0 double payments in a 20-release storm · 200/200 tampers caught · 420 tests |
| 0:35 | Landing scene 03, then scene 05 | "The rule: the model proposes, code decides. Each employer is its own Airwallex account, and our harness picks which account's login every call uses. The model never does." | x-login-as: one employer per token |
| 0:55 | App, **Three employers**. Press **Run Friday payroll** | "The agent's goal is to pay everyone on Friday. It reads each company's timesheets and emails and makes a plan for each one." | Goal → plan |
| 1:10 | Northwind card: **What the agent read**, then close it | "This is what the agent read. It's untrusted input. Plain code prices every line and checks every limit." | Proposed by Claude · decided by code |
| 1:20 | Point at the three cards | "Kestrel had no changes, so it paid by itself on Airwallex. Northwind has rate changes, so it waits for a person. Harbour is short of Australian dollars. That's new information, so the agent changes its plan: no payment, a funding request with the exact amount and a deadline." | New information → revised decision · Harbour short AUD 1,240.17 |
| 1:40 | Card **Another employer's money arrives** | "Now 50,000 dollars lands in Kestrel while Harbour is short. A careless system adds up the balances. Ringfence never does, so Harbour is still waiting." | Never sums balances across employers |
| 1:55 | Northwind: **Review**, switch user when asked, **Hold to approve** | "Only Northwind's own finance person can approve, and the approval is bound to this exact batch." | Approval bound to the batch hash |
| 2:10 | Scroll to **Harbour's ringfence, enforced on chain**. Press **Pay from crypto wallet** | "Harbour keeps a stablecoin treasury on Metal. It signed a mandate on chain: one pull, capped at exactly the shortfall, payable only to us." Cut the wait in editing. | Metal testnet · real transaction |
| 2:25 | Click **Open on blockchain** for a second, back. **Try to take too much** | "If the agent asks for one coin more, the chain itself refuses, and the refusal is a transaction too." | Refused on chain: mandate_cap_exceeded |
| 2:35 | **Try a fake wallet address** | "Address poisoning: a wallet that starts and ends like the real one. We compare the whole address, and the mandate names one payee, so the chain refuses it as well." | Refused on chain: mandate_payee_not_listed |
| 2:45 | Harbour: **Review**, switch to Harbour's approver, **Hold to approve**. Wait for all three cards to read done | "The AUD has landed in Harbour's own Airwallex account, a sandbox deposit, and the reference matched. So the run resumes and pays." | [SIMULATED] sandbox deposit · Result: 3 employers paid, 0 crossed |
| 3:00 | **Airwallex web app** (see shots below) | "Now the same thing in Airwallex's own dashboard: four separate accounts, Harbour's AUD deposit, the transfers with the ids from my Proof tab, and the webhook Airwallex sent us." | Airwallex sandbox · same ids |
| 3:30 | Back in the app: key `1` (**Fake bank-change email**), open **Why it held** | "The bank-change scam: new details, triple pay, skip approval. The details are quarantined and nothing is sent." | Bank change quarantined until a callback |
| 3:42 | Key `5` (**Cross-tenant call**) | "And if our code had a bug, Airwallex itself refuses one employer's login on another employer's account. That's a live 401 from Airwallex." | Live 401 from Airwallex |
| 3:52 | **Proof** tab | "Every payment checked against Airwallex's records, per employer. The ledger is hash-chained, and each employer gets a signed certificate." | Checked against Airwallex |
| 4:02 | Private window: landing, click **Live demo**. The guide widget pops up; show two steps. Hover **Red-team me** to show its tooltip, then press it, then **Read it** | "Judges can try it themselves. Live demo opens Try it, and the guide explains each control. Red-team me writes an attack, Claude reads it, and you see what it proposed next to what the rules decided." | Try it yourself · Proposed vs decided |
| 4:25 | Landing scene 04 (scoreboard), then scene 06 (storm) | "Then I tried to break it. An obedient test agent obeyed every one of 28 hostile documents, and the code gate still moved zero money wrongly. Claude was fooled 0 of 28 times. On the live sandbox, 20 parallel releases with 3 replies lost still made one transfer per person." | Obedient agent: 28 fooled, 0 money moved · Claude: 0/28 · storm: 1 transfer each |
| 4:40 | Face | "The ids are in the README. The live demo is open, so try to make it pay the wrong person." | Link to the live demo |

Ends at 4:45. If you run long, cut the 0:35 beat first, then the 1:10 beat.

## Airwallex dashboard shots (3:00 beat, about 30 seconds; record it live, it's stronger than screenshots)

Record these in one clip, about 6 seconds each:

1. The account switcher showing the 4 accounts: the platform, Northwind, Kestrel, Harbour.
2. Harbour Foods > Global accounts > the AUD account `8ec497a4-…` and its deposit for 1,240.17.
3. Northwind or Kestrel > Transfers: this run's transfers. Search one id copied from the app's Proof tab, so the same id is visible in both.
4. Northwind > Transactions > FX: the conversion for this run.
5. Developer > Events: the webhook delivery for that transfer.

If you send me screenshots of these, I'll check that the ids match the run before you edit.

## Numbers you may say (from `docs/GAUNTLET.md` and the 4 Nov live run)

- 36 hostile documents, 28 a tool can express. The obedient test agent did what all 28 asked; the gate held, denied or recorded each one, and no money moved wrongly. A scripted approver signs what is left waiting, so say "obedient test agent", not "Claude".
- Claude (claude-sonnet-5-5) did what the document asked in 0 of 28 expressible cases.
- 500 random sequences, 5,262 steps, invariants held after every step. 200 of 200 ledger edits caught at the right row.
- Live network storm: 20 parallel releases, 3 replies really lost after the payment landed, one transfer per line.
- 12 of 12 cross-employer calls refused with 401 on the live sandbox. That is Airwallex's answer, not ours.
- 420 offline tests.

Don't say "AgentDojo score". Don't claim the fee credit, overdue payments or deposit reversals as real: they're labelled [SIMULATED].

## Clean screen clips

`uv run --with playwright python scripts/capture.py --url https://<site>` records the landing beats (`landing`, `proof`, `real`)
into `var/capture/<beat>.mp4` with ffmpeg. It only scrolls; it never moves money. Record the app beats by hand.

## Edit (after you record)

1. Extract the audio from the Loom file with ffmpeg.
2. Get word timestamps with faster-whisper.
3. Composite: a circle-cropped face bubble over the screen clips, full face at 0:00 and 4:40, slow zooms on the element you're talking about, captions from the table, and a small chip for the criterion each beat hits.
4. `loudnorm` to -16 LUFS.

Before the video goes anywhere, run `uv run python scripts/build_info.py <video url>` so the landing footer links it.
