# Ringfence: product plan (3 Nov 2026)

Sources: three research passes (hackathon intent, payroll market, agent-payment safety) plus live sandbox recon (see CLAUDE.md).

## 1. What the judges score
From Dan Kim's launch article (Airwallex):
1. **Finance value.** An important finance problem for a clear user.
2. **Airwallex relevance.** Airwallex performs a meaningful financial action, and financial context shapes that action.
3. **Agentic behaviour and controls.** The agent picks the next step, acts within permissions, and handles approvals and exceptions.
4. **Technical execution.** A reliable end-to-end workflow with a clear resulting financial state.

The guide's demo rubric is: user goal → initial plan → **new information** → **revised decision** → resulting balance or status. "Using more tools does not earn you more points." Jack Zhang frames agentic banking as: observe → decide → act within rules → reconcile.

Prizes: $30k Founder's Choice (Jack Zhang) and $20k Judges' Choice. The Visa and Metal awards need their tools, which fit payroll poorly, so we skip them.

**Deadline risk.** HackerEarth says submissions close **13 Nov**. Slack says 15 Nov. We plan to submit on 13 Nov and treat 15 Nov as buffer.

## 2. The problem, from each point of view
- **Payroll platform operator (our user).** Runs weekly contractor pay for many employers. The money belongs to the employers, not the operator. Commingling is how bureaus fail:
  - PayServ: $7.8M shortfall (2026).
  - Payroll Professionals Inc.: paid one client's taxes with another client's money.
  - An Ontario court split a pooled payroll account pro rata among its clients.
  - UK CASS 7.13 requires segregation.
- **Employer.** Wants to know exactly how much to fund and by when, including FX and fees. Wants no surprises.
- **Contractor.** Being paid late or wrong costs trust. In one survey, 49% would start job-hunting after two pay errors, and some laws punish even a one-day delay (Massachusetts treble damages; Australian wage theft is now a crime).
- **Finance and security.** Payroll diversion is the classic BEC attack: an email asks to "change my bank details". BEC losses were $3.05B in 2025, and about 86% moved by wire or ACH. The standard controls are a callback on bank changes, maker-checker, and separating beneficiary edits from payment release.
- **Airwallex.** AgentOS ships with **no money-out by default** because it lacks a trustworthy control layer. Platforms (HR, EOR, payroll) are their embedded-finance customers. They want proof that an agent can move platform money safely. That is literally the Kit 6 brief: "the platform can technically execute that transfer; policy must stop it."

## 3. Market gap
| Player | What exists | What's missing |
|---|---|---|
| Deel / Rippling / Papaya | AI anomaly detection, staged runs for human approval | Per-employer funds enforcement, funding deadline forecasts |
| Ramp / Brex | Policy agents for spend | Payroll payouts, multi-tenant funds |
| Stripe Treasury for agents | Two-party approval on `send_money` | A generic per-account rule, not per-tenant payroll |
| Airwallex AgentOS | MCP and skills, no money-out | The control layer that would make money-out safe |

Nobody ships an **agent that moves multi-tenant payroll money with deterministic, provable segregation**. That is our wedge.

## 4. The product, in one line
**Ringfence: a payroll agent for platforms that can move every employer's money and can prove it never moved one employer's money for another.**

### Core mechanics
Each mechanic maps to a criterion.

1. **Hard tenant binding (C3, C4).** The harness, never the model, picks which employer token each call uses (Airwallex enforces it: a cross-tenant token returns 401). The policy also blocks the one cross-tenant path the platform *can* execute: an employer paying into another tenant's own account.
2. **Per-employer mandate (C3).** Based on AP2's open mandate. It sets a per-run cap, a per-contractor cap, an allowed payee list, currencies and an expiry, and it is HMAC-signed. A **closed approval** is bound to the hash of the exact batch, so approving batch A can't authorise a modified batch B.
3. **Pricing and the "act-by" forecast (C1, C2).** For each employer, using its own wallet only:
   - net pay + SWIFT fees (EUR 12.85 flat, added *before* the FX conversion) + platform fee;
   - an FX quote;
   - shortfall = need − own available.

   Output: "Harbour Foods is short AUD 1,240.17. Fund by 09:00 Thu (cutoff) or contractors are paid late." Financial context drives the decision.
