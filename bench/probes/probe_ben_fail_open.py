"""beneficiary-reads-fail-open: Airwallex's recommended dedupe (list by company_name) and existence check (GET by id).
Live mode (default): writes only on Northwind (A) and one rejected-or-cancelled 1.00 GBP create on Kestrel (B).
Prints nicknames, last-4, codes and counts only. --offline runs the Ringfence arm against a fake Airwallex.
Usage: uv run python bench/probes/probe_ben_fail_open.py [--offline]"""
import json
import os
import sys
import tempfile
import time
from decimal import Decimal

sys.path.insert(0, "scripts")
import awx  # noqa: E402

AMOUNT = Decimal("1.00")  # <= 5.00 per move, 2 money moves total


def last4(b):
    bd = (b or {}).get("beneficiary", {}).get("bank_details", {})
    return (bd.get("account_number") or bd.get("iban") or "")[-4:]


def lst(label, q, who):
    code, d = awx.call("GET", f"/beneficiaries?{q}&page_num=0&page_size=100", login_as=who)
    items = d.get("items", []) if isinstance(d, dict) else []
    print(f"{label} ?{q} -> HTTP {code} n={len(items)} total={d.get('total_count') if isinstance(d, dict) else d!s:.120}")
    return items


def one(label, path, who):
    code, d = awx.call("GET", path, login_as=who)
    body = "EMPTY" if d in ("", None, {}) else (f"nick={d.get('nickname')} last4={last4(d)}" if isinstance(d, dict) else str(d)[:120])
    print(f"{label} GET {path.split('/')[-1][:8]}.. -> HTTP {code} body={body}")
    return code, d


def create_transfer(label, who, bid, rid):
    body = {"request_id": rid, "beneficiary_id": bid, "transfer_amount": str(AMOUNT), "transfer_currency": "GBP",
            "source_currency": "GBP", "transfer_method": "LOCAL", "reason": "professional_business_services",
            "reference": "PRB fail-open"}
    code, d = awx.call("POST", "/transfers/create", body, login_as=who)
    print(f"{label} create -> HTTP {code} code={d.get('code') if isinstance(d, dict) else None} "
          f"msg={(d.get('message') if isinstance(d, dict) else str(d))!s:.160}")
    if 200 <= code < 300:
        tid = d.get("id")
        print(f"  !!! 2xx, transfer {tid} status={d.get('status')}; cancelling")
        for i in range(4):
            cc, cd = awx.call("POST", f"/transfers/{tid}/cancel", None, login_as=who)
            st = awx.call("GET", f"/transfers/{tid}", login_as=who)[1].get("status")
            print(f"  cancel try {i}: HTTP {cc} status now {st}")
            if st == "CANCELLED":
                break
            time.sleep(2 ** i)
        else:
            print("  sim FAILED:", awx.call("POST", f"/simulation/transfers/{tid}/transition",
                                            {"next_status": "FAILED"}, login_as=who)[0])
    return code, d


