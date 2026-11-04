"""The landing page recomputes ledger hashes in the browser. It may only do that if its code agrees with ledger.entry_hash on every row."""
import json
import shutil
import subprocess

import pytest
from helpers import FakeLLM  # noqa: F401  (keeps the helpers import path on sys.path)

from ringfence import attacks, inbox
from ringfence.agent import loop
from ringfence.config import ROOT
from ringfence.orchestrator import Orchestrator
from ringfence.setup_demo import setup

node = shutil.which("node")


def rows_of(L):
    return [{"seq": e["seq"], "ts": e["ts"], "run_id": e["run_id"], "kind": e["kind"], "tenant": e["tenant"], "hash": e["hash"],
             "prev_hash": e["prev_hash"], "payload": e["payload"]} for e in L.entries()]


def run_node(tmp_path, rows):
    f = tmp_path / "rows.json"
    f.write_text(json.dumps(rows), encoding="utf-8")
    r = subprocess.run([node, str(ROOT / "tests" / "chain_parity.js"), str(f)], check=False, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    return json.loads(r.stdout)


@pytest.mark.skipif(node is None, reason="node is not installed")
def test_browser_hash_matches_python_on_a_real_ledger(awx, fake, L, tmp_path):
    setup(awx)
    o = Orchestrator(awx, L)
    o.ex._sleep = lambda s: None
    for g, f in attacks.library()[:4]:  # hostile text, unicode and every kind of payload end up in the ledger
        (inbox.drop_dir("northwind") / f"{attacks.doc_name(g, f)}.txt").write_text(attacks.render(g, f) + "\nCafé 日本語 \U0001F600 \x7f", encoding="utf-8")
    loop.run_tick(o, "northwind", mode="scripted")
    rows = rows_of(L)
    assert len(rows) > 10
    res = run_node(tmp_path, rows)
    assert res == {"bad": [], "firstBreak": None}


@pytest.mark.skipif(node is None, reason="node is not installed")
def test_browser_check_finds_the_edited_row(awx, fake, L, tmp_path):
    setup(awx)
    o = Orchestrator(awx, L)
    loop.run_tick(o, "northwind", mode="scripted")
    rows = rows_of(L)
    rows[5]["payload"] = {**rows[5]["payload"], "edited": "yes"}
    res = run_node(tmp_path, rows)
    assert res["firstBreak"] == rows[5]["seq"] and rows[5]["seq"] in res["bad"]
