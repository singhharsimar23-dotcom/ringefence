"""READ-ONLY probe: GET /transfers ignores page_num live, so a guide-following reconcile (page_num/page_size) sees page 1 forever.
Ringfence's Proof (verify._transfers) pages the same way.

    export MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8
    uv run python bench/probes/probe_transfers_paging.py            # live (read-only) + offline
    uv run python bench/probes/probe_transfers_paging.py --offline  # offline only

No writes anywhere. Prints counts and sha256 of id sets only, never tokens.
"""
from __future__ import annotations

import hashlib
import os
import sys
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
os.environ.setdefault("RF_VAR", tempfile.mkdtemp(prefix="rf_probe_paging_"))
sys.stdout.reconfigure(encoding="utf-8")


def h(ids) -> str:
    return hashlib.sha256(",".join(sorted(ids)).encode()).hexdigest()[:16]


class Counting:
    """Stands in for a TenantClient: _transfers only calls .get. Raises once stopped or capped so no thread lingers."""

    def __init__(self, inner, cap=None):
        self.inner, self.cap, self.n, self.stop, self.pages = inner, cap, 0, False, []

    def get(self, path, params=None):
        if self.stop or (self.cap is not None and self.n >= self.cap):
            raise RuntimeError(f"stopped after {self.n} GETs")
        self.n += 1
        r = self.inner.get(path, params)
        self.pages.append(h(t["id"] for t in r.get("items", [])))
        return r


def cursor_transfers(c, since: str | None = None) -> list[dict]:
    """The fix: page=0 starts a cursor (and lifts the 30-day default), then follow page_after until absent."""
    out, seen, page = [], set(), "0"
    while True:
        p = {"page": page, "page_size": 100}
        if since:
            p["from_created_at"] = since
        r = c.get("/transfers", p)
        for t in r.get("items", []):
            if t["id"] not in seen:  # a cursor should never repeat, but never trust it to
                seen.add(t["id"])
                out.append(t)
        page = r.get("page_after")
        if not page:
            return out


def guide_reconcile(c, payroll: dict[str, str]) -> list[str]:
    """Reference integrator per the payouts guide: page_num/page_size until has_more is false or a page adds nothing new.
    Returns payees with no transfer seen (what a re-pay job would pay again)."""
    seen, page = {}, 0
    while True:
        r = c.get("/transfers", {"page_num": page, "page_size": 100})
        new = [t for t in r.get("items", []) if t["id"] not in seen]
        for t in new:
            seen[t["id"]] = t
        if not new or not r.get("has_more"):
            break
        page += 1
    paid = {t.get("request_id") for t in seen.values()}
    return [p for p, rid in payroll.items() if rid not in paid]


# -- live (read-only) --------------------------------------------------------------------------------
def live() -> None:
    import awx
    A, B = awx.env("AWX_EMPLOYER_A"), awx.env("AWX_EMPLOYER_B")

    def get(q, acct=A):
        code, d = awx.call("GET", "/transfers" + (f"?{q}" if q else ""), login_as=acct)
        assert code == 200, (q, code, str(d)[:200])
        return d

    print("== 2) page_num under Northwind, page_size=100")
    sets = []
    for n in (0, 1, 2):
        d = get(f"page_num={n}&page_size=100")
        ids = [t["id"] for t in d["items"]]
        sets.append(set(ids))
        print(f"page_num={n}: n={len(ids)} sha={h(ids)} has_more={d.get('has_more')} page_after={'yes' if d.get('page_after') else 'no'}")
    print("identical:", sets[0] == sets[1] == sets[2])
    for n in (0, 1):
        d = get(f"page_num={n}&page_size=10")
        print(f"page_num={n}&page_size=10: n={len(d['items'])} sha={h(t['id'] for t in d['items'])}")

    print("== 3) cursor page=0 then page_after")
    allids, page, counts = [], "0", []
    while True:
        d = get(f"page={page}&page_size=100")
        counts.append(len(d["items"]))
        allids += [t["id"] for t in d["items"]]
        page = d.get("page_after")
        if not page:
            break
    print("per-page:", counts, "total:", len(allids), "unique:", len(set(allids)),
          "overlap with page_num page:", len(set(allids[:counts[0]]) & sets[0]), "/", len(sets[0]),
          "beyond page 1 overlap with page_num set:", len(set(allids[counts[0]:]) & sets[0]))

    print("== 4) defaults")
    print("no params: n=", len(get("")["items"]))
    print("page_num=0&page_size=2000 (guide's own example size): n=", len(get("page_num=0&page_size=2000")["items"]))
    old = [t for t in get("page=0&page_size=2000")["items"]]
    cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    print("page=0&page_size=2000: n=", len(old), "created >30 days ago:", sum(t["created_at"] < cutoff for t in old))

    print("== 5) request_id lookup")
    rid = next(t["request_id"] for t in get("page=0&page_size=100")["items"] if t.get("request_id"))
    print("request_id only: n=", len(get(f"request_id={rid}")["items"]),
          "| with page=0: n=", len(get(f"request_id={rid}&page=0")["items"]))

    print("== multi-account: Kestrel")
    k0, k1 = get("page_num=0&page_size=10", B), get("page_num=1&page_size=10", B)
    print("Kestrel page_num 0 vs 1 (size 10) identical:", h(t['id'] for t in k0['items']) == h(t['id'] for t in k1['items']),
          "n=", len(k0["items"]))

    print("== 8 live) guide reconcile over Northwind's whole history")
    from ringfence import awx as R
    c = R.Awx().for_tenant("northwind")
    truth = cursor_transfers(c)
    payroll = {t["id"]: t["request_id"] for t in truth if t.get("request_id")}  # every real transfer stands in for a payee
    unpaid = guide_reconcile(c, payroll)
    print(f"transfers={len(truth)} guide reconcile reports unpaid={len(unpaid)} (each one exists and is not FAILED/CANCELLED: "
          f"{sum(t['status'] not in ('FAILED', 'CANCELLED') for t in truth if t['id'] in set(unpaid))})")

    print("== 6) Ringfence Proof: verify._transfers live")
    from ringfence import verify
    since = "2026-11-01T00:00:00Z"
    n_since = len(cursor_transfers(c, since))
    print("Northwind transfers since", since, "via cursor:", n_since)
    w = Counting(c)
    res = {}
    th = threading.Thread(target=lambda: res.setdefault("out", verify._transfers(w, since)), daemon=True)
    th.start()
    th.join(30)
    alive = th.is_alive()
    w.stop = True
    th.join(10)
    print(f"alive_after_30s={alive} GETs={w.n} distinct_pages={len(set(w.pages))} returned={len(res['out']) if 'out' in res else None}")


