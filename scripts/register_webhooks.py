"""Register (idempotently) one Airwallex webhook per employer account, pointing at the public Ringfence URL.

    uv run python scripts/register_webhooks.py https://<host>/webhooks/airwallex | sudo tee -a /etc/ringfence/env >/dev/null

stdout gets exactly one line, `AWX_WEBHOOK_SECRET=s1,s2,s3`, meant to be piped into the root-only env file, so the
secrets never reach a terminal. Progress (no secrets) goes to stderr. Each webhook is created with THAT employer's
own token; Ringfence verifies a signature against any of the secrets, then re-fetches the transfer (a hint, not truth).
"""
from __future__ import annotations

import hashlib
import sys

from ringfence.awx import AwxError, build_backend
from ringfence.config import EMPLOYERS

VERSION = "2025-02-14"
PAYOUT = [f"payout.transfer.{s}" for s in ("scheduled", "overdue", "processing", "sent", "paid", "failed", "cancelled")]
DEPOSIT = ["deposit.settled", "deposit.rejected", "deposit.reversed"]


def ensure(c, url: str) -> str:
    items = c.get("/webhooks", {"page_num": 0, "page_size": 100}).get("items", [])
    hit = next((w for w in items if w.get("url") == url), None)
    if hit:
        print(f"{c.tenant_key}: already registered ({hit.get('id')})", file=sys.stderr)
        return hit["secret"]
    body = {"request_id": f"rf-wh-{c.tenant_key}-{hashlib.sha256(url.encode()).hexdigest()[:12]}", "url": url, "version": VERSION}
    try:
        w = c.post("/webhooks/create", {**body, "events": PAYOUT + DEPOSIT})
    except AwxError as e:  # deposit event names may not be allowed for this key's scopes: payouts are what matter
        print(f"{c.tenant_key}: full event list refused ({e.code}); retrying with payout events only", file=sys.stderr)
        w = c.post("/webhooks/create", {**body, "request_id": body["request_id"] + "p", "events": PAYOUT})
    print(f"{c.tenant_key}: created {w.get('id')} events={len(w.get('events', []))}", file=sys.stderr)
    return w["secret"]


def main() -> int:
    if len(sys.argv) != 2 or not sys.argv[1].startswith("https://"):
        print(__doc__, file=sys.stderr)
        return 2
    awx, _ = build_backend("live")
    secrets = [ensure(awx.for_tenant(t), sys.argv[1]) for t in EMPLOYERS]
    print("AWX_WEBHOOK_SECRET=" + ",".join(secrets))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
