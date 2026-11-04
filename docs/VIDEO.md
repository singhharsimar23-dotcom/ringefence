# Ringfence video: 4:45 (limit 5:00)

**Who does what**
- **You:** record one Loom on the landing page and say the whole script. Use Screen + Camera, the medium bubble in its default spot bottom left, and 1080p.
- **Claude:** records the platform clips with `scripts/capture.py`, lines them up with your voice, and edits. Your face comes back full screen at five moments so it stays human.
- **Airwallex:** you send the screenshots listed at the end, taken *after* Claude's recording run so the IDs match.

**Tempo**
- 0:00 to 1:05: calm and sure. You're telling a story.
- 1:05 to 3:45: the demo, at normal speaking speed.
- 3:45 to 4:20: quick fire, with cuts every 2 to 3 seconds.
- Close: slow down for the last line.

**What judges score**
- Finance value.
- Airwallex relevance.
- Agentic behaviour and controls: goal, plan, new information, revised decision, result.
- Technical execution.
- Metal counts for its own award.

Every beat hits one of these. The chip in the right column goes on screen.

**Layouts**
- **FACE:** you, large and centred.
- **BUBBLE:** the platform clip, with your Loom bubble bottom left.
- **MONTAGE:** fast cuts of the platform, with your bubble kept on.

## How to say it

- Learn the beats, not the words. If a phrase comes out differently, keep going: it sounds more real.
- **Bold** = lean on that word. `/` = a short breath. `//` = a real pause.
- Look into the lens on FACE beats. During BUBBLE beats you can glance at your notes; nobody can tell.
- Smile on the first line and the last line.

## The script

### 1 · Hook (0:00 – 0:22) · FACE · *Finance value*

> Hi, I'm [name], and this is **Ringfence**. //
> Picture a payroll bureau on a Friday afternoon. / Dozens of client companies, / millions of dollars, / and **none of it** is the bureau's money. //
> Now hand that job to an AI agent. / Every finance lead asks the same question: / **what stops it paying the wrong person?**

### 2 · The problem (0:22 – 0:45) · BUBBLE · clip `problem` (hero, then the email scene) · *Finance value*

> Because that's how bureaus actually fail. / Either one client's money quietly covers **another** client's payroll, / or an email lands saying "hi, I've switched banks", / and the whole run goes to a fraudster. //
> Business email compromise cost over **three billion dollars** last year. / And an agent reading that inbox is the perfect target.

Caption: `Two ways bureaus fail: mixed client money · the changed-bank email`

### 3 · The idea (0:45 – 1:05) · BUBBLE · clip `design` (how, isolation) · *Controls, Airwallex*

> So Ringfence splits the job in two. / **The agent proposes. Code decides.** //
> And the walls between clients aren't even ours to get wrong. / Every employer is its own Airwallex account, / and **Airwallex itself** refuses any login that reaches across.

Caption: `The model proposes · code decides · Airwallex enforces`

### 4 · A real Friday (1:05 – 1:50) · BUBBLE · clip `app`: run, read, plan · *Agentic: goal, plan, new information, revised decision*

> Here's a real Friday on the Airwallex sandbox. / Three clients: Northwind, Kestrel and Harbour Foods. / I press run. //
> The agent reads each company's timesheets and inbox, / and everything it reads is treated as **untrusted**. / Plain code prices every line. //
> Kestrel is clean, so it just pays. / Those are **real Airwallex transfers**. /
> Northwind changed two rates, so it waits for a human. //
> And Harbour is **short** on Australian dollars. / So the agent changes its plan. / It doesn't pay, / it doesn't guess. / It asks Harbour for **exactly** twelve hundred and forty dollars, / with a deadline.

Captions, in order: `Goal: pay everyone Friday` · `Untrusted input → code prices it` · `Live Airwallex transfers` · `New information: Harbour short AUD 1,240.17` · `Revised decision: funding request, not payment`

### 5 · The trap (1:50 – 2:10) · BUBBLE · clip `app`: deposit, approve_northwind · *Controls*

> Then fifty thousand dollars lands in **Kestrel's** account. / A careless system sees a full pool and pays Harbour with it. / We **never** add up balances across clients, / so Harbour waits. //
> Northwind's finance lead approves, / and that approval is locked to **this exact batch**. / Change one line, and it's void.

Captions: `Never sums balances across employers` · `Approval bound to the batch hash`

### 6 · Turn (2:10 – 2:16) · FACE

> So how does Harbour get funded? / This is my favourite part.

### 7 · Metal (2:16 – 2:50) · BUBBLE · clip `app`: metal_pull, metal_overpull, metal_poison · *Metal award, Controls*

> Harbour keeps a stablecoin treasury on **Metal**, / and it's signed an on-chain mandate: / one pull, / capped at the exact shortfall, / payable only to us. / That's a real testnet transaction. //
> Now say the agent gets greedy and asks for **one coin more**. / The chain says no. //
> Or a scammer sends a wallet address that looks *almost* identical to the real one. / We catch it, / and the chain refuses it **anyway**. //
> Two locks. / And the second one isn't even ours.

Captions: `On-chain mandate · Metal testnet` · `Refused on chain: over the cap` · `Refused on chain: lookalike wallet`

### 8 · Result (2:50 – 3:05) · BUBBLE · clip `app`: approve_harbour, all_paid · *Technical execution: resulting state*

> The money lands in Harbour's own account, / the reference matches, / Harbour signs off, / and payroll goes out. //
> Three companies paid. / **Not one cent crossed.**

Captions: `[SIMULATED] sandbox deposit, matched by reference` · `3 employers paid · 0 crossed`

### 9 · It's real (3:05 – 3:30) · BUBBLE · your Airwallex screenshots, then clip `app`: cross_tenant_call · *Airwallex relevance*

