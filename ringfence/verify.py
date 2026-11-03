"""Isolation report and signed segregation certificate (BUILD_SPEC 4.10). No LLM anywhere in this file.

Airwallex's own records are the source of truth: each tenant's transfers are read with THAT tenant's token and
cross-checked against the ledger. A mismatch in either direction fails.

    python -m ringfence.verify report [--backend fake|live] [--write]
    python -m ringfence.verify cert <file.json>
    python -m ringfence.verify chain
"""
from __future__ import annotations

import argparse
import base64
import json
import sys
from decimal import Decimal
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from . import beneficiaries as ben
from .awx import Awx, build_backend
from .config import EMPLOYERS, ROOT, clock, var_dir
from .ledger import Ledger
from .money import canonical_json, q

PUB_PATH = ROOT / "ringfence" / "cert_pub.pem"
CERT_DIR = ROOT / "artifacts" / "certs"
PROBES = (("northwind", "kestrel"), ("kestrel", "harbour"), ("harbour", "northwind"))


# -- keys --------------------------------------------------------------------------------------
def _private_key() -> Ed25519PrivateKey:
    p = var_dir() / "cert_key.pem"
    if p.exists():
        return serialization.load_pem_private_key(p.read_bytes(), None)
    k = Ed25519PrivateKey.generate()
    p.write_bytes(k.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                  serialization.NoEncryption()))
    PUB_PATH.write_bytes(k.public_key().public_bytes(serialization.Encoding.PEM,
                                                     serialization.PublicFormat.SubjectPublicKeyInfo))
    return k


def sign(body: dict) -> dict:
    sig = _private_key().sign(canonical_json(body).encode())
    return {"body": body, "signature": base64.b64encode(sig).decode(), "alg": "Ed25519"}


def check_cert(doc: dict, pub_path: Path | None = None) -> bool:
    try:
        pub = serialization.load_pem_public_key((pub_path or PUB_PATH).read_bytes())
        assert isinstance(pub, Ed25519PublicKey)
        pub.verify(base64.b64decode(doc["signature"]), canonical_json(doc["body"]).encode())
        return True
    except (InvalidSignature, KeyError, ValueError, OSError, AssertionError):
        return False


# -- report ------------------------------------------------------------------------------------
def _transfers(c, since: str) -> list[dict]:
    out, page = [], 0
    while True:
        items = c.get("/transfers", {"from_created_at": since, "page_num": page, "page_size": 100}).get("items", [])
        out += items
        if len(items) < 100:
            return out
        page += 1


def _chk(name: str, ok: bool, detail: str = "") -> dict:
    return {"name": name, "ok": bool(ok), "detail": detail}


def _tenant_report(tenant: str, L: Ledger, reg: dict, seen: dict[str, list[dict]]) -> dict:
    entries = L.entries(tenant=tenant, kind="INTENT")
    intents = {e["payload"]["request_id"]: e for e in entries}
    own = reg["tenants"].get(tenant, {})
    own_bens = {*own.get("beneficiaries", {}).values(), own.get("fee_beneficiary")}
    ts = seen[tenant]
    by_req: dict[str, list[dict]] = {}
    for t in ts:
        by_req.setdefault(t.get("request_id"), []).append(t)

    unknown = [t["id"] for t in ts if t.get("request_id") not in intents]
    foreign_ben = [t["id"] for t in ts if t.get("beneficiary_id") not in own_bens]
    wrong_amt = [t["id"] for t in ts if (e := intents.get(t.get("request_id"))) and
                 (Decimal(str(t["transfer_amount"])) != Decimal(e["payload"]["amount"])
                  or t["transfer_currency"] != e["payload"]["currency"])]
    missing = [rid for rid in intents if len(by_req.get(rid, [])) != 1]
    elsewhere = [rid for rid in intents for other, tl in seen.items()
                 if other != tenant and any(t.get("request_id") == rid for t in tl)]
    paid_per_payee: dict[str, int] = {}
    for rid, e in intents.items():
        cid = e["payload"].get("contractor_id")
        if cid and any(t.get("status") not in ("FAILED", "CANCELLED") for t in by_req.get(rid, [])):
            paid_per_payee[cid] = paid_per_payee.get(cid, 0) + 1
    doubles = [c for c, n in paid_per_payee.items() if n > 1]

    checks = [
        _chk("Every transfer in this account has a ledger intent for this employer", not unknown, ",".join(unknown)),
        _chk("Every payee is one of this employer's own beneficiaries", not foreign_ben, ",".join(foreign_ben)),
        _chk("Amounts and currencies equal the approved lines", not wrong_amt, ",".join(wrong_amt)),
        _chk("Each intent has exactly one transfer here", not missing, ",".join(missing)),
        _chk("No intent produced a transfer in another employer's account", not elsewhere, ",".join(elsewhere)),
        _chk("No contractor was paid twice", not doubles, ",".join(doubles)),
    ]
    totals: dict[str, Decimal] = {}
    fee = Decimal(0)
    for t in ts:
        if t.get("status") in ("FAILED", "CANCELLED"):
            continue
        amt, ccy = Decimal(str(t["transfer_amount"])), t["transfer_currency"]
        if str(t.get("request_id", "")).startswith("fee-"):
            fee += amt
        else:
            totals[ccy] = totals.get(ccy, Decimal(0)) + amt
    return {"tenant": tenant, "ok": all(c["ok"] for c in checks), "checks": checks,
            "debits": [{"transfer_id": t["id"], "request_id": t.get("request_id"), "beneficiary_id": t.get("beneficiary_id"),
                        "amount": str(q(Decimal(str(t["transfer_amount"])), t["transfer_currency"])),
                        "currency": t["transfer_currency"], "status": t.get("status")} for t in ts],
            "payees": len({e["payload"].get("contractor_id") for e in entries if e["payload"].get("contractor_id")}),
            "totals_by_currency": {k: str(q(v, k)) for k, v in sorted(totals.items())}, "fee_gbp": str(q(fee, "GBP"))}


