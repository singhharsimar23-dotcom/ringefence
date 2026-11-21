# Documentation

Start with the row that matches what you want to do.

| I want to... | Read |
|---|---|
| Understand how it works | [ARCHITECTURE.md](ARCHITECTURE.md): the flow, the components, the life of a run, trust boundaries |
| Connect an agent | [MCP.md](MCP.md): one-line connect, the tools, approval, errors |
| Run it | [RUN_IT.md](RUN_IT.md): offline demo, live sandbox, settings, self-hosting MCP |
| See what it does on Airwallex | [AIRWALLEX.md](AIRWALLEX.md): what it calls and why. [PROOF.md](PROOF.md): a recorded run with every ID |
| Judge how safe it is | [THREAT_MODEL.md](THREAT_MODEL.md), [../FINDINGS.md](../FINDINGS.md), [TESTING.md](TESTING.md) |
| Know why it was built this way | [DECISIONS.md](DECISIONS.md) |
| Read state over HTTP | [API.md](API.md) |
| Use the on-chain funding option | [METAL.md](METAL.md) |

## Evidence

| File | What it holds |
|---|---|
| [BENCH.md](BENCH.md) | a recommended agent setup against Ringfence on live faults |
| [GAUNTLET.md](GAUNTLET.md) | 36 hostile documents, a network storm, random sequences |
| [PROBES.md](PROBES.md) | what Airwallex actually does, from live probes. The fake Airwallex follows it. |
| [proof/](proof/) | signed certificates, one per employer |

## Project

[CONTRIBUTING](../CONTRIBUTING.md) · [CHANGELOG](../CHANGELOG.md) · [ROADMAP](../ROADMAP.md) · [SECURITY](../SECURITY.md) · [CODE OF CONDUCT](../CODE_OF_CONDUCT.md) · [LICENSE](../LICENSE)

## Layout

[ringfence/](../ringfence/) core and web app · [tests/](../tests/) · [fuzz/](../fuzz/) fuzz target · [scripts/](../scripts/) findings and setup · [bench/](../bench/) sandbox probes and evidence · [examples/](../examples/) the engine in your own code · [demo/](../demo/) payroll files, attack documents and the standard agent · [static/](../static/) UI · [deploy/](../deploy/) Azure VM
