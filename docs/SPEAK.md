# What you say

One Loom on the landing page: Screen + Camera, medium bubble bottom left, 1080p. Talk it like you're showing a friend.
A blank line is a breath. If you fumble, pause and redo that paragraph. Change any word that doesn't sound like you. Save as `var/loom.mp4`.
At a steady pace this runs about 4:50. If your take runs past 4:55, Claude trims the pauses; don't rush.

---

Hi, I'm [name], and I built Ringfence.

Some companies run payroll for lots of other companies. Every Friday they're holding millions of dollars that aren't theirs. And it goes wrong in two ways: one client's money pays another client's staff, or someone emails "hey, I changed banks," and the salary goes to a scammer.

Now give that job to an AI agent. My first question was: how do I make sure it never pays the wrong person?

So here's what I did: the agent suggests, my code decides, and every client gets its own Airwallex account.

Let me show you. I've got three clients: Northwind, Kestrel and Harbour Foods. I hit run, and the agent reads all their timesheets and emails.

Kestrel had a normal week, so it just pays them. Those are real Airwallex transfers. Northwind changed some pay rates, and I don't want an AI approving that on its own, so it waits for their finance person.

Harbour is the interesting one. They don't have enough Australian dollars. So instead of guessing, the agent works out exactly what's missing and asks Harbour to top up before the deadline.

And here's a trap I set on purpose. Fifty thousand dollars lands in Kestrel's account while Harbour is waiting. A lazy system would just use it. But that's Kestrel's money, so mine won't touch it.

So how does Harbour get funded? Honestly, this is the part I'm proudest of.

You probably saw Binance last week. Over six billion dollars, gone. It started with a fake job interview, and ended with attackers inside the system that signs Binance's wallet transactions. Once they were in, the money just kept flowing for almost four hours.

So I asked myself: what if the wallet itself had a limit that no stolen key could get around?

That's what I built on Metal. Harbour keeps stablecoins there, and signs a rule onto the blockchain: we can take one payment, for exactly what's missing, only into our account, and only for the next hour.

I press the button, and it pulls exactly that. A real transaction on Metal's testnet.

Then I tried to cheat. I asked for one coin more, and the blockchain refused. Then I tried a fake wallet that looks almost identical to the real one. My code catches it, and the blockchain refuses it anyway.

Even if someone stole my keys tomorrow, the most they could ever take is that one payment, into our own account. Not six billion. Not one coin more.

The money lands, Harbour signs off, and everyone's paid. Not one cent went where it shouldn't.

This is the real Airwallex dashboard: four separate accounts, the same transfer IDs as my app. I even tried one client's login on another client's account, and Airwallex blocked me.

Quick one for the engineers. Four decisions matter.

One: the model is never trusted. It writes a proposal; deterministic code prices every line and decides. So the safety doesn't depend on the model, and I'll prove that in a second.

Two: client money is never pooled, not even in a calculation. Each client has its own Airwallex credentials, so the isolation is enforced by Airwallex, not by a filter in my code.

Three: exactly-once under failure. The payment ID is fixed before the first attempt. If a reply times out, I never resend; I look it up. And nothing is final until it reconciles with Airwallex, because a payment can bounce back after it's marked paid.

Four: a bank change from an email never takes effect. The old details stay, and a different person has to confirm it by phone. And an approval signs a hash of the exact batch, so nothing can be swapped between sign-off and release.

It all runs as an MCP server with no approve tool. A human always signs.

Then I tried really hard to break it.

I built a test agent that does whatever it's told, and threw twenty-eight attacks at it. It fell for all twenty-eight, and still didn't send one dollar to the wrong place. Claude didn't fall for one.

I fired twenty payments at once on the live sandbox and cut off some of the replies. Everyone still got paid exactly once.

I tampered with the records two hundred times. Caught all two hundred. Five hundred random runs. Four hundred and twenty tests.

I think you get the point.

But don't take my word for it. The demo's live. Paste in your own payroll, or let it attack itself.

This is Ringfence. An AI that runs payroll for lots of companies, and can't pay the wrong person.
