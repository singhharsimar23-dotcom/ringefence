"""BUILD_SPEC section 11 invariants, checked from the ledger and the fake's own records after a scenario.
Independent of verify.py on purpose: a bug in the report must not hide a bug in the money path."""
from __future__ import annotations

import json
import os
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from ringfence import beneficiaries as ben
from ringfence import store
from ringfence.config import EMPLOYERS, tenants
from ringfence.money import FEE_PER_PAYOUT

DEAD = ("FAILED", "CANCELLED")


def _secrets(fake) -> list[str]:
    found = [t for t in fake.tokens if t]
    found += [os.environ[k] for k in ("RF_MANDATE_KEY", "RF_APPROVAL_KEY", "AWX_API_KEY") if os.environ.get(k)]
    return found


def _runs(L, tenant: str) -> set[str]:
    return {r["run_id"] for r in L.query("SELECT run_id FROM runs WHERE tenant=?", (tenant,))}


def assert_invariants(L, fake, *, chain: bool = True, cert_dir=None) -> None:
    acct = {t: tenants(fake=True)[t].account_id for t in EMPLOYERS}
    transfers = {t: list(fake.accounts[acct[t]].transfers.values()) for t in EMPLOYERS}
    intents = [e for e in L.entries(kind="INTENT")]
    by_req = {e["payload"]["request_id"]: e for e in intents}
    reg = ben.load_registry()["tenants"]

    # I1: nothing in account X belongs to tenant Y, and every payee is X's own beneficiary
    for t, ts in transfers.items():
        own = {*reg.get(t, {}).get("beneficiaries", {}).values(), reg.get(t, {}).get("fee_beneficiary")}
        for x in ts:
            owner = by_req.get(x["request_id"])
            assert owner is None or owner["tenant"] == t, f"I1: {x['id']} in {t} belongs to {owner['tenant']}"
            assert x["beneficiary_id"] in own, f"I1: {x['id']} in {t} pays a beneficiary that is not {t}'s"

    # I2: one transfer per request_id; at most one live transfer per (run, contractor, round)
    for t, ts in transfers.items():
        counts = defaultdict(int)
        for x in ts:
            counts[x["request_id"]] += 1
        assert all(n == 1 for n in counts.values()), f"I2: duplicate request_id in {t}: {dict(counts)}"
    live = defaultdict(int)
    for t, ts in transfers.items():
        for x in ts:
            e = by_req.get(x["request_id"])
            if e and x["status"] not in DEAD and e["payload"].get("contractor_id"):
                live[(e["run_id"], t, e["payload"]["contractor_id"])] += 1
    for t in EMPLOYERS:
        for run in _runs(L, t):
            returned = {ln["contractor_id"] for ln in store.get_lines(L, run, t, states=("RETURNED",))}
            for (r, tt, cid), n in live.items():
                if (r, tt) == (run, t):
                    assert n <= 1 or cid in returned, f"I2: {cid} has {n} live transfers in {t}"

    # I3: every transfer has an INTENT, every INTENT at most one transfer
    flat = [x for ts in transfers.values() for x in ts]
    assert all(x["request_id"] in by_req for x in flat), "I3: a transfer has no ledger INTENT"
    per_intent = defaultdict(int)
    for x in flat:
        per_intent[x["request_id"]] += 1
    assert all(n <= 1 for n in per_intent.values()), "I3: an INTENT produced more than one transfer"

    # I4: the chain verifies
    if chain:
        v = L.verify(cert_dir) if cert_dir else L.verify()
        assert v.ok, f"I4: {v.reason} at {v.bad_seq}"

    # I5: what was paid equals what the ledger intended, and non-fee intents equal the run's line, to the cent
    lines = {}
    for t in EMPLOYERS:
        for run in _runs(L, t):
            for ln in store.get_lines(L, run, t):
                lines[ln["request_id"]] = ln
    for x in flat:
        p = by_req[x["request_id"]]["payload"]
        assert Decimal(str(x["transfer_amount"])) == Decimal(p["amount"]) and x["transfer_currency"] == p["currency"], \
            f"I5: {x['id']} amount differs from its INTENT"
        ln = lines.get(x["request_id"])
        if ln:
            assert Decimal(ln["amount"]) == Decimal(p["amount"]) and ln["currency"] == p["currency"], f"I5: line differs for {x['id']}"

    # I6: bank details still in quarantine were never paid
    for r in L.query("SELECT tenant, data FROM quarantine WHERE status='ACTIVE'"):
        bank = json.loads(r["data"])["bank"]
        number = bank.get("account_number") or bank.get("iban") or ""
        if number:
            for t in EMPLOYERS:
                for x in transfers[t]:
                    assert number not in json.dumps(fake.accounts[acct[t]].beneficiaries.get(x["beneficiary_id"], {}), default=str), \
                        f"I6: {x['id']} paid quarantined details"

    # I7: no payout INTENT without an approval (or an auto-release) for that run and tenant, and none since a reopen
    for e in intents:
        if e["payload"].get("what") == "fee":
            continue
        before = [a for a in L.entries(run_id=e["run_id"], tenant=e["tenant"], kind="APPROVED") if a["seq"] < e["seq"]]
        assert before, f"I7: INTENT {e['payload']['request_id']} has no approval"
        reopened = [r for r in L.entries(run_id=e["run_id"], tenant=e["tenant"], kind="REOPENED")
                    if before[-1]["seq"] < r["seq"] < e["seq"]]
        assert not reopened or e["payload"].get("attempt", 1) > 1, "I7: sent after a reopen on the old approval"

    # I8: no token or key in the ledger rows, the database files, or the certificate directory
    secrets = _secrets(fake)
    blobs = [json.dumps(e, default=str) for e in L.entries()]
    for suffix in ("", "-wal"):
        p = Path(str(L.path) + suffix)
        if p.exists():
            blobs.append(p.read_bytes().decode("latin-1"))
    if cert_dir and cert_dir.exists():
        blobs += [f.read_text(encoding="utf-8", errors="replace") for f in cert_dir.glob("*.json")]
    for s in secrets:
        assert not any(s in b for b in blobs), "I8: a secret reached the ledger or artifacts"

    # I9: net fees never exceed 1.50 per PAID line, and equal it once the run is DONE
    for t in EMPLOYERS:
        for run in _runs(L, t):
            charged = sum((Decimal(e["payload"]["amount"]) for e in L.entries(run_id=run, tenant=t, kind="FEE_CHARGED")), Decimal(0))
            credits = sum((Decimal(e["payload"]["amount"]) for e in L.entries(run_id=run, tenant=t, kind="FEE_CREDIT")), Decimal(0))
            paid = len(store.get_lines(L, run, t, states=("PAID",)))
            net, owed = charged - credits, FEE_PER_PAYOUT * paid
            assert net <= owed, f"I9: {t} charged {net}, owed {owed}"
            if store.get_run(L, run, t)["state"] == "DONE":
                assert net == owed, f"I9: {t} DONE with fee {net}, owed {owed}"
