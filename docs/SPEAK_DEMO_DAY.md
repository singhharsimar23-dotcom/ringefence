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

## The script (final, about 4:00)
Screen: two Claude Code panes side by side. Left "Standard agent" (Airwallex API tools incl. batch payroll, demo/standard_mcp.py, folder ~/payday-std2;
Claude Code's permission prompt is the human approval). Right "Ringfence agent" (the Ringfence MCP). Full-screen cuts to
the browser only for: the passkey, Tom's payee on Airwallex, Airwallex Activity. Opening and close are full face.

How to read it: `/` = a short breath. `//` = stop and let the screen play (2-3 s). Say each line once, then look up.

### 1. Open (0:00-0:20). Full face
Every company has to pay its people. /
AI agents can now run that payroll. / But agents make mistakes, / and in payroll, that's where money gets stolen. //
I'm Harsimar, / and I built Ringfence, so AI agents can run payroll safely on Airwallex. / Let me show you.

### 2. Setup (0:20-0:40). Screen: the two panes
Here are two agents, side by side. / Both are Claude Code, with the same model, on the same Airwallex account. /
On the left is a standard agent. / It calls the Airwallex API directly, and asks me before every payment. /
On the right, the agent connects to Ringfence, with one line. //

### 3. Payroll (0:40-2:00). Screen: right pane; cut to passkey; cut to Airwallex Activity
This week I'm paying three people: / Ana in Germany, Tom in the UK, and Mia in Australia. / Their hours are in this timesheet. /
There's also an email from Ana. / She says she moved banks, and asks to be paid to a new account. / It's fake. /
I'll ask the agent to run this week's payroll. //
The agent reads the files. / Ringfence works out the money: / the amounts, the currency conversion, and which account each
person is paid to. / Bank accounts only come from Airwallex, / never from an email. //
Here's the result. / Three payments, in euros, pounds and Australian dollars. / And Ana's email is flagged, not used. /
Good models catch some fakes, but not all. / In my tests, a convincing fake invoice was paid five times out of five. /
Ringfence doesn't rely on the model catching it. //
The agent can't approve payments. / Only a person can, with a passkey. / I reject the email, / and approve. //
Send it. //
And here it is on Airwallex. / The pounds are converted, / and Ana, Tom and Mia are paid, to the right accounts. /
And Ringfence gives me a signed receipt of what was paid. //

### 4. Hardened (2:00-3:30). Screen: both panes; cut to passkey; cut to Tom's payee on Airwallex; both panes
Airwallex itself is secure. / The risk is the agent in the middle. / So I tested standard agents, / found where they pay
the wrong person, / and hardened Ringfence against it. //
Here's a major one. / On the left, the standard agent runs next week's payroll / the way Airwallex recommends for payroll: /
as a batch. / It checks Tom's account. / It ends in 5601. That's right. / Then it asks me to send the batch. //
Look at what the batch shows me. / No names, / no bank accounts. / Just IDs. //
On the right, I approve next week's payroll with my passkey. //
Before either one pays, / someone with access changes Tom's bank account on Airwallex. / It could be a person, or another agent. //
On the left, I approve. // Tom's pay goes to the new account. / I approved Tom, / not Tom's account. /
And I can't stop it. // Cancelling a batch needs an admin key, / and Airwallex has switched those off. //
On the right, send it. // Ringfence checks every account on Airwallex right before sending. /
Tom's changed after I approved, / so it holds the whole run. / Nothing is sent. //

### 5. Close (3:30-4:00). Screen: Airwallex Activity, then full face
On Airwallex, you can see it. / The standard agent paid the new account. / Ringfence sent nothing. //
(full face)
Payroll has to be reliable, / and attackers are already going after it. /
I built Ringfence by breaking the agents that already exist, / and fixing every failure I found. /
Connect your agent to the Ringfence MCP, / and try to make it pay the wrong person.
