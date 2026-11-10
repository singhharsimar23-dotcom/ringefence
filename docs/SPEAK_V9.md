# What you say (v9)

One Loom: Screen + Camera, medium bubble bottom left, 1080p. Save as `var/loom_v9.mp4`.
What's on your screen doesn't matter; every shot is built in the edit. Say it like you're telling a friend what you found. If you fumble, pause and redo the paragraph.
Say the technical word, then what it means in plain words. The screen carries the detail: the IDs, the code and the analysis. Your voice carries the story.

| Mark | What you do |
|---|---|
| **bold** | Lean on that word. |
| `/` | A tiny beat. |
| `//` | A real pause. Let it land. |
| *(italic)* | How to say the next part. |

---

## 1 · Open
*(warm, to the camera)*

Hi, I'm Harsimar Singh, / and this is **Ringfence**, / my submission for the Airwallex hackathon. //

Some companies run payroll for **lots** of other companies.
Every Friday they're holding **millions** of dollars that **aren't theirs**, /
and more and more, / that job is being handed to an **AI agent**. //
*(slower)* So my first question was: / how do I make sure it **never** pays the **wrong person**? //

---

## 2 · Break it first
*(conversational, a bit curious)*

Airwallex is building for exactly this: / agents that **move money**.
And their guide shows how you'd build one: / a frontier model, / their API as its tools, / and a **human** approving every payment. //
So before I built mine, / I built **that one**, / and spent days trying to **break** it.
If something breaks **there**, / it breaks in **every** agent built the same way. /
So the best way to build mine / was to break theirs **first**, / and harden against **everything** I found. //
*(plain, fair)* Airwallex kept every client's money **separate**, every time.
This is about what an **agent** falls for. //

---

## 3 · What I found
*(slow down; this is the centre of the film)*

The worst one / beats the **human**. //
A payment's waiting for approval.
The approver checks the name, / the amount, / the payee. / All correct. / They click **yes**. //
But while it was waiting, / the **bank account** behind that payee got changed.
Same name, / same ID. /
The money goes to the **new** account. / **Three** out of **three**, / no alert. //
And that payee stays **saved**, / so every run after pays it too, /
*(plain)* until the real person says, / "I **wasn't** paid." //

So who changes the bank account? / *(slower)* The **agent** does. / From an **email**. //
A normal-looking invoice: / *(casual)* "we've changed banks, please use this account." /
And it updated the payee. / **Five** out of **five**. //
*(full face, slowest line of the film)*
The approval checks a **label**. /
The money follows wherever that label **points**. //

