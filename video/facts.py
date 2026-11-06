"""Snapshot the live demo's evidence right after a capture run, so every ID on screen in the film is the real one.
Read-only GETs on the public site. Writes video/src/facts.json (small, the fields the film uses) and var/edit/facts_raw.json.
Usage: uv run python video/facts.py [url]"""
import json
import sys
from pathlib import Path

import httpx

URL = (sys.argv[1] if len(sys.argv) > 1 else "https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com").rstrip("/")
ROOT = Path(__file__).resolve().parent.parent


def transfers(tl: list, creates: list) -> list:
    """Every transfer this run submitted (ledger), read back from Airwallex under that employer's own token.
    The public call log only keeps the last 300 calls, so the create's HTTP status/ms are kept only while it's still there."""
    sys.path.insert(0, str(ROOT / "scripts"))
    from awx import call, env
    acct = {"northwind": env("AWX_EMPLOYER_A"), "kestrel": env("AWX_EMPLOYER_B"), "harbour": env("AWX_EMPLOYER_C")}
    seen = {x["id"]: x for x in creates}
    out = []
    for e in tl:
        if e["kind"] != "SUBMITTED":
            continue
        d = e["detail"]
        code, t = call("GET", f"/transfers/{d['transfer_id']}", login_as=acct[e["tenant"]])
        if code != 200:
            raise SystemExit(f"GET /transfers/{d['transfer_id']} -> {code}")
        c = seen.get(d["transfer_id"], {})
        out.append({"tenant": e["tenant"], "id": t["id"], "request_id": t["request_id"], "amount": t["transfer_amount"], "currency": t["transfer_currency"],
                    "short_reference_id": t.get("short_reference_id"), "status": t["status"], "create_http": c.get("status"), "create_ms": c.get("ms")})
    return out


def main() -> int:
    with httpx.Client(base_url=URL, timeout=120) as c:
        raw = {k: c.get(p).json() for k, p in {"state": "/api/state", "timeline": "/api/timeline", "calls": "/api/calls", "proof": "/api/proof"}.items()}
    (ROOT / "var/edit/facts_raw.json").write_text(json.dumps(raw, indent=1), encoding="utf-8")
    tl = raw["timeline"]
    seqs = ",".join(str(e["seq"]) for e in tl if e["kind"].startswith(("TRANSFER", "METAL", "APPROV", "FUND", "BANK", "BATCH")))[:2000]
    with httpx.Client(base_url=URL, timeout=60) as c:
        rows = c.get("/api/ledger", params={"seqs": seqs}).json() if seqs else []
    calls = raw["calls"]["calls"]
    creates = [x for x in calls if x.get("method") == "POST" and x.get("path") == "/transfers/create"]
    pick = lambda kind: [r for r in rows if r["kind"] == kind]
    facts = {
        "head": tl[-1]["detail"]["hash"] if tl else None,
        "kinds": sorted({e["kind"] for e in tl}),
        "transfers": transfers(tl, creates),
        "metal_pull": [r["payload"] for r in pick("METAL_PULL")],
        "metal_refused": [r["payload"] for r in pick("METAL_REFUSED")],
        "rows": rows,
        "proof_ok": raw["proof"].get("report", {}).get("ok") if isinstance(raw["proof"], dict) else None,
    }
    g = json.loads((ROOT / "docs/gauntlet/results.json").read_text(encoding="utf-8"))  # the published gauntlet run, numbers only
    facts["gauntlet"] = {"evil": {k: v for k, v in g["hostile_documents"]["evil"].items() if k != "rows"},
                         "claude": {k: v for k, v in g["hostile_documents"]["claude"].items() if k != "rows"},
                         "storm": g["network_storm"][-1], "sequences": g["sequences"], "isolation": g["isolation"][-1],
                         "tamper": {k: v for k, v in g["tamper"].items() if k != "rows"}, "commit": g["commit"], "date": g["date"]}
    (ROOT / "video/src/facts.json").write_text(json.dumps(facts, indent=1), encoding="utf-8")
    print("timeline", len(tl), "calls", len(calls), "creates", len(creates), "ledger rows", len(rows), "head", facts["head"])
    print("kinds", facts["kinds"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