4. **Deterministic policy gate (C3).** The LLM proposes and the gate decides. The gate checks the mandate, own-wallet funding, the beneficiary allow-list, the amount recomputed in code, and schema and argument validation. Every rejection has a reason code that goes in the ledger.
5. **Beneficiary-change quarantine (C1, C3).** Bank-detail changes found in emails or invoices (untrusted input) never take effect directly. They are quarantined until an out-of-band callback is confirmed in the UI. This defends against payroll diversion, and it is our prompt-injection demo.
6. **Exactly-once payouts (C4).**
   - request_id = hash(run, employer, contractor, amount, currency).
   - The intent is written to the ledger *before* the call.
   - On a timeout, the payout is marked UNKNOWN and we retry with the same id. Airwallex's `duplicate_request_id` error returns `details.id`, so we can recover the original (verified live).
7. **Exception handling (C3).** On a late failure after PAID (a bank return), the agent reopens that one line, notifies the contractor, and re-pays only after a fresh approval.
8. **Fee collection (C2).** The platform fee is taken from each employer's own wallet, which works live. The platform-side credit is labelled `[SIMULATED]` because the sandbox doesn't credit internal transfers.
9. **Proof (C4).**
   - A hash-chained, append-only ledger with an HMAC run digest stored separately.
   - A `verify` command that catches a tampered row.
   - A **non-LLM isolation report**: it re-reads every account's transfers from Airwallex and proves that every debit belongs to that employer's run.

### The agent's actual job
This is the "agentic" part, and the model owns it.
- Read untrusted inputs: timesheets, contractor emails, invoices.
- Draft each employer's run.
- Notice new information, such as deposits, failures and bank-change requests, and re-plan.
- Choose the next step: pay, hold, escalate, or ask for funding.
- Write plain-English explanations for the employer and the operator.

The tools are typed and narrow, and nothing like a raw "transfer" tool exists without the gate. Model: Claude Sonnet 5.5 via the Anthropic SDK (upgrade from 0.40).

## 4b. Innovation layer
To make the cut, an idea must pass three tests:
- A judge understands it in 10 seconds.
- A payroll operator would actually use it on a Friday.
- We found nobody doing it.

### Base features, each with a twist
| Kit requirement | Plain version | Our twist |
|---|---|---|
| Price payroll | Total = pay + fees | **Act-by countdown per employer and rail.** For example: "Fund AUD 1,240.17 by Thu 09:00 or 4 contractors are paid late." |
| FX conversion | Convert the whole amount | Convert only **that employer's own shortfall** in each currency. The approval is bound to a **rate band** (±0.5%). If the rate moves outside it, we re-ask. |
| Create beneficiaries | Create from input | Any bank change from an email or invoice is **quarantined** until a callback is confirmed. The first payout to new bank details is capped. |
| Pay | Call `transfers/create` | **Exactly-once.** A deterministic id; the intent is logged first; a timeout becomes UNKNOWN and is reconciled, never paid twice. |
| Handle shortfall | Stop and report | **Self-matching funding request.** The agent sends the employer *its own* Airwallex global account details plus a unique reference. When a deposit with that reference lands, it is matched to the run and the run resumes by itself. |
| Collect fee | Charge each employer | The fee applies **only to payouts that actually landed**. A returned payment automatically refunds its fee line. |
| Isolation | Trust the code | A **segregation certificate** per employer and run (see below). |

### New things, beyond the kit
1. **Lanes UI.** Each employer is a sealed lane, and money visibly flows only inside its lane to its contractors. Above the lanes, the "naive total across all employers" is shown crossed out in red next to each employer's true figure. The whole Kit 6 idea fits in one picture.
2. **Approval as a diff.** The approve screen shows *what changed since last run*: a new contractor, a rate change (+20%), new bank details, an FX move. It is not a wall of rows. Payroll operators already work this way, it counters approval fatigue (OWASP ASI09), and the approval is bound to the batch hash.
3. **Rules in plain English, compiled to hard limits.** The employer types "never pay anyone over £5k a week, GBP and EUR only". The agent compiles it into a structured mandate and shows a readable card, and the employer signs that card. **Before signing, a replay against the last runs shows what the rule would have blocked.** The LLM writes the draft, but code enforces the signed structure.
4. **"Try to break it" panel.** Judges click the attacks themselves:
   - a fake bank-change email;
   - a double-click on pay;
   - a network drop mid-payout;
   - an edited ledger row;
   - a cross-tenant call.

   Each one shows the defence live, with its ledger entry. It reuses the scenario engine, and it works on demo day.
5. **Segregation certificate.** After each run, every employer gets a one-page signed statement listing every debit and payee, with the ledger digest. Anyone can check it with `python -m ringfence.verify cert.json`, so auditors and employers don't need to trust us. It answers the segregation question that brought down commingled bureaus.