# -- offline ------------------------------------------------------------------------------------------
def offline() -> None:
    from ringfence.awx import Awx
    from ringfence.config import tenants
    from ringfence.fake_awx import FakeAirwallex, _json
    from ringfence.money import loads_money
    from ringfence import verify

    class LiveLikeFake(FakeAirwallex):
        """Like live 6 Nov: page_num is ignored, page is a cursor, the next cursor comes back as page_after."""

        def _list_transfers(self, a, qs):
            qs = {k: v for k, v in qs.items() if k != "page_num"}
            page = qs.pop("page", None)
            start = 0 if page in (None, "0") else int(page.removeprefix("cur-"))
            size = int(qs.get("page_size", 2000))
            r = super()._list_transfers(a, {**qs, "page_size": 10 ** 9})
            allitems = loads_money(r.content)["items"]  # not r.json(): money stays Decimal
            items = allitems[start:start + size]
            body = {"items": items}
            if page is not None and start + size < len(allitems):
                body["page_after"] = f"cur-{start + size}"
            return _json(200, body)

    ts = tenants(fake=True)
    fake = LiveLikeFake({k: t.account_id for k, t in ts.items()})
    awx = Awx(transport=fake.transport, tenant_map=ts, sleep=lambda s: None)
    acct = fake.accounts[ts["northwind"].account_id]
    base = datetime(2026, 11, 6, 9, 0, tzinfo=timezone.utc)
    payroll = {}
    for i in range(150):
        rid = f"PRB-paging-{i:04d}"
        acct.transfers[f"tr_prb_{i:04d}"] = {
            "id": f"tr_prb_{i:04d}", "request_id": rid, "status": "SCHEDULED", "beneficiary_id": f"ben_{i}",
            "transfer_amount": Decimal("1.00"), "transfer_currency": "GBP", "created_at": (base + timedelta(seconds=i)).isoformat()}
        payroll[f"payee-{i:04d}"] = rid
    c = awx.for_tenant("northwind")

    print("== 7) offline: Ringfence verify._transfers against a live-like fake, 150 transfers, cap 10 GETs")
    w = Counting(c, cap=10)
    try:
        verify._transfers(w, "2026-11-01T00:00:00Z")
        hit = False
    except RuntimeError:
        hit = True
    print(f"cap_hit={hit} GETs={w.n} distinct_pages={len(set(w.pages))}")
    assert hit and len(set(w.pages)) == 1

    fixed = cursor_transfers(c, "2026-11-01T00:00:00Z")
    print("fix (page=0 then page_after):", len(fixed), "unique:", len({t['id'] for t in fixed}))
    assert len({t["id"] for t in fixed}) == 150

    # The repo's own fake honours page_num, which is why tests pass; and it cannot run the fix (no page_after).
    plain = FakeAirwallex({k: t.account_id for k, t in ts.items()})
    plain.accounts[ts["northwind"].account_id].transfers.update(acct.transfers)
    pc = Awx(transport=plain.transport, tenant_map=ts, sleep=lambda s: None).for_tenant("northwind")
    print("repo FakeAirwallex: verify._transfers =", len(verify._transfers(pc, "2026-11-01T00:00:00Z")),
          "| cursor fix =", len(cursor_transfers(pc, "2026-11-01T00:00:00Z")))

    print("== 8) offline: guide-following reconcile, 150-payee payroll")
    unpaid = guide_reconcile(c, payroll)
    print("reported unpaid:", len(unpaid), "(all 150 were paid)")
    assert len(unpaid) == 50
    print("with the cursor fix:", sum(rid not in {t["request_id"] for t in fixed} for rid in payroll.values()))


if __name__ == "__main__":
    if "--offline" not in sys.argv:
        live()
    offline()