def live():
    A, B = awx.env("AWX_EMPLOYER_A"), awx.env("AWX_EMPLOYER_B")
    ada = json.load(open("var/registry.json"))["tenants"]["northwind"]["beneficiaries"]["ada"]
    print("== 1) read-only filter + existence checks")
    every = lst("A all", "x=1", A)
    lst("A", "company_name=ZZZZNOPE", A)
    lst("A", "name=ZZZZNOPE", A)
    lst("A", "nick_name=ZZZZNOPE", A)        # documented spelling
    lst("A", "nickname=ZZZZNOPE", A)         # common misspelling (unknown param)
    lst("A", "bank_account_number=99999999", A)
    lst("A", "entity_type=COMPANY", A)
    one("B token, A's ada:", f"/beneficiaries/{ada}", B)
    one("B token, random uuid:", "/beneficiaries/00000000-0000-4000-8000-000000000000", B)
    one("A token, A's ada (control):", f"/beneficiaries/{ada}", A)

    print("== 2) create COMPANY 'Probe Co' under A")
    ep = int(time.time())
    acct = f"{ep % 100000000:08d}"
    p = {"nickname": f"PRB-beneficiary-reads-fail-open-probeco-{ep}", "transfer_methods": ["LOCAL"], "beneficiary": {
        "entity_type": "COMPANY", "company_name": "Probe Co",
        "address": {"country_code": "GB", "city": "London", "street_address": "1 Probe St", "postcode": "EC1A 1BB"},
        "bank_details": {"bank_country_code": "GB", "account_currency": "GBP", "account_name": "Probe Co",
                         "bank_name": "Probe Bank", "account_routing_type1": "sort_code",
                         "account_routing_value1": "040004", "account_number": acct}}}
    code, d = awx.call("POST", "/beneficiaries/create", p, login_as=A)
    bid = d.get("id") if isinstance(d, dict) else None
    print(f"create -> HTTP {code} id={bid} {'' if bid else str(d)[:200]}")
    if not bid:
        return
    try:
        code, g = one("A token, Probe Co:", f"/beneficiaries/{bid}", A)
        print("  stored company_name:", repr(g.get("beneficiary", {}).get("company_name")) if isinstance(g, dict) else None)
        hits = lst("A", "company_name=Probe%20Co", A)
        print("  Probe Co in results:", any(i.get("beneficiary_id", i.get("id")) == bid for i in hits),
              "| first item nick:", hits[0].get("nickname") if hits else None, "| all=", len(every) + 1)
        lst("A", "company_name=Probe", A)
        lst("A", "name=Probe%20Co", A)
        lst("A", f"bank_account_number={acct}", A)

        print("== 3) KEY: B creates a transfer to A's Probe Co id")
        c3, d3 = create_transfer("B -> A/ProbeCo", B, bid, f"prb-xben-{ep}")
        if 200 <= c3 < 300:
            print("CROSS_TENANT_2XX")

        print("== 5) skill-following dedupe for new supplier 'Acme Design Ltd' (read-only)")
        m = lst("A", "company_name=Acme%20Design%20Ltd", A)
        if m:
            x = m[0]
            print(f"  skill says 'match exists -> update': would update nick={x.get('nickname')} "
                  f"entity={x.get('beneficiary', {}).get('entity_type')} "
                  f"company={x.get('beneficiary', {}).get('company_name')!r} last4={last4(x)}")
        m2 = lst("A", "name=Acme%20Design%20Ltd", A)
        print("  name filter (control) match count:", len(m2))
    finally:
        print("== 4) delete Probe Co, then re-check")
        code, d = awx.call("POST", f"/beneficiaries/{bid}/delete", None, login_as=A)
        print(f"delete -> HTTP {code} {str(d)[:120]}")
        one("A token, deleted Probe Co:", f"/beneficiaries/{bid}", A)
        create_transfer("A -> deleted ProbeCo", A, bid, f"prb-xdel-{ep}")
        print("== 7) cleanup check")
        print("  Probe Co still listed:", any(i.get("beneficiary_id", i.get("id")) == bid for i in lst("A", "x=1", A)))


def offline():
    os.environ["RF_VAR"] = tempfile.mkdtemp(prefix="prb-bfo-")
    os.environ.setdefault("RF_MANDATE_KEY", "prb-mandate-key")
    os.environ.setdefault("RF_APPROVAL_KEY", "prb-approval-key")
    sys.path.insert(0, ".")
    sys.path.insert(0, "tests")
    import httpx
    import ringfence.verify
    from pathlib import Path
    ringfence.verify.PUB_PATH = Path(os.environ["RF_VAR"]) / "cert_pub.pem"
    from ringfence import beneficiaries as ben, store
    from ringfence.awx import Awx, AwxError, TenantClient
    from ringfence.config import tenants
    from ringfence.fake_awx import FakeAirwallex
    from ringfence.ledger import Ledger
    from ringfence.orchestrator import Orchestrator
    from helpers import new_run

    class EmptyOk(FakeAirwallex):
        """Live behaviour (step 1): GET /beneficiaries/{id} for an id this tenant does not own is 200 with no body."""
        def _route(self, req):
            r = super()._route(req)
            if req.method == "GET" and "/beneficiaries/" in req.url.path and r.status_code == 404:
                return httpx.Response(200, content=b"")
            return r

    def trial(patched, direct=False):
        os.environ["RF_VAR"] = tempfile.mkdtemp(prefix="prb-bfo-")
        fake = EmptyOk({k: t.account_id for k, t in tenants(fake=True).items()})
        a = Awx(transport=fake.transport, tenant_map=tenants(fake=True), sleep=lambda s: None)
        L = Ledger()
        o = Orchestrator(a, L, cert_dir=Path(os.environ["RF_VAR"]) / f"certs{int(patched)}")
        run = new_run(a, L, "northwind", run_id=f"20261114-prbbfo{int(patched)}{int(direct)}")
        reg = ben.load_registry()
        # the payee was deleted on Airwallex (or the id is another employer's): Airwallex answers 200 empty
        gone = reg["tenants"]["northwind"]["beneficiaries"]["ada"]
        fake_acct = next(x for x in fake.accounts.values() if gone in x.beneficiaries)
        del fake_acct.beneficiaries[gone]
        orig = TenantClient.get
        if patched:
            def get(self, path, params=None):
                d = orig(self, path, params)
                if d is None and path.startswith("/beneficiaries/"):
                    raise AwxError(404, "not_found", "empty 200 for a beneficiary: not this tenant's")
                return d
            TenantClient.get = get
        try:
            try:
                st, err = (o.ex.release if direct else o.advance)(run, "northwind"), None
            except Exception as e:  # noqa: BLE001
                st, err = None, f"{type(e).__name__}: {e}"
        finally:
            TenantClient.get = orig
        r = store.get_run(L, run, "northwind")
        rows = [(e["kind"], e["payload"].get("code") or e["payload"].get("what")) for e in L.entries(tenant="northwind")
                if e["kind"] in ("HOLD", "ALERT", "GATE_DENY")]
        sub = [e for e in L.entries(tenant="northwind") if e["kind"] == "SUBMITTED"]
        if direct:  # does the next tick (or a retry click) un-stick it?
            print(f"  next advance() -> {o.advance(run, 'northwind')}; release() again -> {o.ex.release(run, 'northwind')}")
        print(f"[{'patched' if patched else 'today'}{' executor.release' if direct else ' orchestrator.advance'}] advance -> {st} exc={err} run.state={r['state']} "
              f"hold={r.get('hold_reason')} hold/alert/deny={rows} submitted={len(sub)}")
        return r, rows, err, sub

    r, rows, err, sub = trial(False)
    assert err and "TypeError" in err, "expected TypeError to escape today"
    assert not rows and r["state"] == "READY" and not sub, "expected stuck READY, no named hold, nothing paid"
    r, rows, err, sub = trial(False, direct=True)  # the executor's own read (_facts L142), past drifted()
    assert err and "TypeError" in err and r["state"] == "RELEASING" and not rows, "expected RELEASING lock with no hold"
    r, rows, err, sub = trial(True)
    assert err is None, err
    print("  patched result:", r["state"], r.get("hold_reason"), rows)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    if "--followup" not in sys.argv:
        offline() if "--offline" in sys.argv else live()


