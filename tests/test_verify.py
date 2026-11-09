import json
import sqlite3
from decimal import Decimal as D

import pytest
from helpers import acct

from ringfence import __main__ as cli
from ringfence import beneficiaries as ben
from ringfence import verify
from ringfence.orchestrator import Orchestrator
from ringfence.setup_demo import setup


@pytest.fixture
def world(awx, fake, L, monkeypatch, tmp_path):
    monkeypatch.setattr(verify, "PUB_PATH", tmp_path / "pub.pem")
    setup(awx)
    o = Orchestrator(awx, L)
    o.ex._sleep = lambda s: None
    cli.demo(o, sleep=lambda s: None)
    return o


def test_isolation_report_passes_and_certificates_verify(world, awx, L):
    rep = verify.report(awx, L)
    assert rep["ok"], rep
    assert all(p["status"] == 401 for p in rep["probes"])
    names = [c["name"] for t in rep["tenants"].values() for c in t["checks"]]
    assert any("offline test double" in n for n in names) and not any("Airwallex" in n and "401" in n for n in names)  # the fake never claims to be Airwallex
    certs = verify.certificates(rep, "r1", "fake")
    assert {c["body"]["result"] for c in certs.values()} == {"PASS"}
    assert all(verify.check_cert(c) for c in certs.values())
    c = certs["harbour"]
    assert c["body"]["totals_by_currency"] == {"AUD": "1240.17"} and c["body"]["fee_gbp"] == "4.50"
    c["body"]["totals_by_currency"]["AUD"] = "1.00"  # edit one number: signature breaks
    assert not verify.check_cert(c)


def test_a_transfer_with_no_ledger_intent_fails_that_tenant_only(world, awx, fake, L):
    kes = fake.accounts[acct("kestrel")]
    some = next(iter(kes.transfers.values()))
    rogue = awx.for_tenant("kestrel").post("/transfers/create", {
        "request_id": "rogue-not-in-ledger-0001", "beneficiary_id": next(iter(ben.load_registry()["tenants"]["kestrel"]["beneficiaries"].values())), "transfer_amount": D("1.00"),
        "transfer_currency": "USD", "source_currency": "USD", "transfer_method": "LOCAL", "reason": "x"})
    rep = verify.report(awx, L)
    assert not rep["ok"] and not rep["tenants"]["kestrel"]["ok"]
    assert rep["tenants"]["harbour"]["ok"] and rogue["id"] in rep["tenants"]["kestrel"]["checks"][0]["detail"]


def test_tampering_a_ledger_row_is_caught_at_that_seq(world, L, tmp_path):
    cert = verify.write_certs(verify.certificates(verify.report(world.awx, L), "r1", "fake"), "r1", tmp_path)[0]
    assert L.verify(tmp_path).ok
    seq = L.entries(kind="FEE_CHARGED")[0]["seq"]
    con = sqlite3.connect(L.path)
    con.execute("DROP TRIGGER ledger_no_update")  # an attacker with the file, not an API user
    con.execute("UPDATE ledger SET payload_json=? WHERE seq=?", (json.dumps({"amount": "0.01"}), seq))
    con.commit()
    v = L.verify(tmp_path)
    assert not v.ok and v.bad_seq == seq
    assert cert.exists()


def test_a_rewritten_ledger_no_longer_matches_the_head_stamped_on_the_transfers(world, awx, L):
    stamped = [t for t in world.awx.for_tenant("kestrel").get("/transfers", {"page": "0", "page_size": 100})["items"] if t.get("metadata")]
    assert stamped and verify.report(awx, L)["ok"]
    seq = int(stamped[0]["metadata"]["rf_seq"])
    con = sqlite3.connect(L.path)
    con.execute("DROP TRIGGER ledger_no_update")  # whoever holds the disk rewrites a row and recomputes the chain
    con.execute("UPDATE ledger SET hash='0'*64 WHERE seq=?".replace("'0'*64", "'" + "0" * 64 + "'"), (seq,))
    con.commit()
    rep = verify.report(awx, L)
    assert not rep["ok"] and any("head hash" in c["name"] and not c["ok"] for c in rep["tenants"]["kestrel"]["checks"])


@pytest.mark.parametrize("junk", [{"rf_seq": "abc", "rf_hash": "x"}, {"rf_seq": "9" * 40, "rf_hash": "x"},
                                  {"rf_seq": "1", "rf_hash": 5}, {"rf_seq": "-1", "rf_hash": "x"}])
def test_junk_in_transfer_metadata_fails_the_check_instead_of_crashing_proof(world, awx, L, junk):
    assert verify._stamp_ok(L, junk) is False
