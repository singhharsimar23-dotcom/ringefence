# Handoff to Sonnet: finish the Airwallex-gaps work

Read first: `CLAUDE.md` (rules), `docs/AIRWALLEX_GAPS.md` (the 15 gaps, with receipts), `docs/BENCH.md`, and
`docs/THREAT_SERVER_OWNED.md`. Today is 6 Nov 2026. The deadline is 15 Nov; submit by 13 Nov.

## Hard rules (don't break these)
- Before any shell command: `export MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8`. Run Python with `uv run`.
- **Frozen money core: don't edit without the user's explicit OK.** The frozen files are gate.py, executor.py,
  ledger.py, mandate.py, money.py, funding.py and fx.py. Items marked FROZEN below need that OK first. Ask once, in one
  message, listing them.
- **Live writes:**
  - Northwind and Kestrel only, GBP/EUR ≤ 5, throwaway payees (prefix `PRB-`).
  - Cancel every transfer by exact id, and delete every payee you made.
  - Never use AUD on Northwind. Harbour and the platform are read-only.
  - Don't run `scripts/recon_isolation.py`.
- **Never print** tokens, keys, `METAL_RPC_URL` or `METAL_RPC_SECRET`.
- **Commit only; don't push or deploy.** The user runs `git push` and `bash deploy/deploy.sh rfvm2`. Commits end with
  `Co-Authored-By: Claude Sonnet 5.5 <noreply@anthropic.com>`.
- **Wording.** Call findings "API-design / SDK / integration gaps", never "Airwallex vulnerabilities". No cross-tenant
  2xx was seen. Never claim Ringfence would have stopped Bybit or Binance.
- **Speaker.** Harsimar; use they/them.

## Step 0: the working tree has uncommitted Ringfence fixes. Test them, then commit.

`git diff --stat` shows 5 files. Their purpose:

| File | Change | Fixes gap |
|---|---|---|
| `ringfence/verify.py` `_transfers` | Pages with the cursor (`page="0"`, then `page_after`), dedupes by id, and stops when a page adds nothing. Before, it used `page_num` and looped forever past 100 transfers. | #4 |
| `ringfence/fake_awx.py` `_list_transfers` | Like live: ignores `page_num`, treats `page` as a cursor (`cur-N`), and returns `page_after`. | #4 |
| `ringfence/fake_awx.py` beneficiary GET | Like live: an unknown id returns 200 with an empty body (it used to return 404). | #13 |
| `ringfence/awx.py` `TenantClient.get` | An empty 200 (`None` or `{}`) raises `AwxError(404, "not_found")`. | #13 |
| `ringfence/awx.py` `_raise_for` | Maps `request_id_duplicate` + `details.source_id` to `duplicate_request_id` + `details.id`, so the existing `_adopt` path handles CA transfers and Charges. | #3 |
| `tests/test_controls.py` | 2 new tests: empty-200 payee holds the run; Proof sees 250/250 transfers when `page_num` is ignored. | |
| `tests/test_awx.py` | 1 new test: the CA spelling is normalised. | |

The suite passed (432) **before** the `_raise_for` change. Steps:
1. Run `uv run pytest -q`. If anything fails, fix it in those files only.
2. Commit: "Fix: cursor paging on /transfers, empty-200 payee reads, CA-transfer duplicate spelling".
3. Check that the `_raise_for` change didn't break `executor._adopt`. It reads `e.details["id"]`. Grep `details` in
   executor.py and fees.py, read only.

## Step 1: remaining Ringfence fixes, in priority order

1. **FROZEN: inline bank details in `executor._body`.** Send the pinned `beneficiary` object inline in
   `transfers/create` instead of `beneficiary_id`. This removes the race residual in gap #1 and makes batches safe (#2).
   Live proof that inline works: `05bf3293-e9b9-43b4-ab30-bd47ae282b0b`.
   - Keep `beneficiary_id` in the ledger for Proof.
   - The fake's `_create_transfer` must accept an inline `beneficiary`.
   - Add a test: "repointed after release, the transfer still goes to the pinned account".
