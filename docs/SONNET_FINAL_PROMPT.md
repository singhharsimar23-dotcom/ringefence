Paste everything below the line into a fresh Claude Code session (Sonnet 5.5) opened in this repo.

---

You are finishing Ringfence for submission (branch `build`). Before touching code, read `CLAUDE.md`, then **all** of `docs/FINAL_SPEC.md`. The spec is the contract. If the spec and the code disagree, trust the code, fix the spec in the same commit, and say so.

**Order.** WP1 → WP2 → WP3 → WP4 → WP5 → WP6 → WP7. Do one WP at a time, and don't start the next until the gate in spec §2 is green (pytest, ruff, e2e on fake). Commit after each WP.

**Non-negotiables.**
- Don't edit the frozen money core listed in §2. If you think you must, stop and ask.
- Decimal money. The LLM proposes, code decides. Never log secrets.
- Use the landing copy and design tokens in §6 **verbatim**. Don't add sections, slogans, gradients, colours, shadows, icons or animations that aren't in the spec. When in doubt, leave it out.
- Vendor GSAP and the Geist fonts with their licence files. No npm build step, no CDN at runtime.
- Every WP1 fix ships with its test. Every new endpoint validates input and is covered by a test.
- Before you call WP5 done, do the design QA in §6 twice, with screenshots.
- Windows: `export MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8`; use `uv run`.
- Don't push or merge. Deploy only in WP7.

**Report at each gate (short):**
- what was built
- the test count before and after
- spec changes and why
- anything skipped
- risks you noticed

Then stop and wait.