def followup():
    """Step 3/4 said only 'validation_failed': print the errors object, and run a control with the same body on a valid id."""
    A, B = awx.env("AWX_EMPLOYER_A"), awx.env("AWX_EMPLOYER_B")
    ep = int(time.time())
    p = {"nickname": f"PRB-beneficiary-reads-fail-open-probeco2-{ep}", "transfer_methods": ["LOCAL"], "beneficiary": {
        "entity_type": "COMPANY", "company_name": "Probe Co",
        "address": {"country_code": "GB", "city": "London", "street_address": "1 Probe St", "postcode": "EC1A 1BB"},
        "bank_details": {"bank_country_code": "GB", "account_currency": "GBP", "account_name": "Probe Co",
                         "bank_name": "Probe Bank", "account_routing_type1": "sort_code",
                         "account_routing_value1": "040004", "account_number": f"{ep % 100000000:08d}"}}}
    code, d = awx.call("POST", "/beneficiaries/create", p, login_as=A)
    bid = d["id"]
    print(f"create -> HTTP {code} id={bid}")
    _, g = awx.call("GET", f"/beneficiaries/{bid}", login_as=A)
    print("  GET top keys:", sorted(g), "| beneficiary keys:", sorted(g.get("beneficiary", {})))
    print("  create-response beneficiary keys:", sorted(d.get("beneficiary", {})), "company_name in create resp:",
          repr(d.get("beneficiary", {}).get("company_name")))

    def tr(label, who, b, rid):
        body = {"request_id": rid, "beneficiary_id": b, "transfer_amount": str(AMOUNT), "transfer_currency": "GBP",
                "source_currency": "GBP", "transfer_method": "LOCAL", "reason": "professional_business_services",
                "reference": "PRB fail-open"}
        c, r = awx.call("POST", "/transfers/create", body, login_as=who)
        print(f"{label}: HTTP {c} code={r.get('code')} errors={json.dumps(r.get('errors') or r.get('details'))[:300]} "
              f"status={r.get('status')}")
        return c, r
    try:
        tr("B -> A/ProbeCo2", B, bid, f"prb-xben2-{ep}")
        tr("B -> random uuid", B, "00000000-0000-4000-8000-000000000000", f"prb-xrnd-{ep}")
        c, r = tr("A -> A/ProbeCo2 (control, same body)", A, bid, f"prb-ctrl-{ep}")
        if 200 <= c < 300:
            tid = r["id"]
            for i in range(4):
                cc, _ = awx.call("POST", f"/transfers/{tid}/cancel", None, login_as=A)
                st = awx.call("GET", f"/transfers/{tid}", login_as=A)[1].get("status")
                print(f"  control cancel try {i}: HTTP {cc} -> {st}")
                if st == "CANCELLED":
                    break
                time.sleep(2 ** i)
            else:
                cc, _ = awx.call("POST", f"/simulation/transfers/{tid}/transition", {"next_status": "FAILED"}, login_as=A)
                print("  control sim FAILED:", cc, awx.call("GET", f"/transfers/{tid}", login_as=A)[1].get("status"))
    finally:
        print("delete ->", awx.call("POST", f"/beneficiaries/{bid}/delete", None, login_as=A)[0])
        tr("A -> deleted ProbeCo2", A, bid, f"prb-xdel2-{ep}")
        print("still listed:", any(i.get("id") == bid for i in awx.call("GET", "/beneficiaries?page_num=0&page_size=100", login_as=A)[1]["items"]))


if __name__ == "__main__" and "--followup" in sys.argv:
    followup()