*(a bit quicker; you're showing range)*
And once I saw that, / I kept finding the **same** shape.
**Batches**, / built for payroll, / never show a bank account at review, /
so the same swap hits the **whole run**, / and my key **couldn't cancel** it. //
Their Node SDK keeps **one** login for the whole program. /
Make a client per employer, / and Northwind's payment goes out on **Kestrel's** login. / I found that in their **code**. //
Their MCP gives every payment a **new** ID, /
so if a reply gets lost and the agent tries again, / that's a **second** payment.
I ran that retry live: / one pound owed, / **two** moved, / no cancel. //
*(quick)* And two plain ones: / the transfer list ignores the page number, / and the SDK's retry drops its filter. /
So paid people look **unpaid**, / and unpaid ones look **paid**. //

---

## 4 · So I built Ringfence
*(lighter, you're proud of it)*

So after all that, / here's what I built. / Ringfence. / The agent **suggests**. / My code **decides** what moves. //
Three clients, / Northwind, / Kestrel / and Harbour, / live on the Airwallex sandbox. / I hit **run**.
Kestrel had a normal week, / so it **pays**. / Northwind changed pay rates, / so it **waits** for their finance person. //

*(firmer; tie each fix to its bug)*
The approval swap: / Ringfence signs the exact **bank details** into the approval / and sends them **inside** the transfer. / No label left to swap. / **Held**, / three out of three.
Swap it at the last second, / and it reads the transfer back / and **cancels** it. //
The email: / a bank change goes into **quarantine** / until a **different** person confirms **by phone**. //
Every client gets its **own** login, / picked by my code, / never the model.
I tried crossing that line **twelve** ways. / Airwallex blocked **all twelve**. //

---

## 5 · Harbour, and the same trick on chain
*(a bit sly, then confident)*

Harbour's **short** this week, / and Kestrel's **fifty thousand** is sitting right there. /
Ringfence **won't touch it**. / It works out exactly what Harbour is missing / and asks **Harbour**. //
Harbour pays from its crypto wallet on **Metal**, / with a rule signed on chain: / **our** account, / **that** amount, / **one** pull. //
And the same trick shows up again: / an email with a wallet address that **looks** like ours, / same first six characters, / same last four. /
My code catches it, / and the chain refuses it **anyway**. / One coin more: / **refused**. //

---

## 6 · For the engineers
*(peer to peer, quicker, one fix per breath)*

Quick one for the **engineers**. //
Every payment gets its ID **before** the first try. /
A lost reply means **look it up**, / check payee, amount and currency, / **never** a new ID. //
I page by **cursor** / and check every item **myself**, / so a dropped filter can't fool it. /
**Paid** isn't final, / payments bounce, / so a run stays open until it **reconciles**. //
Every action goes into a **hash-chained** ledger, / and its head is stamped **inside** each Airwallex transfer. /
Rewrite my database, / re-hash the whole chain, / and Airwallex's copy **still** disagrees. //
And it runs as an **MCP server** / with **no** approve tool. / A **human** always signs. //

---

## 7 · Then I tried to break mine
*(build energy)*

Then I tried **really hard** to break mine. //
An agent that obeys **every** attack, / thirty-six hostile documents: / **not one dollar** moved. /
Twenty payments fired at once, / each paid **once**. / Two hundred ledger edits, / all **caught**. /
*(stop, half smile)* Four hundred and sixty-two tests. / I think you get the point. //

---

## 8 · Close
*(slow, to the camera)*

It's still a **normal** payroll agent, / with **one fix** / for every way I broke the first one. //
It's all **sandbox**, / and every finding is in the repo with its transfer IDs.
But don't take my word for it. / The demo's **live**. / Try to make it pay the **wrong** person. //
*(slow, simply)*
So, / back to my first question: / how do I make sure an AI agent / **never** pays the wrong person? //
**That's** Ringfence. // Thanks for watching.

---
---

## Receipts for every spoken claim (skip when recording)

| Spoken claim | Receipt |
|---|---|
| Their guide's agent: frontier model, API as tools, a human approving | AgentOS "require manual approval for tool calls"; `bench/market_agent.py` (Opus 5.5). The approver is a modelled diligent human who checks id, amount and currency. |
| Isolation held every time | `docs/GAUNTLET.md` §4, 12/12 401 `credentials_invalid` live; no cross-tenant 2xx ever (`AIRWALLEX_GAPS.md` "What Airwallex got right") |
| Approval swap, 3/3, no alert | `22c0a5d8…`, `49a84d09…`, `0d0b978b…` to ..9901; no beneficiary-changed webhook (`silent_divert.out.txt`). Never "undetectable": `/transfers` items do carry a bank snapshot. |
| Every run after, until the person says "I wasn't paid" | The payee stays saved; the bound is one pay cycle (`WHY_THESE_FINDINGS.md` §1) |
| Agent changes it from an email, 5/5 | `agent_bec_repeat.out.txt`, 9 Nov: `45528e1d…`, `749ebed0…`, `3dd76387…`, `70b841be…`, `958cc5cd…`. Overt "SYSTEM" injections were refused. Each link was verified on its own, not as one run. |
| Batches show no bank account at review; whole run; key can't cancel | `f5bd21a8…`, `f1cd2e93…`, `66404ad8…`, `f72b2134…` (4/4); 401 "Admin permissions required" |
| SDK keeps one login; Northwind's payment on Kestrel's login; found in code | `bench/probes/sdk_singleton_check.out.txt`, offline: A's call attached B's token. We checked the token, not a completed payment. |
| MCP gives every payment a new ID; a retry is a second payment | `@airwallex/developer-mcp@0.3.0-beta.13` `createTransfer.js`: `request_id: uuid.v4()` per call (code). |
| Fresh-ID retry live: one pound owed, two moved, no cancel | `charges-request-id-duplicate-new-id.out.txt`: `tr_EVfI4fFUMiKaByQv2_pW4w` + `tr_i7K2mR5GNpqv0iirL3-rGg`, both SETTLED, connected-account transfer, no cancel endpoint; reversed by hand. This was a REST retry, not through the MCP. Compose it as "that kind of retry", never "the MCP paid twice". Never cite the docs row. |
| Page number ignored → paid people look unpaid | `scripts/breakit.py pages` live, 9 Nov: 100 of 215 seen, 115 look unpaid |
| SDK retry drops its filter → unpaid ones look paid | `apiClient.js:157` argument swap; live REST: request_id filter 0, unfiltered 215, so "non-empty means it landed" marks a never-paid line as paid |
| Ringfence: bank details signed and sent inline; held 3/3; last-second swap cancelled | `39a2bf9`; live cards "Swap the bank account after approval" (HELD) and "Swap it at the last second" (CANCELLED, fresh world) |
| Quarantine + phone callback by a different person | `propose_bank_change` / `confirm_callback`; `tests/test_controls.py`; live card "Fake bank-change email" |
| Own login per client, picked by code; 12/12 | `x-login-as`; `GAUNTLET.md` §4 |
| Kestrel's 50k untouched; asks Harbour for exactly the shortfall | live card "Another employer's money arrives" `[SIMULATED]`; funding card |
| Metal: our account, that amount, one pull; lookalike (first 6 + last 4) caught and refused on chain; one coin more refused | `metal.py` (`--max-occurrences 1`, budget = shortfall, `poisoned_pull`); live cards "Try a fake wallet address", "Try to take too much"; tx hashes in `facts.json` |
| ID before first try; lookup checks payee/amount/currency | deterministic `request_id`; `_adopt` (`executor.py`); `b9403e6`, `7d8ff13` |
| Cursor paging; check items myself | `0e1bcb7`; `transfer_by_request` matches request_id per item |
| Paid isn't final; stays open until reconciled | PAID→FAILED live; live card "Payment bounces back" |
| Ledger head stamped in each transfer; re-hash → Airwallex disagrees | `rf_seq`/`rf_hash` metadata (`7d8ff13`); live card "Change a record and re-hash the chain" |
| MCP server, no approve tool | `mcp_server.py` |
| 36 docs / 0 moved; 20 at once; 200 edits; test count | `GAUNTLET.md` §1, 2, 5 (the obedient agent did what 28 of the 36 asked; the other 8 had no tool); `pytest -q`, say the number on the day |

## Runtime
About 840 spoken words, roughly 4:48 at 175 wpm. That's tight against the 5:00 cap, so deliver briskly; the pauses get tightened in post and the end card is about 5 s. If the first edit runs over 5:00, cut in this order:
1. The "two plain ones" line at the end of §3.
2. "Twenty payments… Two hundred ledger edits" in §7.
3. The paging line in §6.
4. "Ask for one coin more: refused" in §5.
5. The last-second swap line in §4.

Never cut: §2's "break theirs first" line, the label line in §3, or the first two lines of the close.

## Notes for the edit (skip when recording)
- **Spine.** The human approver is beaten, and an email supplies the access. Every other finding is the "same shape" (a label stays the same and the money moves). Every fix in §4 to §6 names the bug it answers.
- **The point is spread out, not saved for the end:** the method in §2, each fix tied back in §4, Metal as the same trick in §5, "one fix for every way I broke the first one" in the close.
- **Findings on screen.** As each finding is named, show what happened in plain words: their side in red, the transfer IDs, the one line of code (`apiClient.js:157`, `uuid.v4()`, the singleton), and the probe output. The voice stays simple; the screen carries the analysis.
- **Live demo, in this order, on a fresh world (press Start over first).** Run → Kestrel SCHEDULED, Northwind diff → "Swap the bank account after approval" HELD → "Swap it at the last second" CANCELLED → "Fake bank-change email" quarantine → isolation 12/12 → "Another employer's money arrives" `[SIMULATED]` → Harbour funding card → Metal "Pay from crypto wallet", "Try a fake wallet address", "Try to take too much" → under §6: "Internet drops mid-payment", "Double-click pay", "Payment bounces back", "Change a record and re-hash the chain" (stamp turns red).
- **Full face:** the open, the label line, the close.
