"""OFFLINE Ringfence arm for the Airwallex Pay sibling-wallet repoint.

Live (sibling-wallet-repoint-airwallex-pay.out.txt): a DIGITAL_WALLET payout reaches PAID in <0.3s and
cannot be cancelled; the transfer's own beneficiary snapshot carries {type, digital_wallet} and NO
bank_details; every sibling Airwallex account is named 'Sandbox Business'.

This checks whether Ringfence's content-pinning defences cover that rail. They key off bank_details, so:
  A. _recall_redirected skips any snapshot with no bank_details  -> no PAID_TO_UNAPPROVED_ACCOUNT (fail open)
  B. verify.report's "human approved" check skips it too         -> Proof reports CLEAN (fail open)
  C. drifted() reads ["bank_details"] unguarded                  -> KeyError, not a named HOLD
  D. the payroll gate's tenant_ga_keys omits the platform GA     -> BENEFICIARY_IS_OTHER_TENANT_ACCOUNT never fires
     for a contractor repinned to the platform's own 041907/07371376 account

Run: uv run python bench/probes/probe_digital_wallet_recall.py   (sets its own temp RF_VAR; writes no money)
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import date
from pathlib import Path

os.environ.setdefault("RF_VAR", tempfile.mkdtemp(prefix="rf_dw_"))
os.environ.setdefault("RF_MANDATE_KEY", "probe-mandate-key")
os.environ.setdefault("RF_APPROVAL_KEY", "probe-approval-key")
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from ringfence import beneficiaries as ben  # noqa: E402
from ringfence import store, verify  # noqa: E402
from ringfence.awx import Awx  # noqa: E402
from ringfence.config import tenants  # noqa: E402
from ringfence.fake_awx import FakeAirwallex  # noqa: E402
from ringfence.orchestrator import Orchestrator  # noqa: E402
from ringfence.setup_demo import setup  # noqa: E402

PAY = date(2026, 11, 14)
WALLET_SNAPSHOT = {"type": "DIGITAL_WALLET",  # as live GET /transfers/{id} returns for an Airwallex Pay payout
                   "digital_wallet": {"account_name": "Sandbox Business", "id_type": "account_number",
                                      "id_value": "1032103325024976", "provider": "AIRWALLEX"}}
out: list[str] = []


def say(*a):
    line = " ".join(str(x) for x in a)
    print(line)
    out.append(line)


def build():
    os.environ["RF_VAR"] = tempfile.mkdtemp(prefix="rf_dw_")  # fresh ledger + registry per arm
    tmap = tenants(fake=True)
    fake = FakeAirwallex({k: t.account_id for k, t in tmap.items()})
    awx = Awx(transport=fake.transport, tenant_map=tmap, sleep=lambda s: None)
    from ringfence.ledger import Ledger
    L = Ledger()
    reg = setup(awx)
    o = Orchestrator(awx, L)
    o.ex._sleep = lambda s: None
    return fake, awx, L, o, reg, tmap


def acct(tmap, tenant):
    return tmap[tenant].account_id


def arm_a_b_recall_and_proof():
    """Release a kestrel run, then make the transfer look like an Airwallex Pay payout (no bank_details).
    Assert recall is a no-op and Proof stays clean -- the fail-open on the wallet rail."""
    fake, awx, L, o, reg, tmap = build()
    rid = o.create_run("kestrel", PAY)
    assert o.submit(rid, "kestrel") == "READY"
    assert o.advance(rid, "kestrel") == "RELEASED"
    ka = acct(tmap, "kestrel")
    tids = list(fake.accounts[ka].transfers)
    # the payee was an Airwallex Pay wallet all along: the live snapshot has {type, digital_wallet}, no bank_details
    for tid in tids:
        fake.set_status(ka, tid, "PAID", beneficiary=dict(WALLET_SNAPSHOT))

    alerts_before = [e for e in L.entries(kind="ALERT") if e["payload"].get("what") == "PAID_TO_UNAPPROVED_ACCOUNT"]
    c = awx.for_tenant("kestrel")
    o._recall_redirected(c, rid, "kestrel")
    alerts_after = [e for e in L.entries(kind="ALERT") if e["payload"].get("what") == "PAID_TO_UNAPPROVED_ACCOUNT"]
    statuses = {fake.accounts[ka].transfers[t]["status"] for t in tids}
    say("A. recall on a no-bank_details (DIGITAL_WALLET) snapshot:")
    say("   PAID_TO_UNAPPROVED_ACCOUNT alerts added by recall:", len(alerts_after) - len(alerts_before))
    say("   transfer statuses after recall:", statuses, "(none CANCELLED -> not recalled)")
    assert len(alerts_after) == len(alerts_before), "recall unexpectedly alerted"
    assert statuses == {"PAID"}, "recall unexpectedly cancelled a wallet payout"

    rep = verify.report(awx, L)
    kchecks = rep["tenants"]["kestrel"]["checks"]
    approved_chk = next(c for c in kchecks if "human approved" in c["name"])
    say("B. Proof on the same run: tenant ok =", rep["tenants"]["kestrel"]["ok"],
        "| 'human approved' check ok =", approved_chk["ok"])
    assert approved_chk["ok"], "Proof flagged the wallet payout (good) -- expected fail-open"
    say("   => FAIL OPEN confirmed: a wallet-rail redirect is invisible to both recall and Proof.\n")


def arm_c_drifted_keyerror():
    """A live beneficiary flipped to the Airwallex Pay (DIGITAL_WALLET) shape makes drifted() raise KeyError,
    so the release path crashes instead of raising a named HOLD."""
    fake, awx, L, o, reg, tmap = build()
    rid = o.create_run("kestrel", PAY)
    o.submit(rid, "kestrel")
    lines = store.get_lines(L, rid, "kestrel", states=("READY",))
    ka = acct(tmap, "kestrel")
    bid = lines[0]["beneficiary_id"]
    fake.accounts[ka].beneficiaries[bid]["beneficiary"] = dict(WALLET_SNAPSHOT)  # live now returns a wallet payee
    c = awx.for_tenant("kestrel")
    raised = None
    try:
        ben.drifted(c, "kestrel", lines)
    except KeyError as e:
        raised = e
    say("C. drifted() on a live DIGITAL_WALLET beneficiary raised:", type(raised).__name__ if raised else None)
    assert isinstance(raised, KeyError), "drifted() did not raise KeyError on a bank_details-less payee"
    say("   => no named HOLD; the release path raises an unhandled KeyError (fails closed only by crashing).\n")


def arm_d_platform_ga_gate():
    """A contractor repinned to the platform's OWN global account (041907/07371376) passes gate check 7,
    because tenant_ga_keys is built from employer GAs only and omits the platform."""
    fake, awx, L, o, reg, tmap = build()
    gak = ben.all_ga_keys(reg)
    say("D. platform GA 07371376 in all_ga_keys(reg)?", "07371376" in gak,
        "| reg tenants:", list(reg["tenants"]))
    assert "07371376" not in gak, "platform GA is in all_ga_keys -- gate would catch it (claim refuted)"

    # Drive it through the real release gate: repin a contractor to the platform GA, then check the decision.
    from ringfence import gate
    rid = o.create_run("kestrel", PAY)
    o.submit(rid, "kestrel")
    ready = store.get_lines(L, rid, "kestrel", states=("READY",))
    run = store.get_run(L, rid, "kestrel")
    c = awx.for_tenant("kestrel")
    # point the first line's live beneficiary + pin at the platform GA (sort 041907, acct 07371376)
    bid = ready[0]["beneficiary_id"]
    plat_bd = {"bank_country_code": "GB", "account_currency": "GBP", "account_name": "Sandbox Business",
               "bank_name": "Airwallex", "account_routing_type1": "sort_code", "account_routing_value1": "041907",
               "account_number": "07371376"}
    c.post(f"/beneficiaries/{bid}/update", {"transfer_methods": ["LOCAL"],
                                            "beneficiary": {"bank_details": plat_bd}})
    regw = ben.load_registry()
    regw["tenants"]["kestrel"].setdefault("pins", {})[bid] = ben.fingerprint(plat_bd)  # server-owned pin now matches
    ben.save_registry(regw)
    with L.tx() as tx:  # put the run in RELEASING so the gate passes check 1 and actually reaches check 7
        store.set_run(tx, rid, "kestrel", state="RELEASING")
    run = store.get_run(L, rid, "kestrel")
    facts, _ = o.ex._facts(c, run, ready)
    d = gate.check_release(facts)
    code = getattr(d, "code", "ALLOW")
    say("   gate decision for a platform-GA payee:", type(d).__name__, "code=", code)
    assert code != "BENEFICIARY_IS_OTHER_TENANT_ACCOUNT", "gate caught the platform GA (claim refuted)"
    say("   => the platform's own account is NOT in the payroll gate's other-tenant set; check 7 does not fire.\n")


def main():
    arm_a_b_recall_and_proof()
    arm_c_drifted_keyerror()
    arm_d_platform_ga_gate()
    say("ALL OFFLINE ASSERTIONS PASSED: Ringfence fails open on the Airwallex Pay (DIGITAL_WALLET) rail.")
    Path(__file__).with_suffix(".out.txt").write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    main()