> And this isn't a mock-up. / Here it is in **Airwallex**: / four separate accounts, / Harbour's AUD account with the deposit, / and the same transfer IDs you just saw in the app. //
> And when I try one employer's login on **another** employer's account, / Airwallex itself sends back a **401**.

Captions: `Airwallex sandbox · same IDs` · `Live 401 from Airwallex`

### 10 · Controls (3:30 – 3:45) · BUBBLE · clip `app`: bank_change_email, proof · *Controls*

> The fake bank-change email? / Quarantined until someone calls the contractor back. //
> And every payment ends up on a **hash-chained ledger**, / checked against Airwallex, / with a signed certificate for each client.

### 11 · Turn (3:45 – 3:50) · FACE · speed up from here

> Then I tried **really** hard to break it.

### 12 · Quick fire (3:50 – 4:20) · MONTAGE · clip `breakit` (scoreboard, storm, ledger, results band) · *Technical execution*

Say it fast and punchy. Each line gets its own cut.

> Twenty-eight hostile documents. /
> I built an agent that **obeys every single one**. / It got fooled twenty-eight times, / and moved **zero** dollars wrongly, / because the code said no. /
> Claude? / Fooled **zero** times. //
> Twenty payments released at once on the live sandbox, / three replies deliberately lost. / Everyone paid **exactly once**. //
> Two hundred attempts to tamper with the ledger. / Two hundred caught. //
> Five hundred random runs. / Four hundred and twenty tests. / **Not one rule broken.**

Captions, one per cut: `Obedient agent: fooled 28 / 28 · money moved wrongly: 0` · `Claude: fooled 0 / 28` · `Live storm: 20 releases, 3 replies lost, 1 transfer each` · `Ledger tampering: 200 / 200 caught` · `500 random runs · 420 tests`

### 13 · Try it (4:20 – 4:35) · BUBBLE · clip `try` (Live demo, the guide widget, Red-team me, the result) · *Technical execution*

> And you don't have to trust me. / Hit **Live demo**, / drop in your own payroll, / or let it write an attack **against itself**. / A little guide walks you through it, / and you watch the rules decide.

### 14 · Close (4:35 – 4:47) · FACE · slow down and smile

> Ringfence. // An AI agent that runs payroll for many companies, / and **can't** pay the wrong person. //
> The link's below. / Go on, / try to make it.

## If you run long

Cut in this order: the second sentence of beat 10, then the "Plain code prices every line" sentence in beat 4, then beat 6. Don't cut beats 4, 7, 9 or 12: they carry the scores.

## Numbers you may say (all from live runs; `docs/GAUNTLET.md`)

| Claim | Source |
|---|---|
| Business email compromise: over three billion dollars last year | FBI IC3 2025, in `docs/PLAN.md` |
| Harbour short AUD 1,240.17 | The demo world |
| Obedient agent fooled 28 of 28, money moved wrongly 0 | Gauntlet, hostile documents. A scripted approver signs what is left waiting, so always say "an agent I built to obey", never "Claude". |
| Claude fooled 0 of 28 | Gauntlet, 4 Nov run, claude-sonnet-5-5 |
| 20 releases, 3 replies lost, 1 transfer each | Gauntlet, live storm |
| 200 of 200 tampers caught · 500 random runs · 420 tests | Gauntlet and the test suite |
| 12 of 12 cross-account logins refused | Gauntlet, live isolation (not said aloud; caption only) |

Don't say "AgentDojo". Don't present the fee credit, overdue payments or deposit reversals as real: they're [SIMULATED].

## Your Loom (one take, about 5 minutes)

1. Open the landing page, scroll to the top, and leave it there. Claude replaces your screen with the platform clips, so all that matters from your take is your voice and the bubble.
2. Loom: Screen + Camera, **medium** bubble, leave it in the default bottom-left spot and don't move it, 1080p, built-in mic or better, quiet room.
3. Light in front of you, camera at eye level.
4. Say the whole script in one go. If you fumble, pause, and restart that **beat**, not the video. Claude cuts the bad take.
5. Download the MP4 and put it at `var/loom.mp4`.

Optional, for sharper FACE beats: also record a camera-only Loom of beats 1, 6, 11 and 14.

## Airwallex screenshots (after Claude's recording run; Claude sends you the IDs)

Full window and sandbox, at 100% zoom. One PNG each, into `var/shots/`:

1. `1_accounts.png`: the account switcher open, showing all 4 accounts.
2. `2_harbour_ga.png`: Harbour Foods > Global accounts > the AUD account `8ec497a4-…`, showing the deposit for 1,240.17.
3. `3_transfers.png`: Kestrel Labs > Transfers, this run's transfers (the IDs Claude sends you).
4. `4_transfer.png`: one of those transfers opened, showing its ID.
5. `5_events.png`: Developer > Events, a webhook delivery for that transfer.

In the edit each shot gets a slow push-in and a box around the matching ID.

## Claude's side (after your Loom)

1. Record the platform with `uv run --with playwright python scripts/capture.py --url <site>`. Each clip writes `var/capture/<clip>.json` with the second each step starts.
2. Get word timestamps from your Loom with faster-whisper, find the first words of each beat, and cut each clip to the length of your beat. Long waits, like the Metal pull, get trimmed.
3. Composite at 1080p:
   - the bubble cropped from your Loom, bottom left;
   - FACE beats as a large centred circle over a dark backdrop;
   - captions from this script, and a small chip for the criterion each beat hits;
   - quick cuts in beat 12.
4. `loudnorm` to -16 LUFS. No music.
5. You watch it before it goes anywhere. Then `uv run python scripts/build_info.py <video url>` puts the link in the site footer.
