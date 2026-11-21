# HTTP API

Two supported ways in: the [MCP server](MCP.md) (`/mcp`) and the engine as a library ([examples/embed.py](../examples/embed.py)). The web app's `/api/*` routes are its own backend. Only the read-only ones below are meant for outside callers. `/openapi.json` lists every route.

## Read-only, safe to call

| Route | Returns |
|---|---|
| `GET /healthz` | `{ok, head, queue, ready, backend}`: ledger head and whether the engine is ready |
| `GET /api/state` | the current `run_id` and pay date, and per employer (`lanes`) its run state, account and next step |
| `GET /api/proof` | the verifier's 10 checks per employer, certificate validity and balances. Runs the verifier, so allow a few seconds |
| `GET /api/cert/{tenant}` | the signed Ed25519 certificate for `northwind`, `kestrel` or `harbour`, as a JSON download. Verify offline with `uv run python -m ringfence.verify cert <file>` |
| `GET /api/recheck/{transfer_id}` | fetches one transfer again from Airwallex and returns its status, amount, currency and `request_id`. Only transfer IDs in the current ledger, so it is not an open proxy |
| `GET /api/ledger?seqs=1,2,3` | up to 50 ledger entries by sequence number, each with `hash` and `prev_hash` so you can check the chain |

## Webhook in

`POST /webhooks/airwallex` expects Airwallex's `x-timestamp` and `x-signature` headers: HMAC-SHA256 of the timestamp followed by the raw body, keyed with the account's webhook secret ([Airwallex docs](https://www.airwallex.com/docs/developer-tools/webhooks/listen-for-webhook-events.md#check-webhook-signatures)). Missing, wrong or stale (older than the allowed window) signatures get `401`. A valid event only prompts a re-fetch of the transfer. It never sets state.

## Not an integration surface

`/api/start`, `/api/approve`, `/api/release`, `/api/hold`, `/api/kill`, `/api/reset`, `/api/scenario/*` and the rest are the buttons of the demo UI. On the public site they act on one shared demo run, take a user name from a drop-down with no login, and are throttled. Real approval for an agent run is a passkey on `/approve/<run>` ([mcp_remote.py](../ringfence/mcp_remote.py)), and there is no approve tool.
