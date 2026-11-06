"""Ringfence arm of node-sdk-retry-reconcile (offline, fake Airwallex).
The SDK's retried reconcile GET arrives without ?request_id= (node-sdk 2.1.0-beta.5 apiClient.js:157), so the
account's whole transfer page comes back. Here the fake ignores request_id on GET /transfers for EVERY call (worse
than one dropped retry), and we check Ringfence still neither adopts an unrelated transfer nor double-pays.
  uv run python bench/probes/probe_reconcile_filter_ignored.py"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "tests")]
os.environ["RF_VAR"] = tempfile.mkdtemp(prefix="rfprobe-")  # before ringfence reads var_dir()
os.environ.setdefault("RF_MANDATE_KEY", "probe-mandate-key")
os.environ.setdefault("RF_APPROVAL_KEY", "probe-approval-key")

from helpers import acct, new_run  # noqa: E402

import ringfence.verify  # noqa: E402
from ringfence import store  # noqa: E402
from ringfence.awx import Awx  # noqa: E402
from ringfence.config import tenants  # noqa: E402
from ringfence.executor import Executor  # noqa: E402
from ringfence.fake_awx import FakeAirwallex  # noqa: E402
from ringfence.ledger import Ledger  # noqa: E402

ringfence.verify.PUB_PATH = Path(os.environ["RF_VAR"]) / "cert_pub.pem"  # never touch the published key


class FilterIgnoringFake(FakeAirwallex):
    def _list_transfers(self, a, qs):
        return super()._list_transfers(a, {k: v for k, v in qs.items() if k != "request_id"})


fake = FilterIgnoringFake({k: t.account_id for k, t in tenants(fake=True).items()})
awx = Awx(transport=fake.transport, tenant_map=tenants(fake=True), sleep=lambda s: None)
L = Ledger()
ex = Executor(awx, L, sleep=lambda s: None)
kc = awx.for_tenant("kestrel")
n = lambda: len(fake.all_transfers(acct("kestrel")))  # noqa: E731

r1 = new_run(awx, L, "kestrel", run_id="20261114-prb001")
print("run1 (clean):", ex.release(r1, "kestrel"), "transfers:", n())

page = kc.get("/transfers", {"request_id": "prb-missing-000001"}).get("items", [])
hit = kc.transfer_by_request("prb-missing-000001")
print(f"filterless page for a never-used request_id: items={len(page)} naive_says_paid={len(page) > 0} ringfence_lookup={hit}")
assert len(page) > 0 and hit is None

for rid, fault in (("20261114-prb002", ("error_before_commit", {"status": 500, "n": 1})),
                   ("20261114-prb003", ("timeout_after_commit", {"n": 1}))):
    before = n()
    new_run(awx, L, "kestrel", run_id=rid)
    fake.inject(fault[0], **fault[1])
    st = ex.release(rid, "kestrel")
    lines = store.get_lines(L, rid, "kestrel")
    mine = [t for t in fake.all_transfers(acct("kestrel")) if t["request_id"] in {ln["request_id"] for ln in lines}]
    adopted_ok = all(ln.get("transfer_id") in {t["id"] for t in mine} for ln in lines)
    print(f"{rid} fault={fault[0]}: {st} new_transfers={n() - before} lines={[ln['state'] for ln in lines]} "
          f"each_line_adopted_its_own_transfer={adopted_ok}")
    assert n() - before == len(lines) == len(mine) and adopted_ok

rids = [t["request_id"] for t in fake.all_transfers(acct("kestrel"))]
assert len(rids) == len(set(rids))
print(f"RESULT ringfence_lookup_none={hit is None} total_transfers={n()} duplicates={len(rids) - len(set(rids))} ledger_ok={L.verify().ok}")
