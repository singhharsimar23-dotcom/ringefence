# What you say

One Loom on the landing page: Screen + Camera, medium bubble bottom left, 1080p. Save as `var/loom.mp4`.
Talk it like you're showing a friend something you're proud of. If you fumble, pause and redo that paragraph; Claude cuts the bad take.
About 4:50 with the pauses. If you run long, don't rush: Claude tightens silences in the edit.

## How to read the marks

| Mark | What you do |
|---|---|
| **bold** | Lean on that word. Louder or slower, not both. |
| `/` | A tiny beat, half a second. Like a comma, but you actually stop. |
| `//` | A real pause, one full second. Let it land. |
| *(italic)* | How to say the next part. |
| new line | New thought. Take a breath if you need one. |

The rule: **slow down on numbers and on the last words of a section.** Speed up on lists and stories. Monotone comes from every sentence having the same speed, so change it on purpose.

---

## 1 · Open
*(warm, smile, look at the camera)*

Hi, I'm [name], / and I built **Ringfence**.

*(conversational, like explaining to a friend)*

Some companies run payroll / for **lots** of other companies.
Every Friday, they're holding **millions** of dollars / that **aren't theirs**.
And it goes wrong in **two** ways. //
*(count them off)*
One client's money / pays **another** client's staff. /
Or someone emails, *(casual voice)* "hey, I changed banks," / and the salary goes to a **scammer**. //

Now give that job / to an **AI agent**.
*(slower)* My first question was: / how do I make sure it **never** pays the **wrong person**? //

So here's what I did. / The agent **suggests**. / My code **decides**. / And every client gets its **own** Airwallex account. //

---

## 2 · The demo
*(lighter, quicker, you're showing it off)*

Let me show you.
I've got three clients: / Northwind, / Kestrel, / and Harbour Foods.
I hit **run**, / and the agent reads all their timesheets and emails.

Kestrel had a normal week, / so it just **pays** them.
Those are **real** Airwallex transfers. /
Northwind changed some pay rates, / and I don't want an AI approving that **on its own**, / so it **waits** for their finance person. //

*(lean in a little)*
Harbour / is the interesting one.
They don't have enough **Australian dollars**.
So instead of **guessing**, / the agent works out **exactly** what's missing, / and asks Harbour to top up / **before** the deadline. //

*(a bit sly)*
And here's a **trap** / I set on purpose.
**Fifty thousand dollars** lands in **Kestrel's** account / while Harbour is waiting.
A lazy system would just **use** it. /
*(firm, slower)* But that's **Kestrel's** money. / So mine **won't touch it**. //

---

## 3 · Metal
*(drop your voice, slower, this is the serious part)*

So how does Harbour get funded? /
Honestly, / this is the part I'm **proudest** of. //

You probably saw **Binance** last week.
*(slow)* Over **six billion dollars**. / **Gone**. //
It started with a **fake job interview**, / and ended with attackers **inside** the system that signs Binance's wallet transactions.
Once they were in, / the money just kept **flowing** / for almost **four hours**. //

*(look at the camera)*
So I asked myself: / what if the **wallet itself** had a limit / that **no stolen key** could get around? //

*(pick the pace back up)*
That's what I built on **Metal**.
Harbour keeps stablecoins there, / and signs a rule onto the blockchain.
*(count these off, one by one)*
We can take **one** payment. / For **exactly** what's missing. / Only into **our** account. / And only for the **next hour**. //

I press the button, / and it pulls **exactly** that.
A **real** transaction, / on Metal's testnet. //

*(playful)*
Then I tried to **cheat**.
I asked for **one coin more**, / and the blockchain **refused**. /
Then I tried a **fake wallet** / that looks almost **identical** to the real one.
My code catches it, / and the blockchain refuses it **anyway**. //

*(slow, to the camera, every word)*
Even if someone stole my keys **tomorrow**, / the most they could ever take / is that **one payment**, / into our **own** account. //
Not **six billion**. / Not **one coin more**. //

*(release, lighter)*
The money lands, / Harbour signs off, / and everyone's **paid**.
*(slow)* Not **one cent** / went where it shouldn't. //

---

## 4 · Proof and the engineers
*(confident, matter-of-fact)*

This is the **real** Airwallex dashboard. / **Four** separate accounts, / the **same** transfer IDs as my app.
I even tried one client's login / on **another** client's account, / and Airwallex **blocked** me. //

*(shift gear, a bit faster, peer to peer)*
Quick one for the **engineers**. / **Four** decisions matter. //

**One.** / The model is **never** trusted.
It writes a **proposal**; / deterministic code prices every line / and **decides**.
So the safety doesn't depend on the model, / *(small smile)* and I'll **prove** that in a second. //

**Two.** / Client money is **never pooled**, / not even in a **calculation**.
Each client has its **own** Airwallex credentials, / so the isolation is enforced by **Airwallex**, / not by a filter in my code. //

**Three.** / **Exactly once**, / under failure.
The payment ID is fixed **before** the first attempt.
If a reply times out, / I **never** resend. / I **look it up**.
And nothing is **final** / until it reconciles with Airwallex, / because a payment can **bounce back** / after it's marked paid. //

**Four.** / A bank change from an email / **never** takes effect.
The old details **stay**, / and a **different person** has to confirm it / **by phone**.
And an approval signs a **hash** of the exact batch, / so nothing can be **swapped** / between sign-off and release. //

It all runs as an **MCP server**, / with **no** approve tool.
*(slow)* A **human** / always signs. //

---

## 5 · Break it
*(build energy, getting faster from here to the end)*

Then I tried **really hard** / to **break** it. //

I built a test agent that does **whatever it's told**, / and threw **twenty-eight** attacks at it.
It fell for **all twenty-eight**, / and still didn't send **one dollar** to the wrong place. /
*(beat)* **Claude** / didn't fall for **one**. //

I fired **twenty** payments at once, on the **live** sandbox, / and cut off some of the replies.
Everyone still got paid / **exactly once**. //

*(fast, punchy, one number per breath)*
I tampered with the records **two hundred** times. / Caught **all two hundred**. /
**Five hundred** random runs. /
**Four hundred and twenty** tests. //

*(stop, half smile, slower)*
I think you get the point. //

---

## 6 · Close
*(relaxed, to the camera)*

But don't take my word for it.
The demo's **live**. / Paste in your **own** payroll, / or let it **attack itself**. //

*(slow, calm, no sell)*
So, / back to my first question: / how do I make sure an AI agent / **never** pays the wrong person? //
*(beat, then simply)*
**That's** Ringfence. //
Thanks for watching.
