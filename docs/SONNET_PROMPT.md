Paste everything below the line into a new Claude Code session (Sonnet 5.5) opened in this repo.

---

You are building Ringfence v2 in this repo (branch `build`). Read `CLAUDE.md`, then all of `docs/PLAYGROUND_SPEC.md`, before you touch code. The spec is the contract: when it and your instinct disagree, follow the spec. When the spec and the code disagree, trust the code, fix the spec in the same commit, and say so in your report.

**Goal.** Judges can describe their own payroll (type it, paste an email, drop a CSV, or pick an example). The real agent, real gate and real Airwallex sandbox then run it in an isolated "world", and every step shows evidence they can check. Today's three-employer demo stays, with every feature, at `#/demo`.

**Order (one tier at a time; don't start the next until the current gate passes):**
1. **T1 backend** (spec 4.3, then 4.2, 4.1, 4.4–4.7, plus the tests in 6 and 5b)
2. **T2 UI** (3.1–3.3)
3. **T3 evidence** (3.4)
4. **Deploy and T4 docs** (10.4–10.5)
5. **T5 Metal**, per 9.1: probe first, hard stop 11 Nov 12:00

**Non-negotiables:**
- Don't change `gate.py`, `executor.py`, `ledger.py`, `mandate.py`, `money.py`, `funding.py` or `fx.py`. The single exception is the `run_id` world suffix in `orchestrator.run_id` (spec 4.3). If you believe you need another money-core change, stop and ask.
- When `RF_WORLD`, `RF_TENANTS`, `RF_DEMO` and `RF_METAL` are unset, the Three employers demo must behave exactly as today.
- Money is Decimal (BigInt cents in JS, display only). The LLM proposes; code decides. Never log tokens, keys, `METAL_RPC_URL`, `METAL_RPC_SECRET` or the full `AWX_PLAYGROUND_ACCOUNT`.
- Run the regression gate (spec 10.8) after every tier: pytest, ruff, and the e2e flow on fake. After each deploy, also run the e2e against the live URL.
- UI: follow spec section 3 exactly, including the "Slop tells, banned" list. Premium means restraint: one accent colour, aligned numbers, real data in mono, a written sentence for every state, and purposeful 160–400ms motion that respects reduced motion. Do the screenshot design QA at 1440×900 and 390×844 before calling T2 done.
- Walk every row of the judge-proofing matrix (spec 5b) yourself before T2 sign-off.
- Copy: no banned words, emoji or exclamation marks (`tests/test_copy.py`). Short, plain sentences. Put new strings in `copy.js` and `copy.py`.
- Commit per tier on `build` with clear messages, ending with your Co-Authored-By line. Deploy with `bash deploy/deploy.sh rfvm2`. Don't push or merge to `main` until T1–T3 are green and the live e2e passes.
- Windows/Git Bash: `export MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8`. Use `uv run` (system Python 3.10 lacks `datetime.UTC`). Azure CLI and gh live under `/c/Program Files/...` (see `CLAUDE.md`).

**Known state (3 Nov):**
- `AWX_PLAYGROUND_ACCOUNT=acct_zQZE…` is set locally and on the VM.
- The playground account is linked to the API key, and login works (verified 3 Nov). The live playground is available.
- `METAL_RPC_URL` and `METAL_RPC_SECRET` are set locally and on the VM, and the chain id was verified as 63825. T5 is unblocked; see spec section 8, item 4.

**Report back at each tier gate:**
- What was built, and the test count before and after
- Anything in the spec you changed and why
- The judge-proofing rows you verified
- Live URL checks
- What's left

Keep it short.
