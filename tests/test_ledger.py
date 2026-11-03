import json
import sqlite3
import threading
from decimal import Decimal as D

import pytest

from ringfence.ledger import GENESIS, Ledger


@pytest.fixture
def ledger(tmp_path):
    return Ledger(tmp_path / "t.db")


def test_chain_and_verify(ledger):
    assert ledger.verify().ok and ledger.head() == (0, GENESIS)
    a = ledger.append("RUN_CREATED", {"amount": D("1.10")}, run_id="r1", tenant="kestrel")
    b = ledger.append("PRICED", {"x": 1}, run_id="r1", tenant="kestrel")
    assert (a, b) == (1, 2)
    rows = ledger.entries()
    assert rows[0]["prev_hash"] == GENESIS and rows[1]["prev_hash"] == rows[0]["hash"]
    assert rows[0]["payload"] == {"amount": "1.10"}
    v = ledger.verify()
    assert v.ok and v.head_seq == 2


def test_triggers_block_update_and_delete(ledger):
    ledger.append("RUN_CREATED")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        ledger.conn().execute("UPDATE ledger SET kind='PRICED'")
    with pytest.raises(sqlite3.DatabaseError, match="append-only"):
        ledger.conn().execute("DELETE FROM ledger")


def tamper(ledger, seq, payload):
    c = ledger.conn()
    c.executescript("DROP TRIGGER ledger_no_update")
    c.execute("UPDATE ledger SET payload_json=? WHERE seq=?", (json.dumps(payload), seq))


def test_verify_detects_tamper_at_exact_seq(ledger):
    for i in range(5):
        ledger.append("STATUS", {"i": i})
    tamper(ledger, 3, {"i": 99})
    v = ledger.verify()
    assert not v.ok and v.bad_seq == 3 and v.reason == "hash mismatch"


def test_anchor_mismatch(ledger, tmp_path):
    ledger.append("STATUS", {"i": 1})
    seq, h = ledger.head()
    d = tmp_path / "certs"
    d.mkdir()
    (d / "c.json").write_text(json.dumps({"body": {"ledger_head": {"seq": seq, "hash": h}}}))
    assert ledger.verify(d).ok
    (d / "c.json").write_text(json.dumps({"body": {"ledger_head": {"seq": seq, "hash": "f" * 64}}}))
    v = ledger.verify(d)
    assert not v.ok and v.bad_seq == seq and "anchor" in v.reason


def test_tx_atomicity(ledger):
    with pytest.raises(RuntimeError), ledger.tx() as t:
        t.execute("INSERT INTO runs(run_id, tenant, state) VALUES('r', 'k', 'DRAFT')")
        t.append("RUN_CREATED", run_id="r")
        raise RuntimeError("boom")
    assert ledger.head()[0] == 0
    assert ledger.query("SELECT * FROM runs") == []
    with ledger.tx() as t:
        t.execute("INSERT INTO runs(run_id, tenant, state) VALUES('r', 'k', 'DRAFT')")
        t.append("RUN_CREATED", run_id="r")
    assert ledger.head()[0] == 1 and len(ledger.query("SELECT * FROM runs")) == 1


def test_secret_keys_and_unknown_kinds_refused(ledger):
    with pytest.raises(ValueError):
        ledger.append("STATUS", {"headers": {"Authorization": "Bearer x"}})
    with pytest.raises(ValueError):
        ledger.append("NOPE")
    assert ledger.head()[0] == 0


def test_concurrent_writers_serialise(ledger):
    def work():
        for _ in range(10):
            ledger.append("STATUS")
    ts = [threading.Thread(target=work) for _ in range(6)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    v = ledger.verify()
    assert v.ok and v.head_seq == 60


def test_epoch_stable_and_kill_switch(ledger):
    e = ledger.epoch()
    assert len(e) == 6 and ledger.epoch() == e
    assert not ledger.kill_switch_on()
    ledger.set_kill_switch(True, "maya")
    assert ledger.kill_switch_on() and ledger.entries(kind="KILL_SWITCH")[0]["payload"]["by"] == "maya"
