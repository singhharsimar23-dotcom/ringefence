# On-chain funding with Alta (formerly Metal)

> Approval-bound settlement (each approved payroll line becomes a one-pull mandate, with live attack results and every defect found) is in [ALTA_SETTLEMENT.md](ALTA_SETTLEMENT.md).

[Metal](https://testnet.metalntwx.com) is a blockchain testnet (chain ID 63825) whose wallets support on-chain spending mandates, with test token USDZ. Ringfence uses it as a second way for a short employer to fund payroll, through the pinned `@metalntwx/metal-agent@0.3.3` CLI ([metal.py](../ringfence/metal.py#L134)).

1. Harbour signs a mandate for exactly its shortfall: one pull, payable only to the platform's settlement wallet, expiring in one hour.
2. The agent pulls once, and the transaction hash goes into the ledger. The matching Airwallex deposit is [SIMULATED] and closes the funding request.
3. In device-signed mode, Harbour's own device signs and binds the mandate ([harbour_device.py](../scripts/harbour_device.py)), and the server never holds that key. A compromised server can pull at most what Harbour signed, once, to the payee Harbour named ([metal.py](../ringfence/metal.py#L108)).

Live testnet receipts from a server holding no Harbour key ([proof_device_signed.py](../scripts/proof_device_signed.py)):

| Step | Result | Transaction |
|---|---|---|
| Server pulls the shortfall | paid | [0x65c108fb…63bf](https://testnet.metalntwx.com/tx/0x65c108fbd62681b4ba788cad3cf56e3ed29063e80f8177bdaccce2a08d2463bf) |
| Same mandate pulled again | refused, `mandate_budget_spent` | [0x9ff764b4…1468](https://testnet.metalntwx.com/tx/0x9ff764b4879ad69b1a21031d2eca28fc87e8e4fb88eb982b9dbe6d8085021468) |
| Pull to a lookalike wallet | refused, `mandate_payee_not_listed` | [0x598bb65d…c703](https://testnet.metalntwx.com/tx/0x598bb65db1c032762020dc6a6039af57a1b0a5382225b82ad0fa13146e4ec703) |
| Server binds its own mandate on Harbour's account | bind reverted | none |

The faucet gives about 100 USDZ, so the demo counts 1 USDZ as USD 10. Tests: [test_metal.py](../tests/test_metal.py) (14).

Setup and variables: [RUN_IT.md](RUN_IT.md#metal-on-chain-funding).
