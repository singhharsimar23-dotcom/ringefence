"""Run the attack lab on the live Alta testnet and write the result to docs/alta/attacks-<date>.json.

The attacker is the Ringfence server itself (every pull key, no owner key). Each attack runs against a broad mandate and
against Ringfence's per-line mandates. Spend, printed first and again at the end: a few cents of USDZ per attack (the
amounts are 0.05 and 0.04 USDZ), all of it moved between accounts this script creates, except attack 2's lookalike address,
which nobody owns. Binds and revokes are paid in gas by the Harbour owner key, about 30 transactions.

  python scripts/alta_attack_run.py --go
"""
import argparse
import json
import os
import sys
import time
from datetime import date
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import awx

for n in ("METAL_RPC_URL", "METAL_RPC_SECRET"):
    os.environ.setdefault(n, awx.env(n) or "")
from ringfence import metal
from ringfence.alta_attacks import ATTACKS, Lab

OWNER = ROOT / "var" / "metal" / "harbour_device" / "owner.json"
STATE = ROOT / "var" / "metal" / "harbour" / "state.json"
AMOUNTS = {"noah": Decimal("0.05"), "zoe": Decimal("0.04")}


def account(work: Path, name: str) -> str:
    rc, out = metal.run_cli(["account", "create", "--out", str(work / f"{name}.json"), *metal.NET], work / name)
    f = metal.parse(out)
    if rc != 0 or not f.get("account"):
        raise SystemExit(f"could not create the {name} account: {metal.scrub(out)[:600]}")
    return f["account"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    o = ap.parse_args()
    print(__doc__.split("\n\n")[0])
    print(__doc__.split("\n\n")[1])
    if not o.go:
        return
    st = json.loads(STATE.read_text(encoding="utf-8"))
    work = ROOT / "var" / "alta" / "attacks" / time.strftime("%Y%m%d-%H%M%S")
    work.mkdir(parents=True)
    # no faucet grants spent here (10 a day per IP): the attacker's key and one wallet come from a single account made once
    kf = work.parent / "attacker.json"
    if not kf.exists():
        wal = account(work.parent, "attacker")
    else:
        wal = json.loads((work.parent / "attacker.addr").read_text())["account"]
    (work.parent / "attacker.addr").write_text(json.dumps({"account": wal}))
    wallets = {"noah": st["settlement"], "zoe": wal}
    mule = "0x" + "dead" * 10  # nobody owns it: what lands there is lost, which is the point of attack 1
    lab = Lab(metal.run_cli, OWNER, st["principal"], work, wallets=wallets, mule=mule,
              recorder_key=Path(str(metal.Metal().treasury_key())), attacker_key=kf, amounts=AMOUNTS)
    lab.on_row = lambda r: print(f"{r['attack']} {r['name']:<28} {r['side']:<16} {r['outcome']:<8} {r['reason'] or r['tx'][:18]}", flush=True)
    rows = lab.all()
    for r in rows:
        print(f"{r['attack']} {r['name']:<28} {r['side']:<16} {r['outcome']:<8} {r['reason'] or r['tx'][:18]}  {r.get('note', '')}")
    out = ROOT / "docs" / "alta" / f"attacks-{date.today().isoformat()}.json"
    out.write_text(json.dumps({"date": date.today().isoformat(), "network": "alta testnet (chain 63825)", "principal": st["principal"],
                               "attacks": {str(k): {"name": v[0], "does": v[1], "class": v[2]} for k, v in ATTACKS.items()},
                               "rows": rows}, indent=1), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