2. **DIGITAL_WALLET fails open (#7).** Each of these sites skips the check when the snapshot has no `bank_details`:
   - `orchestrator.py` ~L198–200 (`if not bd …: continue`);
   - the `redirected` check in `verify.py`, which requires `bank_details` to be truthy;
   - `beneficiaries.drifted()`, which catches only `AwxError`, so a missing key raises `KeyError` with no named hold.

   Fix:
   - Fingerprint `digital_wallet` when `type == DIGITAL_WALLET`.
   - Treat a snapshot with neither field as drift.
   - Make `drifted()` read `.get("beneficiary", {}).get("bank_details")` and count a missing value as drifted.
   - Add `all_ga_keys()` to the platform's own GA (`beneficiaries.py` ~L148).

   None of this is frozen except where the gate calls it.
3. **FROZEN: `poll_inflight` misses late returns.** `executor.py` ~L365 polls PAID lines only for runs in RELEASED or
   DONE. A second late return in a run that is AWAITING_APPROVAL (reopened) goes unseen if its webhook is missed. Widen
   the poll to AWAITING_APPROVAL, READY and HELD. Offline proof: `bench/probes/probe_webhook_double_event.out.txt` "4b".
4. **FROZEN: a 409 `request_pending` goes to FAILED_TO_SUBMIT.** It should go to UNKNOWN and then reconcile by
   `request_id`, because the create may have booked.
5. **FROZEN: IN_APPROVAL lines aren't reserved.** Add `IN_APPROVAL` to the `lines_in_states(...)` reservation, so
   funding never double-counts.
6. **H5:** `name_match()` must block UNAVAILABLE, INVALID and PARTIAL in production (it's `shortcut:`-marked). Gate it
   on an env flag, not the demo.
7. **FROZEN, H4:** anchor each run's ledger head hash outside the server (transfer `metadata` or a Metal payment id).

**Status 6 Nov: items 1-7 are DONE** (`5d001ac`, `39a2bf9`, `7d8ff13`; the user approved the frozen edits). Item 2 of the Step 1 list was
the wallet fix. Still open from this document: Step 2 probes P0 batch-approval and the P1 approval probes (need the user),
the P1 market-agent faults (need Anthropic credit), and Step 3.

## Step 2: remaining Airwallex probes

Template: copy the helpers from `bench/probes/snapshot_timing.py` (`ben`, `repoint`, `dest`, `body`, `call`,
`cleanup`). Write the raw output to `bench/probes/<name>.out.txt`. Add each confirmed result to
`docs/AIRWALLEX_GAPS.md` with its transfer ids.

| Priority | Probe | How | Needs user? |
|---|---|---|---|
| P0 | **Official MCP payer unbound (#6)** | Re-run `uv run python bench/probes/official-mcp-payer-unbound.py`. Trial 0 was invalid: the approver compared first and last name, which Airwallex drops for SG payees. Count trials where the model paid from the wrong employer, or a human-style check (name, last-4, amount, currency) approved the wrong payer. | No |
| P0 | **Batch under the approval workflow (#2)** | User enables "API-initiated transfers require approval" on Northwind. Then: add_items → submit → repoint while it waits for approval → approve in the web app. Which account does it pay? | Yes: enable the policy, then click approve |
| P1 | APPROVAL_REJECTED / RECALLED: edit and resubmit | With the same policy: reject, edit the payee, resubmit. Does the old approval carry over? | Yes |
| P1 | IN_APPROVAL can't be cancelled | With the same policy: try `/transfers/{id}/cancel` while IN_APPROVAL. If refused, Ringfence's race recall is disabled in approval mode. | Yes |
| P1 | Market agent with `duplicate_request_id` at a different amount | Add a fault to `bench/market_agent.py`: the sheet amount changes on re-run, same `request_id`. Does the model adopt the wrong amount? | No |
| P1 | Market agent with PAID → FAILED late return | Add a fault: after the run, simulate PAID → FAILED on one line. Does the model re-pay safely, once? | No |
| P2 | Cheaper model arm | Run `market_agent.py` with `claude-haiku-5-5` on `approval` and `inject`, 3 trials each. | No |
| P2 | Wrong-bound batch with inline beneficiary | Kestrel token, batch item with Northwind's payee bank details inline. Does it book from Kestrel's wallet? It probably does, as a correct API, but it shows the binding is the only guard. | No |

**Cleanup debt.** A GBP 1 Airwallex Pay movement, Northwind to Kestrel, is PAID and can't be cancelled (#7). Leave it
unless the user asks. The reversal would be a CA transfer back from Kestrel.

## Step 3: video re-cut (Remotion project in `video/`, plan in `C:\Users\hprad\.claude\plans\soft-floating-stallman.md`)
- **Replace the "Break it" chapter** with an "Airwallex's own stack" segment, about 60–75 s. Hard cuts, real terminal
  and `.out.txt` captures, Bam text, in this order:
  1. Approval repoint: "approved the id · paid ..9901 · 3/3".
  2. Batch payroll: "batch preview shows no bank · 4/4 to ..9901 · can't cancel (401 admin)".
  3. Docs say new `request_id`: "GBP 2 for a GBP 1 payable · SETTLED · no cancel".
  4. Pagination: "page_num ignored · 99 of 199 look unpaid".
  5. SDK retry: "lookup loses its filter · 201 results say paid".
  6. End: "Airwallex binds pointers. Ringfence binds content."
- Lines to speak: the "Video line" under each gap in `docs/AIRWALLEX_GAPS.md`.
- Keep the total under 5:00. The current cut is 4:58, so cut theory time to make room.
- Personal screenshots go only in gitignored `video/public/real/`. Never show Claude Code on screen.

## User-only steps (tell the user; don't attempt)
1. Deploy the new code: `bash deploy/deploy.sh rfvm2`, then `setup_demo` and a reset on the VM.
2. Enable "API-initiated transfers require approval" on Northwind (web app), for the P0 and P1 probes.
3. Optional hardening to mention in the video: an IP allow-list on the scoped key, and per-employer keys.
4. `git push` once the commits are reviewed.
