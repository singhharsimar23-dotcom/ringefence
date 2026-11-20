# Security policy

Ringfence moves money on the Airwallex sandbox and the Metal testnet only. It is not deployed against live funds.

## Report a vulnerability

Use GitHub's private reporting: **Security tab → Report a vulnerability** on this repository. Please do not open a public issue for a security problem.

Include the route, tool or file involved, the steps to reproduce, and what an attacker gains. Never include real credentials. We aim to acknowledge a report within 3 working days.

## What counts

Anything that lets a caller move money without the approval gate, pay an account the approver did not sign, reach another employer's funds, replay or double-send a payout, or alter the ledger undetected. The security findings already known are in [FINDINGS.md](FINDINGS.md).

## Supported version

Only the latest commit on `main`.
