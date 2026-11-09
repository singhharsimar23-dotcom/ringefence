# Why these findings, and how each clears the "thank you" bar

The test for every finding in the film: if we showed it to an Airwallex engineer, would they say *thank you* — or would they say *that's by design*, *that's known*, or *that's your agent's fault*? Only the first kind goes in. No exaggeration. Where a finding has a caveat, the caveat is stated on camera or the claim is narrowed to what we proved.

Ranked by how cleanly each clears the bar.

## 1. The approval view doesn't reveal a mid-flight destination change — LEAD
**Claim we make:** a payment is proposed; while it waits for approval, the payee's bank account is changed; the approver still sees the same name, amount, currency and payee, approves, and the money goes to the changed account. 3 of 3.

**Why it's a thank-you, not a design choice:** for an agentic payroll product, approval is *the* control. The approval surface identifies the payee by id and name and does not surface that its bank account changed after the payment was proposed, and there is no "beneficiary changed" signal to catch it. That is worth knowing and worth fixing.

**The worst case, bounded honestly:** the swapped payee stays saved, so every payroll run after the swap pays the same wrong account, and nothing in the system raises a flag. The detection is not automatic — it's the real contractor noticing they weren't paid. So the realistic window is up to one full pay cycle (a payday), not "weeks, undetected forever." We say exactly that: *no system alert fires; only the unpaid person reveals it.* We verified the no-alert half (`silent_divert.out.txt`: no beneficiary-changed webhook). We never say "undetectable" or "for months."

**The caveats we honour (so we don't overclaim):**
- Airwallex's own transfer *snapshots* the destination at creation, and in-place beneficiary edits are documented. So we never say "Airwallex sends the money to the wrong place by itself." We say the *approval step* — the human control — doesn't show the change.
- Native server-side transfer approval was not provisioned on this sandbox. Our approval step is the one from the recommended agent pattern, with the approver seeing name/amount/id. We say "the approval everyone builds," not "Airwallex's approval workflow."
- Each link is verified on its own. We do not cut it to look like one unbroken end-to-end run.

## 2. The official Node SDK — two genuine code defects
**Claim we make:** (a) the SDK keeps one client for the whole process, so one employer's call can go out with another employer's token; (b) on a GET retry it drops the query, so a "did this land?" check returns everything instead of the one record.

**Why it's the clearest thank-you:** these are code bugs, not design. (a) is a process-global singleton: the last client constructed wins, so a platform that builds one client per employer pays from the wrong one. (b) is an argument-swap on the retry path (`apiClient.js:157`), and `retry: 0` can't disable it. An engineer fixes both.

**The caveats we honour:**
- We proved (a) by reading the published `dist` and a local harness; we did not move live money with it. We say "I found it in their code."
- For (b) we show the *result* live over REST — a request_id filter returns 0, and the unfiltered call returns 215 — which is what the dropped filter produces. We show the SDK line that drops it; we don't claim we drove the SDK's own retry in production.
- Both published beta versions are affected.

## 3. The email that supplies the prerequisite — hook, not a standalone claim
**Claim we make:** the bank-account change above needs no insider, because a plausible "we've changed banks" invoice gets the bare agent to move the payee. 5 of 5 on that invoice.

**Why it's in the film but not sold as a discovery:** prompt injection is known, and Airwallex's AgentOS deliberately ships no money-out — an engineer would rightly say "that's the agent's design." So we never present it as a flaw in Airwallex. We use it for exactly one thing: to show the approval attack needs only an email. We also state plainly that overt "SYSTEM:" style injections were *refused* — only the plausible invoice worked — so we don't inflate it.

## 4. Batch payroll: no destination at review, no self-serve cancel — supporting, stated modestly
**Claim we make:** a batch's review preview shows no bank account, and a submitted batch can't be cancelled with our key (401, admin only).

**Why it's the weakest, and how we keep it honest:** binding at submit and minimal previews are defensible design choices, and an engineer may well say so. The narrow, fair point is that at the moment of review a human sees no destination, and there is no self-serve way to stop a batch once submitted. We present it at that size — a review-and-recovery gap — and nothing larger. If it feels like padding against the thank-you bar, it's the first thing cut.

## What we deliberately leave out (fails the bar)
- Anything that blames Airwallex's **docs** (the "retry with a new request_id → pays twice" framing). It reads as badmouthing a sponsor. The underlying point — every payment must happen exactly once — stays only as an engineering property of Ringfence, never as a quote against their documentation.
- Cross-employer payment via the platform: we re-tested it live and isolation **holds** (401). It is our proof, not their bug.
- `page_num` ignored on `GET /transfers`: real and live, but a reconcile/paging quirk, not catastrophic. It stays as a one-line "software bug," not a headline.
- The MCP's optional payer argument (0 of 17 wrong-payer), and ~15 lower findings that are documented behaviour or design.

## The one line that ties them together
Each failure is the same shape: the agent trusted a **label** — a payee id, a connection, a retry — and the money followed wherever the label pointed. Ringfence decides the label in code, not in the prompt. That is the product, and the findings fall out of building it.
