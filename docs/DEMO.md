# Demo runbook (target under 4:30)

The app is public and has no login. Before a take: open the public URL (or `make fake-demo` locally), add `?present=1`,
press **R** to start over, wait for the lanes to read "Not started". Do not run probes or `scripts/recon_*` during a take.
Keep a fake-backend take as backup. In presenter mode keys **1-6** run the "Try to break it" cards in the order below,
and the arrow keys move the caption.

Open on the playground (home page): pick **Bank-change email**, press Read it, Run, and hold to approve. Say: "Describe any payroll.
The real agent, the real rules and the real Airwallex sandbox run it in a world of its own, and every step shows its evidence."
Open the bank-change row to show the quarantine, then press Three employers and follow the table below for isolation and proof.

| Time | Do | Say |
|---|---|---|
| 0:00 | Pay tab, progress rail | One bureau, three employers, three separate Airwallex accounts. Ringfence can move any employer's money, but only that employer's own. |
| 0:25 | Press **Run Friday payroll**. Lanes fill in one by one, each with an agent note | Claude reads the inbox and prepares each run. Code prices it and checks every limit. Kestrel has no changes and is inside its mandate. Northwind has two rate changes. Harbour is short on AUD. |
| 1:10 | Northwind: **Review and approve**, switch to Priya when asked, hold to approve | Only the named finance person can approve, and the approval is bound to this exact batch. |
| 1:50 | Harbour: copy the funding details. Cards: **Other employer's deposit**, then **Harbour top-up**. Approve as Lee | A deposit into another employer's account changes nothing. Harbour gets its own account and reference, the top-up matches, and it is paid. |
| 2:20 (optional) | Harbour cards: **Pay the shortfall from Metal**, then **Agent over-pulls on Metal** | Harbour's on-chain mandate allows one pull of exactly the shortfall. The real Metal testnet transaction is linked. Asking for 1 more is refused on chain. |
| 2:40 | Key **1**: bank-change email. Key **5**: cross-tenant call | The email asks for new bank details and 3x pay: the details are quarantined, the email is flagged, nothing is sent. Airwallex itself refuses one employer's token on another's account (401). |
| 3:20 | Key **2** double click, key **3** network drop | Clicking twice or dropping the network still pays once. |
| 3:40 | Proof tab | Isolation green per employer from Airwallex's records, certificates verify offline. Key **4** tampers a ledger row and the chain goes red at that row. |
| 4:10 | Rules tab, then close | A plain-English rule previewed against last week, signed by the employer. Ringfence is also an MCP server with no approve tool. |

A start takes about 40 s on Sonnet (lanes fill in as each agent finishes). Talk over the first lane, or cut the wait in the edit.
If a card fails: use **Start over** (menu, top right) and retake. Start over is limited to once per 20 s on the public demo.