6. **Ringfence as an MCP server.** Expose our gated tools (`price_run`, `propose_payroll`, `approve`, `status`, `certificate`) over MCP. An operator can then run payroll from Claude Code or Claude Desktop, right next to Airwallex's own AgentOS tools. Pitch: *"AgentOS has no money-out by default. Ringfence is the control layer that makes money-out safe."* This plugs straight into Airwallex's own strategy.
7. **Webhooks instead of polling.** When a deposit or a transfer status changes, the agent reacts within seconds. A real event drives the "new information → revised decision" beat, not a loop. This needs a public URL: a tunnel during development, and the deployed app at the end.
8. **Public live link.** Judges open a URL and press the "try to break it" buttons themselves, rather than only watching the video.
9. **Contractor "track my pay" page.** Shows each payout as approved → sent → paid → returned, with an ETA. It cuts "where's my money" tickets, and a bank return tells the contractor how to fix their details through the verified flow.

**Competitor reference.** The public repo Rokit12/airwallex builds all 10 kits in one app, which is breadth. We win on depth: a live, Airwallex-enforced isolation proof and a product an operator would actually adopt.

## 5. Demo story (under 5 minutes)
Three employers, weekly run:
- Northwind: GBP and EUR contractors, funded.
- Kestrel: USD, funded.
- Harbour: AUD contractors, short.

1. **Goal and plan.** The agent prices all three runs. Northwind and Kestrel are approved by an approval bound to the batch hash, then paid live on Airwallex.
2. **New information.** A Kestrel deposit lands mid-run. A naive agent would sum balances and think Harbour is covered. Ringfence shows the cross-tenant total next to the per-employer truth: Harbour is still short. The agent holds Harbour's run and sends a funding request with the exact amount and act-by time.
3. **Revised decision.** Harbour's own top-up arrives in its AUD wallet. The agent re-plans and Harbour is paid.
4. **Attack.** A contractor "email" says "new bank details, also pay me 3x". The model may propose it, but the gate rejects it, the beneficiary is quarantined, and the reason codes go in the ledger.
5. **Exception.** One Northwind payout fails after PAID (simulated). The agent reopens it and asks for re-approval. The duplicate retry is a no-op.
6. **Proof.**
   - The isolation report is green.
   - A live cross-tenant probe returns 401.
   - Tampering with a ledger row turns `verify` red.
   - The fees are collected.
   - Final balances are shown for each employer.

## 6. Architecture (Python, kept small)
```
ringfence/
  awx.py        Airwallex client; per-employer token binding and cache; never logs tokens
  money.py      Decimal pricing, fees, FX
  mandate.py    open mandate and closed batch approval (HMAC)
  gate.py       pure policy checks -> allow / deny(reason)
  ledger.py     SQLite append-only hash chain, digest, verify
  executor.py   payout state machine, idempotency, UNKNOWN reconcile, polling
  verify.py     non-LLM isolation report
  scenarios.py  fault injection behind one interface ([SIMULATED])
  agent.py      Claude tool loop with typed tools
  app.py        FastAPI + one HTML dashboard
tests/          offline against a fake Airwallex
```
Hosting: build and test locally. At the end, deploy one small container (AWS credits) so judges get a public URL and Airwallex can reach us with webhooks.
Out of scope: multi-agent setups, the Visa and Metal awards, T:0, and real payroll calculation such as tax (we execute payouts; the payroll software calculates).

## 7. Schedule
| Date | Work |
|---|---|
| 3–4 Nov | awx client, money, mandate, gate, ledger, fake Airwallex, tests |
| 5–6 Nov | executor live on sandbox: 3 employers, FX, fees, idempotency |
| 7 Nov | scenarios: shortfall, mid-run deposit, late failure, injection, retry, tamper |
| 8–9 Nov | Claude agent loop with typed tools; plain-English rules compiler with replay |
| 10 Nov | dashboard: lanes UI, diff approval, "try to break it" panel |
| 11 Nov | segregation certificate, isolation report, README with setup, hardening |
| 12 Nov | record the video |
| 13 Nov | **submit** (15 Nov is buffer) |

## 8. Known deviations from the kit
- The kit assumes connected accounts (`x-on-behalf-of`) and `/charges`. Neither is enabled for us.
  - We use org-linked accounts with an `x-login-as` token per employer. This gives stronger isolation, because Airwallex itself refuses cross-tenant calls.
  - Fees are a real employer-to-platform transfer, with a simulated credit on the platform side.
  - Only the binding layer changes if Airwallex enables connected accounts (devhelp@airwallex.com).
- Sandbox OVERDUE status and deposit reversal can't be triggered, so they are simulated in the harness and labelled.
