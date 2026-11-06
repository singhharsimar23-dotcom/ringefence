"""Probe: is Harbour's ISSUER key (owner.issuer.json) enough to mint a payable mandate, with no owner key and no bind?
Pays 0.01 USDZ from Harbour's testnet account to OUR OWN settlement wallet. All CLI output passes through metal.scrub."""
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import awx  # noqa: E402

for n in ("METAL_RPC_URL", "METAL_RPC_SECRET"):
    os.environ.setdefault(n, awx.env(n) or "")
from ringfence import metal  # noqa: E402

m = metal.Metal()
c = m.cfg()
rd = m.dir / "runs" / f"probe-issuer-{int(time.time())}"
issuer = str(m.dir / "owner.issuer.json")


def run(label, args, cwd=rd):
    rc, out = metal.run_cli([*args, *metal.NET], cwd, timeout=180)
    print(f"--- {label} (exit {rc})")
    print("\n".join(ln for ln in out.splitlines() if ln.strip())[:1500])
    return rc, metal.parse(out)


run("credential signed by the ISSUER key only (no --key owner.json)",
    ["mandate", "credential", "create", "--principal", c["principal"], "--payee", c["settlement"], "--cap", "0.01",
     "--budget", "0.01", "--max-occurrences", "1", "--expires-in", "900", "--issuer-key", issuer, "--out", "m.json",
     "--description", "probe: issuer key only, never bound"])
run("status before any bind", ["mandate", "status", "--credential", "m.json"])
run("pull WITHOUT bind", ["mandate", "pull", "--credential", "m.json", "--to", c["settlement"], "--amount", "0.01",
                          "--payment-id", rd.name])
