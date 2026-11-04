# Live demo script (about 4:30)

**The one idea:** a payroll bureau runs payroll for three companies. An AI agent does the work, but it can only ever
spend each company's own money, only on that company's own people, and nothing an email says can change that.
A wrong payment never happens, rather than being caught later.

Judges score whether the agent has a goal, makes a plan, meets new information, changes its decision, and gets a result
you can check. Each beat below shows one of those. Say the "Say" column in your own words.

## Before you start (2 minutes)

1. Open https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com/#/demo
2. Menu (top right, `...`) > **Start over**. Wait for all three cards to read "Not started".
3. Have `demo/samples/` open in a file window. You will drop one file into the page.
4. Don't run anything else against the site while recording. Start over works once every 20 s.

## The script

| Time | Click | Say |
|---|---|---|
| 0:00 | Stay on **Three employers** | "This is a payroll bureau with three clients: Northwind, Kestrel and Harbour. Each has its own Airwallex account. The risk the bureau carries is simple: one wrong transfer pays one company's staff with another company's cash. Ringfence makes that impossible." |
| 0:20 | **Run Friday payroll** | "The agent's goal is to get everyone paid on Friday. It reads each company's timesheets and emails and makes a plan for each one. The cards fill in as it finishes." |
| 0:40 | On Northwind, **What the agent read** | "This is the raw timesheet the agent read. It's untrusted. The agent proposes a run; plain code prices it and checks every limit." Close the dialog. |
| 0:55 | Point at the three cards | "Kestrel had no changes and is inside its limits, so it pays on its own. Northwind has two rate changes, so it waits for a person. Harbour doesn't have enough Australian dollars. That's new information, and the agent changes its plan: it asks Harbour for a top-up instead of paying." |
| 1:15 | Northwind: **Review**, switch user when asked, hold to approve | "Only Northwind's named finance person can approve, and the approval covers this exact batch." |
| 1:40 | Card **Another employer's money arrives** | "Now 50,000 dollars lands in Kestrel's account while Harbour is short. A careless system would use it. Ringfence never adds up balances across companies, so Harbour is still waiting." |
| 2:00 | Scroll to **Harbour's ringfence, enforced on chain**. Press **Pay from crypto wallet** | "Harbour keeps a stablecoin treasury on Metal. It has signed a mandate on chain: one pull, capped at exactly the shortfall, payable only to the platform. That's a real testnet transaction; the link opens it." (Takes up to a minute. Talk over it.) |
| 2:40 | **Try to take too much** | "Suppose the agent goes wrong and asks for one coin more. The chain itself refuses, and the refusal is recorded on chain. Ringfence's checks are the first lock; the mandate is the second." |
| 3:00 | **Try a fake wallet address** | "This is the scam that's costing people real money right now: address poisoning. An email gives a new wallet that starts and ends like the real one, which is all most people check. Ringfence compares the whole address and flags it. Even if it got through, the mandate names one payee, so the chain refuses that too." |
| 3:25 | Card **Fake bank-change email** | "Same scam, the bank version: a contractor 'changed banks', asks for triple pay and says skip approval. The new details are quarantined, the email is flagged, nothing is sent." Open **Why it held**. |
| 3:45 | Card **Cross-tenant call** | "Even if our code had a bug, Airwallex refuses one company's login on another company's account. That's a live 401 from Airwallex." |
| 4:00 | **Proof** tab | "The result, checked against Airwallex's own records, per company: every payment had an approved intent, went to that company's own payees, and nothing crossed. The ledger is hash-chained, and each company gets a signed certificate." |
| 4:20 | **Try it** tab. Press **Attach**, pick `demo/samples/timesheet_week45.csv`, **Read it** | "And you can try it yourself. Drop in any timesheet or email and the same agent and rules run it in a sandbox of its own." End there. |

## If something goes wrong

- A card says "Still working": wait. The page updates by itself when the step finishes.
- A Metal button stays greyed out: Harbour has to be waiting for funds first (after **Run Friday payroll**).
- Anything else: menu > **Start over**, wait 20 s, retake. Keep a recorded take as backup.

## Sample files (`demo/samples/`)

| File | What it shows |
|---|---|
| `timesheet_week45.csv` | A normal weekly timesheet, three countries. Code reads it directly; no AI involved. |
| `email_bank_change.txt` | The bank-change scam. Paste or attach it on **Try it**: the pay is drafted, the new bank details are held. |
| `email_hidden_instructions.txt` | A prompt-injection email that tells the agent to ignore its rules. The agent's output is checked by code, so it changes nothing. |
