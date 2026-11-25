# ruff: noqa: F811, F401
"""The /alta page, API and MCP: read-only by construction, and the re-check reads the chain, not a stored answer."""
import asyncio
import json
import shutil

import pytest
from fastapi.testclient import TestClient
from helpers import RUN
from test_alta_device import NOAH, ZOE, chain, device, executor, exp, rid, world

from ringfence import alta_app, alta_mcp, alta_verify


@pytest.fixture
def docs(tmp_path, monkeypatch):
    monkeypatch.setattr(alta_app, "DOCS", tmp_path / "docs")
    (tmp_path / "docs").mkdir()
    return tmp_path / "docs"


def record(world, device, chain, L, docs):
    """What scripts/alta_payroll_run.py writes: the approved batch, each credential file (never a pull key), the certificate."""
    device.sign(exp(L), chain.creds)
    executor(world, L).release(RUN, "kestrel")
    executor(world, L).release(RUN, "kestrel")
    out = docs / "payroll-2026-11-25"
    (out / "creds").mkdir(parents=True)
    for x in exp(L)["lines"]:
        (out / "creds" / x["request_id"]).mkdir()
        shutil.copy(chain.creds / x["request_id"] / "m.json", out / "creds" / x["request_id"] / "m.json")
        shutil.copy(chain.creds / x["request_id"] / "m.key.json", out / "creds" / x["request_id"] / "m.key.json")  # must never be served
    rep = alta_verify.report(L, world.chain, RUN, "kestrel")
    (out / "export.json").write_text(json.dumps(exp(L)))
    (out / "book.json").write_text(json.dumps({"noah": NOAH, "zoe": ZOE}))
    (out / "report.json").write_text(json.dumps(rep, default=str))
    alta_verify.write(alta_verify.certificate(L, rep), out)
    return out


def test_with_nothing_recorded_the_page_says_so_and_still_lists_the_findings(docs):
    c = TestClient(alta_app.create_app())
    o = c.get("/alta/api/overview").json()
    assert o["attacks"] is None and o["payroll"] is None and len(o["findings"]) >= 4
    assert c.post("/alta/api/recheck").status_code == 404
    assert c.get("/alta").status_code == 200 and c.get("/alta/healthz").json() == {"ok": True}


def test_price_uses_the_registry_rates_and_refuses_a_non_cent_amount(docs):
    c = TestClient(alta_app.create_app())
    j = c.post("/alta/api/price", json={"noah": "10", "zoe": "8"}).json()
    assert [(x["usd"], x["usdz"]) for x in j["lines"]] == [("550.00", "55.00"), ("500.00", "50.00")]
    assert c.post("/alta/api/price", json={"mallory": "1"}).status_code == 400
    assert c.post("/alta/api/price", json={"noah": "0.001"}).status_code == 400


def test_recheck_reads_the_chain_now_so_a_later_change_shows(world, device, chain, L, docs):
    record(world, device, chain, L, docs)
    c = TestClient(alta_app.create_app(chain))
    assert c.post("/alta/api/recheck").json()["ok"] is True
    chain.state[rid("zoe")]["payee"] = "0x" + "9" * 40  # the chain's record changes after the payroll was recorded
    j = c.post("/alta/api/recheck").json()
    assert j["ok"] is False and any(not r["ok"] and r["line"] == "zoe" for r in j["rows"])


def test_recheck_is_capped_per_hour_and_one_at_a_time(world, device, chain, L, docs, monkeypatch):
    record(world, device, chain, L, docs)
    monkeypatch.setattr(alta_app, "RECHECKS_PER_HOUR", 1)
    app = alta_app.create_app(chain)
    c = TestClient(app)
    assert c.post("/alta/api/recheck").status_code == 200
    assert c.post("/alta/api/recheck").status_code == 429
    monkeypatch.setattr(alta_app, "RECHECKS_PER_HOUR", 99)
    r = alta_app.Recheck(chain)
    r.lock.acquire()
    with pytest.raises(alta_app.HTTPException) as e:
        r()
    assert e.value.status_code == 409


def test_the_proof_download_never_contains_a_pull_key(world, device, chain, L, docs):
    record(world, device, chain, L, docs)
    import io
    import zipfile
    z = zipfile.ZipFile(io.BytesIO(TestClient(alta_app.create_app(chain)).get("/alta/payroll.zip").content))
    names = z.namelist()
    assert "export.json" in names and any(n.endswith("m.json") for n in names)
    assert not any(n.endswith("m.key.json") for n in names)


def test_overview_carries_the_certificate_and_the_recorded_lines(world, device, chain, L, docs):
    record(world, device, chain, L, docs)
    o = TestClient(alta_app.create_app(chain)).get("/alta/api/overview").json()
    assert o["payroll"]["cert"]["body"]["result"] == "PASS" and len(o["payroll"]["export"]["lines"]) == 2


def test_the_mcp_tools_are_read_only_and_take_no_wallet_or_amount(docs):
    m = alta_mcp.build(dict)
    tools = asyncio.run(m.list_tools())
    assert {t.name for t in tools} == {"price_payroll", "attack_report", "payroll_proof", "recheck_on_chain"}
    for t in tools:
        assert not any(w in t.name for w in ("approve", "bind", "sign", "pull", "revoke", "release"))
        assert not {"wallet", "address", "amount", "payee"} & set(t.input_schema.get("properties", {}))


def test_the_main_app_has_no_alta_routes():
    from ringfence.app import Engine, create_app
    from ringfence.awx import Awx
    from ringfence.config import tenants
    from ringfence.fake_awx import FakeAirwallex
    from ringfence.ledger import Ledger
    fake = FakeAirwallex({k: t.account_id for k, t in tenants(fake=True).items()})
    E = Engine(Awx(transport=fake.transport, tenant_map=tenants(fake=True), sleep=lambda s: None), Ledger(), "fake", "scripted", idle=3600)
    assert not [r.path for r in create_app(E).routes if "alta" in getattr(r, "path", "")]
