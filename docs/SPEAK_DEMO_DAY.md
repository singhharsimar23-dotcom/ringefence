# Demo Day script, final (about 4:00)

## What the organisers asked for
- 3 to 4 minutes, max. 2 to 3 is ideal.
- Intro under 30 seconds. Show the product within 30 to 45 seconds.
- The real product, not slides. One relatable use case, end to end. For dev tools, show real commands and outputs.
- Show a before and after.
- Don't jump between lots of windows. Don't explain features you don't show.
- Face in a bubble, at eye level. 1080p or better, clear audio.
- Sound natural: "let me show you", say what you're doing, pause so people can read. Don't read word for word.
- Structure: 0:00-0:30 the problem and who you are. 0:30-3:00 the demo. 3:00-3:30 the result, with a number.
  3:30-4:00 what's next and how to try it.
- Clear and natural beats polished. Get to the point and let the product speak.
- V1 goes to Dan Kim on Slack for feedback.

## The script (final, 3:30)
Screen: two Claude Code panes side by side. Left "Standard agent" (plain Airwallex API tools, batch payroll included;
Claude Code's permission prompt is the approval). Right "Ringfence agent" (the Ringfence MCP). Full-screen browser cuts only
for: the passkey, Tom's payee on Airwallex, Airwallex Activity. Opening and close are full face.

Recorded separately: the face take is read straight through; the screen take is recorded live and cut to the voice in the edit.
`/` = a short breath. `//` = a longer pause (a cut point in the edit). About 450 words, 3:30 at a calm pace.

### 1. Open (0:00-0:25). Full face
Every company has to pay its people. /
AI agents can now run that payroll. / But agents make mistakes, / and in payroll, that's where money gets stolen. //
I'm Harsimar, / and I built Ringfence, so AI agents can run payroll safely on Airwallex. / Let me show you.

### 2. Setup (0:25-0:45). Both panes
Here are two agents, side by side. / Same model, / same Airwallex account. /
On the left is a standard agent. / It uses the Airwallex API directly, and asks me before it pays. /
On the right is the same agent, connected to Ringfence. / Connecting it is one line. //

### 3. Payroll (0:45-1:55). Right pane, then passkey, then Airwallex
This week's hours are in this timesheet. / There's also an email from Ana, asking to be paid to a new bank account. / It's fake. /
I'll ask the agent to run this week's payroll. //
It reads the files and hands them to Ringfence. / Ringfence opens the company's own Airwallex account, /
works out each person's pay, / prices the currency conversion, / and checks every bank account against what's saved on Airwallex. //
Everyone is priced, / and Ana's email is flagged, not used. /
In my tests, agents paid a fake invoice five times out of five. /
Ringfence doesn't rely on the model catching it. / It only pays accounts already saved on Airwallex. //
The agent can't approve payments, / and it can't skip the approval. / Only I can approve, with my passkey. /
I reject the email, / and approve. //
Send it. //
And on Airwallex, / they're paid, / to the right accounts. //

### 4. Hardened (1:55-3:00). Both panes, passkey, Tom's payee
Airwallex itself is secure. / The risk is the agent in the middle. /
So I tested standard agents, / found where they pay the wrong person, / and hardened Ringfence against it. /
Here's a second bug, live. //
Next week's payroll, on both agents. //
On the left, the agent sends it as a batch, / the way Airwallex recommends for payroll. /
Look at what it asks me to approve. / No names, / no bank accounts. / Just IDs. //
On the right, I approve with my passkey. //
Now, before either one sends, / someone changes Tom's bank account on Airwallex. //
On the left, I approve. // Tom's pay went to the new account. /
I approved Tom, / not his account. / And I can't cancel it. / That needs an admin key, / and Airwallex has switched those off. //
On the right, send it. // Ringfence checks every account again, right before sending. /
Tom's changed since I approved, / so it holds the whole run. / Nothing is sent. //

### 5. Close (3:00-3:30). Airwallex, then full face
On Airwallex, you can see both. / The standard agent paid the new account. / Ringfence sent nothing. //
(full face)
Payroll has to be reliable, / and attackers are already going after it. /
I built Ringfence by breaking the agents that already exist, / and fixing every failure I found. /
Connect your agent to the Ringfence MCP, / and try to make it pay the wrong person.
