# Ringfence demo — the plan (simple language)

The word-for-word script is `docs/SPEAK_V5.md`. This is the shorter map of *why it's shaped that way*, so you
don't drift into a bug report on the take. Same tone as V5: a builder showing a friend what he made. Not a
researcher reading a defect list.

**The one rule for tone:** we **brag about what we built**, and the finding falls out of the bragging. We never
"present bugs." The order is product → the gap we noticed while building it → the control that closes it. If a
line sounds like "here is vulnerability number three," cut it.

**The story in one line:** "I built the thing that moves the money safely. Building it, I noticed where everyone
else leaks. So I closed it. Watch."

---

## The arc (what goes where, and why)

**First, the product — most of the time. (~2:25)**
Three companies, three accounts, one run. Kestrel pays for real. Northwind waits for a human and shows what
changed. Harbour is short and says exactly how much and by when. Then the twist: $50k lands in Kestrel's account
and we **don't** touch it for Harbour. Harbour funds itself, gets paid. Real dashboard, same IDs, cross-login
blocked, tamper turns the proof red.

This is the brag. It's live, it's specific, the money is real in the sandbox. Numbers slow and clear.

**Then, the thing I noticed. (~1:00) — abstract, not a catalogue.**
Not "I found bugs." It's one honest thought: *a payroll agent's whole job is reading mail, and the usual way of
building one treats the AI's judgement as the safety.* Show it once — a plain agent, built the normal way, pays a
fake "our bank details changed" invoice one time in five. Good model. But "usually" is not a control.

Then the deeper one, still abstract: add a human to approve — and the money can still leave correctly-approved and
land in the wrong place, because **the approval reads a label and the money follows what that label points to.**
Right name, right amount, a human said yes, wrong account. Three times out of three. Every piece of that is
reasonable on its own. Nobody owns the gap between them. That's the whole finding, in one sentence — don't turn it
into a list.

**Then, the control closes it. (~0:30)**
Same invoice, my agent: the bank change is quarantined until a different person confirms by phone. Same edit
mid-approval: I approve the account, not the label — it changed, so it's held, nothing moves. And fair to
Airwallex: the walls between accounts held every time; amount, payer and FX were all bound. The findings went to
their team first.

**Close.** The agent suggests. My code decides. That's Ringfence.

---

## Lines that keep it a brag, not a bug report
- Say **"the gap,"** "where the money leaks," "what I noticed" — never "vulnerability," "exploit," "bug #."
- Lead every finding with the product reason it matters, then the finding — never the other way round.
- The hero finding is **one sentence**: *the check reads a label, the money follows what it points to.* Resist
  listing the fifteen. They flash on screen for two seconds; you say "each with a receipt."
- Keep it humble where it's honest: "once in five," "a good model," "to be fair to Airwallex, the walls held."
  The humility is what makes the brag land.

## Rules while recording (don't skip)
- Live, in the sandbox, small amounts (GBP/EUR 5 or less). Cancel every transfer and delete every test payee after.
- Pre-record the shaky parts and play them in: anything with a short settle window, and the "who's unpaid" count
  (live numbers have grown).
- One line only on the deeper research: "fifteen findings, each with a receipt, and Airwallex has them first."

## Before you hit record
1. Send the private findings note (`docs/DISCLOSURE_AIRWALLEX.md`) — fill in the date and contact first. Line 8b
   of the script is only said if it's sent.
2. One full dry run of the app, start to finish, so the product screens all load.
3. Re-check the Binance figure and date, and the "1 of 5" / "3 of 3" numbers on a fresh run, before you say them.
