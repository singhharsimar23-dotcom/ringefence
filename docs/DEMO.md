# Demo runbook (target under 4:30)

Before a take: `RF_NOW=2026-11-14T07:00:00+11:00`, then start the app (`make demo` live, or `make fake-demo`), open
`/?present=1`, press **R** to reset. Do not run probes or `scripts/recon_*` during a take. Keep a fake-backend take as backup.

| Time | Do | Say |
|---|---|---|
| 0:00 | Lanes screen | One bureau, many employers. Pooled money turned one shortfall into everyone's problem. Ringfence can move any employer's money, but only its own. |
| 0:25 | Key **1**: Run Friday payroll | Kestrel had no changes and is inside its mandate, so it pays itself. Northwind has one change: open the diff, hold to approve; only Northwind's own FX is converted. |
| 1:15 | Key **2**: other-tenant deposit, then **3**: Harbour top-up | A Kestrel deposit lands. The naive total says Harbour is covered; Ringfence says no. Harbour gets its own account and reference, the top-up matches, it is approved and paid. |
| 2:05 | Key **4**: bank-change email | The email asks for new bank details and 3x pay. Details are quarantined until someone else confirms by phone; the rate rise is a red diff, not applied. |
| 2:50 | Key **5**: late return, then double click and network drop | A payout is returned after PAID [SIMULATED]; re-pay needs a new approval. Clicking twice or dropping the network still pays once. |
| 3:30 | Proof tab | Isolation green per employer from Airwallex's records; the cross-tenant call returns 401; certificate verifies offline; tamper a row and the chain goes red at that row. |
| 4:10 | Rules tab, then close | A plain-English rule previewed against last week, signed by the employer. Ringfence is also an MCP server with no approve tool. |

If a card fails: use the Restore the row card (tamper), then press **R** and retake.
