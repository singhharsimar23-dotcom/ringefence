"""The approver's device for Alta settlement. Run it where the employer's owner key lives, never on the Ringfence server.

  python scripts/alta_device.py sign --export batch.json --book payees.json --owner owner.json --principal 0x.. --to server_creds/
  python scripts/alta_device.py revoke-all --run <run_id> --book payees.json --owner owner.json --principal 0x..

`payees.json` is {"contractor_id": "0xwallet"}: the device's own book. The server's export is checked against it and against
the approved batch hash; see ringfence/alta_device.py for every refusal. `sign` shows each line and asks for BIND."""
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
from ringfence import metal
from ringfence.alta_device import Device, DeviceRefused


def show(terms: list[dict]) -> bool:
    for t in terms:
        print(f"  {t['contractor_id']:<12} {t['payee']}  USD {t['usd']}  =  {t['usdz']} USDZ, one pull, {t['expires_in']}s")
    return input("type BIND to sign and bind these mandates: ").strip() == "BIND"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["sign", "revoke-all"])
    ap.add_argument("--export")
    ap.add_argument("--run")
    ap.add_argument("--book", required=True)
    ap.add_argument("--owner", required=True)
    ap.add_argument("--principal", required=True)
    ap.add_argument("--to")
    ap.add_argument("--out", default=str(Path(os.environ.get("RF_DEVICE_OUT", "device-out"))))
    ap.add_argument("--yes", action="store_true", help="skip the BIND prompt (the unattended device service only)")
    a = ap.parse_args()
    dev = Device(metal.run_cli, Path(a.owner), Path(a.out), json.loads(Path(a.book).read_text(encoding="utf-8")), a.principal)
    try:
        if a.cmd == "revoke-all":
            print("revoked:", ", ".join(dev.revoke_all(a.run)) or "nothing was still payable")
            return 0
        done = dev.sign(json.loads(Path(a.export).read_text(encoding="utf-8")), Path(a.to), (lambda t: True) if a.yes else show)
    except DeviceRefused as e:
        print("REFUSED:", e)
        return 1
    print(f"signed and bound {len(done)} mandates, handed over to {a.to}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
