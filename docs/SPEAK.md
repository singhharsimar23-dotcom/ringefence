# What you say

One Loom on the landing page: Screen + Camera, medium bubble bottom left, 1080p. Talk it like you're showing a friend.
A blank line is a breath. If you fumble, pause and redo that paragraph. Change any word that doesn't sound like you. Save as `var/loom.mp4`.

---

Hi, I'm [name], and I built Ringfence.

So there are companies that run payroll for lots of other companies at once. Which means every Friday they're sitting on millions of dollars, and none of it is theirs.

When they get it wrong, it's usually one of two things. One client's money ends up paying another client's staff. Or someone emails saying "hey, I changed banks," and the salary goes straight to a scammer.

Now give that job to an AI agent. The first thing I asked myself was: how do I make sure it can never pay the wrong person?

So here's what I did. The agent reads everything and suggests what to pay, but it doesn't get the final say. My code checks every payment before anything moves. And every client has its own Airwallex account, so Airwallex itself keeps them apart.

Let me show you. I've got three clients: Northwind, Kestrel and Harbour Foods. I hit run, and the agent reads all their timesheets and emails.

Kestrel had a normal week, so it just pays them. Those are real Airwallex transfers. Northwind changed some pay rates, and I don't want an AI approving that on its own, so it waits for their finance person.

Harbour is the interesting one. They don't have enough Australian dollars. So instead of guessing, the agent works out exactly what's missing and asks Harbour to top up before the deadline.

And here's a trap I set on purpose. Fifty thousand dollars lands in Kestrel's account while Harbour is waiting. A lazy system would just use it. But that's Kestrel's money, so mine won't touch it.

So how does Harbour get funded? Honestly, this is the part I'm proudest of.

Harbour keeps stablecoins on Metal. And I had Harbour sign a rule onto the blockchain: we can take one payment, for exactly what's missing, and only into our account.

I press the button, and it pulls exactly that. That's a real transaction, you can open it on Metal's testnet.

Then I tried to cheat. I asked for one coin more, and the blockchain refused. Then I tried a scam people are falling for right now, a fake wallet that looks almost identical to the real one. My code catches it, and the blockchain refuses it anyway.

That's the point. Even if my code had a bug, the blockchain still won't let one extra coin out. It's a second lock I don't even control.

So the money lands, Harbour signs off, and everyone gets paid. Three companies, and not one cent went where it shouldn't.

And this isn't a mock-up. This is the real Airwallex dashboard. Four separate accounts, the same transfer IDs from my app. I even tried using one client's login on another client's account, and Airwallex blocked me.

But I didn't just want to say it's safe. So I tried really hard to break it.

I built a test agent that does whatever it's told, and threw twenty-eight attacks at it. It fell for all twenty-eight, and still didn't send a single dollar to the wrong place, because my code said no every time. Claude didn't fall for one.

I fired twenty payments at once on the live sandbox and cut off some of the replies. Everyone still got paid exactly once.

I tampered with the records two hundred times. Caught all two hundred. Five hundred random runs, four hundred and twenty tests. Not one rule broken.

But don't take my word for it. The demo's live. Paste in your own payroll, or let it attack itself.

This is Ringfence. An AI that runs payroll for lots of companies, and can't pay the wrong person.
