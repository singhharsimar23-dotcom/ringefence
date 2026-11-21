# Changelog

All notable changes. Dates are 2026. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and versions follow [Semantic Versioning](https://semver.org/). Ringfence is below 1.0: sandbox and testnet only.

## [Unreleased]

### Added
- Documentation set in [docs/](docs/): architecture, MCP reference, run guide, Airwallex usage, testing, threat model and decisions.
- Contributing guide, code of conduct, roadmap, issue and pull request templates.
- Coverage floor in `make check`, and a release workflow that attaches checksums and a build attestation.
- Dependency review on pull requests and a daily OSV scan of `uv.lock`.

## [0.1.0] - 2026-11-21

First tagged release: the Airwallex Agentic Banking Hackathon, Kit 06 submission.

### Added
- Gate, mandates and exact-batch approval, an exactly-once executor, deadline-aware funding, FX on the employer's own account, and a hash-chained ledger (3 Nov).
- Fund isolation: one login per employer, a verifier with no model, and an Ed25519 certificate per employer (3 Nov).
- Web app with three employers, rules and proof tabs, and the Try it playground with isolated worlds (3 Nov).
- On-chain funding mandates on the Metal testnet (3 Nov).
- The Gauntlet: 36 hostile documents, a network storm, random operation sequences and a tamper test (4 Nov).
- Bench against a recommended agent setup, and five reproducible security findings ([FINDINGS.md](FINDINGS.md)) (6 to 10 Nov).
- A local stdio MCP server (3 Nov), and a remote MCP server with passkey approval (18 Nov).
- Supply-chain controls: MIT license, security policy, CodeQL, Dependabot, OpenSSF Scorecard (7.6 of 10 on 20 Nov), pinned actions, Atheris fuzz target (20 Nov).

### Fixed
- A stray carriage return in a timesheet raised an unhandled `csv.Error` instead of being rejected. Found by fuzzing (20 Nov).

[Unreleased]: https://github.com/singhharsimar23-dotcom/ringefence/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/singhharsimar23-dotcom/ringefence/releases/tag/v0.1.0
