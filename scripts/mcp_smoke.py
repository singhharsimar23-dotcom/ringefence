"""Live MCP smoke: a real MCP client runs demo/payday through Ringfence on the Airwallex sandbox, a software passkey
approves, and the run is released. With --swap, Tom's live beneficiary is repointed after approval: the release must
hold, then the edit is reverted, the run re-approved and paid.
Usage: python scripts/mcp_smoke.py [--swap] [--fake]   (live needs AWX_PLAYGROUND_ACCOUNT and ANTHROPIC_API_KEY)"""
import asyncio
import base64
import hashlib
import json
import sys
import threading
import time
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.stdout.reconfigure(encoding="utf-8")

import httpx
import uvicorn
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from mcp import Client

from ringfence import mcp_remote
from ringfence.app import build_engine, create_app
from ringfence.playground import Manager
from scripts.awx import call as awx
from scripts.awx import env

PORT, RP = 8765, "127.0.0.1"
BASE = f"http://{RP}:{PORT}"
SWAP, FAKE = "--swap" in sys.argv, "--fake" in sys.argv


def b64u(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


KEY = ec.generate_private_key(ec.SECP256R1())


def sign(challenge: str) -> dict:
    """What Windows Hello returns: user present + verified, over authData || sha256(clientDataJSON)."""
    cdj = json.dumps({"type": "webauthn.get", "challenge": challenge, "origin": BASE}).encode()
    ad = hashlib.sha256(RP.encode()).digest() + bytes([0x05]) + (1).to_bytes(4, "big")
    sig = KEY.sign(ad + hashlib.sha256(cdj).digest(), ec.ECDSA(hashes.SHA256()))
    return {"challenge": challenge, "id": "smoke", "clientDataJSON": b64u(cdj), "authenticatorData": b64u(ad), "signature": b64u(sig)}


def view(wid: str, until=lambda v: True, timeout=60) -> dict:
    t0 = time.monotonic()
    while True:
        v = httpx.get(f"{BASE}/approve/{wid}/view", timeout=30).json()
        if until(v) or time.monotonic() - t0 > timeout:
            return v
        time.sleep(1.5)


def approve(wid: str) -> None:
    v = view(wid, lambda v: v["state"] == "AWAITING_APPROVAL")
    r = httpx.post(f"{BASE}/approve/{wid}", json=sign(v["passkey"]["challenge"]), timeout=60)
    assert r.status_code == 200 and r.json()["state"] == "READY", r.text
    print("  approved with passkey -> READY")


def tom_beneficiary(wid: str, acct: str) -> dict:
    _code, d = awx("GET", "/beneficiaries?page_num=0&page_size=100", login_as=acct)
    hits = [b for b in d.get("items", []) if b.get("nickname") == f"rf:{wid[:6]}:tom"]
    assert len(hits) == 1, f"Tom's beneficiary for {wid}: {len(hits)} found"
    return hits[0]


def set_account(acct: str, b: dict, number: str) -> None:
    body = deepcopy(b["beneficiary"])
    body["bank_details"]["account_number"] = number
    code, d = awx("POST", f"/beneficiaries/{b['id']}/update", {"nickname": b["nickname"], "transfer_methods": ["LOCAL"], "beneficiary": body}, login_as=acct)
    assert code == 200, (code, d)


async def tool(c: Client, name: str, **args):
    r = await c.call_tool(name, args, read_timeout_seconds=400)
    text = r.content[0].text
    return r.is_error, (text if r.is_error else json.loads(text))


async def main() -> int:
    files = {p.name: p.read_text(encoding="utf-8") for p in sorted((ROOT / "demo" / "payday").iterdir())}
    async with Client(f"{BASE}/mcp") as c:
        names = {t.name for t in (await c.list_tools()).tools}
        assert names == {"run_payroll", "release_payroll", "payroll_status", "payroll_proof"}, names
        print("tools:", sorted(names))

        t0 = time.monotonic()
        err, run = await tool(c, "run_payroll", files=files)
        assert not err, run
        wid = run["run_id"]
        print(f"run_payroll {time.monotonic() - t0:.0f}s: {run['bank']} | {run['state']} | {run['totals']}")
        for p in run["payments"]:
            print(f"  {p['name']}: {p['amount']} {p['currency']} -> ****{p['to_account_ending']}")
        print("  bank changes:", run["bank_change_requests"])
        print("  flagged:", json.dumps(run["refused_or_flagged"], indent=1))
        print("  fx:", run["fx"])
        assert run["state"] == "AWAITING_APPROVAL" and run["totals"], run
        live = not run["bank"].startswith("[SIMULATED]")
        assert live or FAKE, "expected the live sandbox; pass --fake to accept the simulated bank"

        err, text = await tool(c, "release_payroll", run_id=wid)
        assert err and "Not approved" in text, text
        print("  release before approval: refused")

        for b in run["bank_change_requests"]:
            assert httpx.post(f"{BASE}/approve/{wid}/reject", json={"qid": b["id"]}, timeout=60).status_code == 200  # noqa: ASYNC210  a smoke script; blocking is fine
        view(wid, lambda v: all(b["status"].startswith("rejected") for b in v["bank_change_requests"]))
        print("  bank change email rejected")
        approve(wid)

        if SWAP:
            assert live, "--swap needs the live sandbox"
            acct = env("AWX_PLAYGROUND_ACCOUNT")
            tom = tom_beneficiary(wid, acct)
            real = tom["beneficiary"]["bank_details"]["account_number"]
            set_account(acct, tom, "99999901")
            print(f"  [swap] Tom repointed on Airwallex: ****{real[-4:]} -> ****9901")
            err, out = await tool(c, "release_payroll", run_id=wid)
            print("  release after swap:", out["state"], out.get("changed_after_approval"))
            assert out["state"] == "HELD" and not any(p.get("airwallex_transfer_id") for p in out["payments"]), out
            set_account(acct, tom, real)
            print("  [swap] reverted; reopening for a fresh approval")
            assert httpx.post(f"{BASE}/approve/{wid}/resume", timeout=60).status_code == 200  # noqa: ASYNC210  a smoke script; blocking is fine
            approve(wid)

        err, out = await tool(c, "release_payroll", run_id=wid)
        assert not err, out
        t1 = time.monotonic()
        while out["state"] not in ("RELEASED", "DONE") and time.monotonic() - t1 < 120:
            await asyncio.sleep(3)
            err, out = await tool(c, "payroll_status", run_id=wid)
        print("release:", out["state"])
        for p in out["payments"]:
            print(f"  {p['name']}: {p['state']} {p.get('airwallex_transfer_id')}")
        assert out["state"] in ("RELEASED", "DONE") and all(p.get("airwallex_transfer_id") for p in out["payments"]), out
        err, again = await tool(c, "release_payroll", run_id=wid)
        assert again["note"].startswith("Already sent"), again
        print("  second release: nothing new sent")

        err, proof = await tool(c, "payroll_proof", run_id=wid)
        print("proof:", proof["result"], "signature_valid", proof["signature_valid"], "checks", proof["all_checks_passed"])
        assert not err and proof["signature_valid"] and proof["result"] == "PASS", proof

        if live:  # what the Airwallex dashboard on the left shows
            _code, d = awx("GET", "/transfers?page_num=0&page_size=20", login_as=env("AWX_PLAYGROUND_ACCOUNT"))
            mine = {p["airwallex_transfer_id"] for p in out["payments"]}
            seen = {t["id"]: t for t in d.get("items", []) if t["id"] in mine}
            print(f"Airwallex lists {len(seen)}/{len(mine)} of these transfers:",
                  [(t.get("amount_beneficiary_receives"), t.get("transfer_currency"), t.get("status"))
                   for t in seen.values()] if seen else "")
            assert len(seen) == len(mine)
    print("OK")
    return 0


if __name__ == "__main__":
    E = build_engine("fake", "scripted")  # moves RF_VAR to a temp dir: enrol the key after it
    mcp_remote.save_key("smoke", b64u(KEY.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)), -7, RP)
    play = Manager(live_probe=(lambda: False) if FAKE else None)
    server = uvicorn.Server(uvicorn.Config(create_app(E, play), host=RP, port=PORT, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    while not server.started:
        time.sleep(0.2)
    try:
        rc = asyncio.run(main())
    finally:
        server.should_exit = True
        play.shutdown()
    sys.exit(rc)
