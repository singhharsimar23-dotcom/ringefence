# A live run on Airwallex

The offline tests prove the logic. This page is the same logic against the real Airwallex sandbox. Nothing here is a screenshot: every ID can be looked up in the matching Airwallex sandbox account.

Run `20261114-53jrfe` (pay date 14 Nov 2026), executed 11 Nov 2026 at 01:39 UTC through the public demo. Every ID can be looked up in the matching Airwallex sandbox account.

| Account | ID | Pays in |
|---|---|---|
| Platform (operator, collects fees) | `acct_NIym7HZZOOOqBCE7F6LkMA` | |
| Northwind Studio | `acct_Y5VX3QXWNSyiun0cbai15A` | GBP, EUR, AUD (with FX) |
| Kestrel Labs | `acct_FG3wEt9HNg29C0zhpelKHg` | USD |
| Harbour Foods | `acct_8bUTqZJePIG80-z_-xiutw` | AUD, starts short |

| Employer | Contractor | Amount | Transfer ID |
|---|---|---|---|
| Northwind | Ada Okoye | GBP 450.00 | `7730d4e5-50fe-4241-b702-25ee11556d45` |
| Northwind | Lukas Brandt | EUR 400.00 | `5295001b-4cad-4c8f-a93e-cb5fe2730b42` |
| Northwind | Mia Tran | AUD 300.00 | `fa7d28fb-14b4-43df-9a4a-8abbf14b7a4c` |
| Kestrel | Zoe Park | USD 500.00 | `e3534d8b-95b8-4e9b-bebb-7e00e9e6a4cf` |
| Kestrel | Noah Reyes | USD 550.00 | `31c9e9df-cee6-4a10-80ab-403b228aa234` |
| Harbour | Ivy Nguyen | AUD 700.00 | `893fa7a1-a902-45ec-b531-bcd30813034d` |
| Harbour | Omar Haddad | AUD 480.00 | `88ead1ba-d583-4305-b285-f0007366e5b1` |
| Harbour | Ruth Adler | AUD 60.17 | `1614a59d-8c4e-4ca4-86cf-e1d771b095f3` |

- **FX:** Northwind sold its own GBP 155.45 for AUD 300.00 at 1.929858, inside the approved rate band. Conversion `3e5a9c08-74fb-43c3-a78c-9709998a9804`, request ID `fx-20261114-53jrfe-northwind-AUD-r1`.
- **Short employer:** Harbour was AUD 1,240.17 short. It was asked to fund its own AUD global account `8ec497a4-67a9-4ba2-8b3d-48f1a53d1f4d` with reference `RF-HAR-JRFE-690Q` by 14 Nov 09:00 Sydney. Deposit `00db6d9e-9998-4866-a767-080d5da6153d` [SIMULATED] matched, and the run resumed.
- **Platform fees:** Northwind GBP 4.50 `5cd1d3a5-96f9-44ee-8250-b59bf003d37c`, Kestrel GBP 3.00 `7f9b745b-f449-46e1-a5d5-c00d7bd295ef`, Harbour GBP 4.50 `b0c08166-a751-4465-9651-e3e6a7818a4d`.
- **Certificates:** each employer passed all 10 verifier checks. The certificates in [docs/proof/](proof/) list every debit with its request ID. `uv run python -m ringfence.verify cert docs/proof/northwind.json` prints `VALID ... PASS`, and any edited field gives `INVALID`.
- **Real vs simulated:** transfers, FX, fees, beneficiaries, the global account and the isolation check are real sandbox calls. Payouts reaching `PAID` and Harbour's deposit used Airwallex's `/simulation/*` endpoints. The platform's fee credit is recorded by Ringfence only, because the sandbox doesn't credit the platform. All simulated steps are labelled `[SIMULATED]`.
- **APIs used:** login per account (`x-login-as`), `/balances/current`, `/beneficiaries`, `/global_accounts`, `/deposits`, `/fx/quotes/create`, `/fx/conversions/create`, `/transfers/create`, `/transfers` (get, list by `request_id`, cancel), `/webhooks`, `/simulation/*`.
