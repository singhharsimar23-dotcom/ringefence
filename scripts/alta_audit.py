"""An auditor's check of an Alta run that needs neither the Ringfence server nor its ledger.

  python scripts/alta_audit.py --export batch.json --creds creds/ [--book payees.json]

Inputs: the approved batch the device received (batch.json), the credentials the server holds (one folder per line), and
optionally the device's payee book. For each line it reads the credential's own state from the chain and prints PASS or
FAIL: the payee, the amount, one pull, the approved batch hash in the signed description, and how many payments the chain
shows. It recomputes the batch hash first. It cannot see a mandate that is not in the folder you give it."""
import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import awx

for n in ("METAL_RPC_URL", "METAL_RPC_SECRET"):
    os.environ.setdefault(n, awx.env(n) or "")
from ringfence.alta_verify import audit


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", required=True)
    ap.add_argument("--creds", required=True)
    ap.add_argument("--book")
    a = ap.parse_args()
    book = json.loads(Path(a.book).read_text(encoding="utf-8")) if a.book else None
    rows = audit(json.loads(Path(a.export).read_text(encoding="utf-8")), Path(a.creds), book)
    for r in rows:
        print(f"{'PASS' if r['ok'] else 'FAIL'}  {r['line']:<12} {r['why']}" + (f"  payments={r['payments']} spent={r['spent_usdz']}" if "payments" in r else ""))
    return 0 if all(r["ok"] for r in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
