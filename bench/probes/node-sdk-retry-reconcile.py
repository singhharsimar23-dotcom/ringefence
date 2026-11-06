"""node-sdk-retry-reconcile, live arm (Northwind only; Harbour/platform untouched except a read-only count).
Airwallex docs (transfers/create, request_id): "When you are not sure about the outcome of a payout creation request ...
you can try to get a payout with this request_id to find out."
@airwallex/node-sdk 2.1.0-beta.5 dist/client/apiClient.js:157 retries with `this._request(method, url, config, data)`,
so a retried GET is `get(url, undefined)`: no params, no headers. This script sends, live, exactly the two GETs the
SDK sends (filtered first attempt, filterless retry), then fires one landed-create's duplicate pair and passes the real
error bodies through a line-for-line port of apiClient.js:73-101 + developer-mcp errorHandler.js:16.
  uv run python bench/probes/node-sdk-retry-reconcile.py
Money: one GBP 1.00 transfer (at most 3 create attempts, one booking), cancelled after."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import awx as _env  # noqa: E402

for n in ("AWX_CLIENT_ID", "AWX_API_KEY", "AWX_BASE_URL", "AWX_EMPLOYER_A", "AWX_EMPLOYER_B", "AWX_EMPLOYER_C", "AWX_PLATFORM_ACCOUNT"):
    os.environ.setdefault(n, _env.env(n) or "")
from ringfence.awx import Awx, AwxError  # noqa: E402

TAG = f"PRB-node-sdk-retry-reconcile-{int(time.time()) % 100000}"
awx = Awx()
nw = awx.for_tenant("northwind")
made_t: list[str] = []
made_b: list[str] = []


def say(*a):
    print(*a, flush=True)


def sdk_error(status: int, data: dict) -> tuple[str, str]:
    """Port of node-sdk 2.1.0-beta.5 apiClient.js:73-101 (class + message)."""
    msg = data.get("message") or data.get("error_description") or data.get("error") or f"Server error: {status}"
    if isinstance(data.get("details"), list) and data["details"]:  # :80 only joins ARRAY details; Airwallex sends {id}
        msg += " - " + ", ".join(map(str, data["details"]))
    cls = {401: "AuthenticationError", 403: "AuthorizationError", 404: "NotFoundError", 429: "RateLimitError",
           400: "ValidationError"}.get(status, "ServerError" if status >= 500 else "ApiError")
    return cls, msg


def mcp_text(status: int, msg: str) -> str:
    """developer-mcp 0.3.0-beta.13 dist/utils/errorHandler.js:16, operation name from createTransfer.js:78."""
    return f"Failed to create transfer ({status}): {msg}"


def part_live_get():
    say("\n== 2 live: the reconcile GET as sent (attempt 1) vs as retried by the SDK (no params)")
    rid = "prb-never-used-000001"
    filt = nw.get("/transfers", {"request_id": rid}).get("items", [])
    bare = nw.get("/transfers").get("items", [])  # the retry: url only, params dropped
    say(f"northwind GET /transfers?request_id={rid}: items={len(filt)}")
    say(f"northwind GET /transfers (retried, filterless): items={len(bare)} matching_request_id={sum(t.get('request_id') == rid for t in bare)}")
    say(f"RESULT live_filterless_nonempty={len(bare) > 0} naive_length_check_says_paid={len(bare) > 0} "
        f"per_item_match_says_paid={any(t.get('request_id') == rid for t in bare)}")
    # the 'platform's own view' when a platform-token caller's x-on-behalf-of is dropped: count only, read-only
    plat = awx.for_tenant("platform").get("/transfers").get("items", [])
    say(f"platform GET /transfers (no x-on-behalf-of): items={len(plat)}")


def part_live_409():
    say("\n== 3 live: two identical creates within ms (SDK retry racing a slow first attempt), then a re-POST")
    p = {"nickname": f"{TAG}-ada", "transfer_methods": ["LOCAL"], "beneficiary": {
        "entity_type": "PERSONAL", "first_name": "Ada", "last_name": "Probe",
        "address": {"country_code": "GB", "city": "London", "street_address": "1 Test St", "postcode": "EC1A 1BB"},
        "bank_details": {"bank_country_code": "GB", "account_currency": "GBP", "account_name": "Ada Probe", "bank_name": "HSBC",
                         "account_routing_type1": "sort_code", "account_routing_value1": "040004", "account_number": "41234567"}}}
    bid = nw.post("/beneficiaries/create", p)["id"]
    made_b.append(bid)
    rid = f"prb-409-{int(time.time())}"
    body = {"request_id": rid, "beneficiary_id": bid, "transfer_amount": Decimal("1.00"), "transfer_currency": "GBP",
            "source_currency": "GBP", "transfer_method": "LOCAL", "reason": "wages_salary", "reference": TAG[:40]}
    nw._tok()  # warm the token so both threads hit create, not login
    gate, out = threading.Barrier(2), [None, None]

    def fire(i):
        gate.wait()
        t0 = time.monotonic()
        try:
            out[i] = (201, nw.post_money("/transfers/create", body), t0)
        except AwxError as e:
            out[i] = (e.status, {"code": e.code, "message": e.message, "details": e.details}, t0)

    th = [threading.Thread(target=fire, args=(i,)) for i in (0, 1)]
    [t.start() for t in th]
    [t.join() for t in th]
    say(f"start skew ms={round(abs(out[0][2] - out[1][2]) * 1000, 1)}")
    for st, d, _ in out:
        if st == 201:
            made_t.append(d["id"])
            say(f"  201 id={d['id']} status={d.get('status')}")
        else:
            say(f"  {st} {json.dumps(d)[:300]}")
    try:
        third = (201, nw.post_money("/transfers/create", body))
        made_t.append(third[1]["id"])
    except AwxError as e:
        third = (e.status, {"code": e.code, "message": e.message, "details": e.details})
    say(f"re-POST: {third[0]} {json.dumps(third[1], default=str)[:300]}")
    booked = [t for t in nw.get("/transfers", {"request_id": rid}).get("items", []) if t.get("request_id") == rid]
    for t in booked:
        if t["id"] not in made_t:
            made_t.append(t["id"])
    say(f"booked at Airwallex for {rid}: {len(booked)} -> {[t['id'] for t in booked]}")
    ids = {t["id"] for t in booked}
    for st, d in [o[:2] for o in out] + [third]:
        if st == 201:
            continue
        cls, msg = sdk_error(st, d)
        txt = mcp_text(st, msg)
        say(f"  SDK throws {cls}; MCP tool text: {txt!r}; details.id in body={((d.get('details') or {}).get('id') if isinstance(d.get('details'), dict) else None) in ids}; "
            f"original_id_in_tool_text={any(i in txt for i in ids)}")


def cleanup():
    say("\n== cleanup")
    for x in made_t:
        st = "?"
        for i in range(5):
            try:
                nw.post(f"/transfers/{x}/cancel", "PRB cleanup")
            except AwxError as e:
                say(f"  cancel {x}: {e.status} {e.code}")
            st = nw.get(f"/transfers/{x}").get("status")
            if st in ("CANCELLED", "FAILED"):
                break
            time.sleep(3 * (i + 1))
        if st not in ("CANCELLED", "FAILED"):
            try:
                nw.post(f"/simulation/transfers/{x}/transition", {"status": "FAILED"})
            except AwxError as e:
                say(f"  transition {x}: {e.status} {e.code}")
            st = nw.get(f"/transfers/{x}").get("status")
        say("transfer", x, st)
    for b in made_b:
        try:
            nw.post(f"/beneficiaries/{b}/delete", {})
            say("beneficiary deleted", b)
        except AwxError as e:
            say(f"beneficiary {b} delete: {e.status} {e.code}")


if __name__ == "__main__":
    try:
        part_live_get()
        part_live_409()
    finally:
        cleanup()
