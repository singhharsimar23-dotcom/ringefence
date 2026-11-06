"""Ringfence arm, offline: the same 'build employer A's client, then employer B's, then check A's status' sequence that
sends A's batch-items GET with B's bearer in @airwallex/node-sdk (node_sdk_batch_binding.js). Fake transport mirrors live:
items list of a batch the bearer does not own -> 200 {"items": []}.
  uv run python bench/probes/rf_batch_binding_offline.py"""
import json
import os
import sys
import tempfile
from pathlib import Path

os.environ.setdefault("RF_VAR", tempfile.mkdtemp(prefix="rf_prb_bx_off_"))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import httpx  # noqa: E402

from ringfence.awx import Awx  # noqa: E402

OWNER = {"batch_NW": "acct_FAKE_northwind"}
sent = []


def handler(req: httpx.Request) -> httpx.Response:
    if req.url.path.endswith("/authentication/login"):
        return httpx.Response(201, json={"token": "tok_for_" + req.headers["x-login-as"]})
    acct = req.headers["authorization"].removeprefix("Bearer tok_for_")
    sent.append((req.url.path, acct))
    bid = req.url.path.split("/batch_transfers/")[1].split("/")[0]
    return httpx.Response(200, json={"items": [{"status": "BOOKED"}] if OWNER.get(bid) == acct else []})


awx = Awx(transport=httpx.MockTransport(handler), sleep=lambda s: None)
nw = awx.for_tenant("northwind")
ks = awx.for_tenant("kestrel")  # built second, like the next employer's job
r = nw.get("/batch_transfers/batch_NW/items")
path, acct = sent[-1]
print("northwind client GET items -> sent as", acct, "| response", json.dumps(r))
assert acct == nw.account_id and r["items"], "Ringfence sent A's status check under another binding"
assert awx.for_tenant("northwind") is nw and ks is not nw
print("RESULT wrong_binding=False (each TenantClient logs in with its own x-login-as; no shared module client)")