def report(awx: Awx, L: Ledger, cert_dir: Path | None = None) -> dict:
    reg = ben.load_registry()
    seen: dict[str, list[dict]] = {}
    for t in EMPLOYERS:
        first = L.entries(tenant=t, kind="RUN_CREATED")
        since = (first[0]["ts"] if first else clock.utc_now().isoformat())[:19] + "Z"
        seen[t] = _transfers(awx.for_tenant(t), since)
    tenants = {t: _tenant_report(t, L, reg, seen) for t in EMPLOYERS}
    probes = []
    for a, b in PROBES:
        status, code = awx.probe_cross_tenant(a, b)
        probes.append({"from": a, "to": b, "status": status, "code": code, "ok": status == 401})
    chain = L.verify(cert_dir)
    head = {"seq": chain.head_seq, "hash": chain.head_hash}
    for t in tenants.values():
        mine = next(p for p in probes if p["from"] == t["tenant"])
        t["checks"].append(_chk("Another employer's account is out of reach (live 401 from Airwallex)", mine["ok"],
                                f"HTTP {mine['status']} {mine['code']}"))
        t["checks"].append(_chk("Ledger hash chain verifies", chain.ok, chain.reason))
        t["ok"] = all(c["ok"] for c in t["checks"])
    return {"ok": all(t["ok"] for t in tenants.values()), "tenants": tenants, "probes": probes,
            "chain": {"ok": chain.ok, "bad_seq": chain.bad_seq, "reason": chain.reason, **head}}


def certificates(rep: dict, run_id: str, backend: str) -> dict[str, dict]:
    out = {}
    for t, r in rep["tenants"].items():
        body = {"tenant": t, "run_id": run_id, "issued_at": clock.utc_now().isoformat(), "backend": backend,
                "result": "PASS" if r["ok"] else "FAIL", "debits": r["debits"], "payees": r["payees"],
                "totals_by_currency": r["totals_by_currency"], "fee_gbp": r["fee_gbp"],
                "ledger_head": {"seq": rep["chain"]["seq"], "hash": rep["chain"]["hash"]},
                "checks": [{"name": c["name"], "ok": c["ok"]} for c in r["checks"]]}
        out[t] = sign(body)
    return out


def write_certs(certs: dict[str, dict], run_id: str, dest: Path = CERT_DIR) -> list[Path]:
    dest.mkdir(parents=True, exist_ok=True)
    paths = []
    for t, doc in certs.items():
        p = dest / f"{t}_{run_id}.json"
        p.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
        paths.append(p)
    return paths


def current_run_id(L: Ledger) -> str:
    e = L.entries(kind="RUN_CREATED")
    return e[-1]["run_id"] if e else f"none-{L.epoch()}"


def main() -> int:
    ap = argparse.ArgumentParser(prog="ringfence.verify")
    ap.add_argument("cmd", choices=["report", "cert", "chain"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--backend", choices=["fake", "live"])
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    if a.cmd == "cert":
        doc = json.loads(Path(a.file).read_text(encoding="utf-8"))
        ok = check_cert(doc)
        b = doc.get("body", {})
        print(f"{'VALID' if ok else 'INVALID'}  {b.get('tenant')} {b.get('run_id')} {b.get('result')} "
              f"ledger head #{b.get('ledger_head', {}).get('seq')}")
        return 0 if ok else 1
    L = Ledger()
    if a.cmd == "chain":
        v = L.verify(CERT_DIR)
        print(f"chain {'OK' if v.ok else 'BROKEN at seq ' + str(v.bad_seq) + ': ' + v.reason}; head #{v.head_seq}")
        return 0 if v.ok else 1
    awx, _ = build_backend(a.backend)
    rep = report(awx, L, CERT_DIR)
    for t, r in rep["tenants"].items():
        print(f"{t}: {'PASS' if r['ok'] else 'FAIL'}  {r['payees']} payees  {r['totals_by_currency']}  fee GBP {r['fee_gbp']}")
        for c in r["checks"]:
            print(f"   [{'ok' if c['ok'] else 'FAIL'}] {c['name']} {c['detail']}")
    if a.write:
        for p in write_certs(certificates(rep, current_run_id(L), a.backend or "live"), current_run_id(L)):
            print("wrote", p.relative_to(ROOT))
    return 0 if rep["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
