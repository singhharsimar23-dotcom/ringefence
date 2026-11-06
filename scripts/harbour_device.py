"""Runs on HARBOUR's device, never on the Ringfence server. Signs and binds one-shot top-up mandates with Harbour's owner
key, prints the terms read back from each credential (what you see is what you bind), then hands the server only the
credential and its pull key. Only the owner's bind makes a mandate payable, so the server can never mint one.

The payee is typed here, not taken from the server: a server that chose it could make Harbour blind-sign its own wallet.

  python scripts/harbour_device.py --device DIR --principal 0x.. --payee 0x.. --cap 50 --to SERVER/signed [--count 1] [--days 30] [--yes]
"""
import argparse
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import awx  # noqa: E402

for n in ("METAL_RPC_URL", "METAL_RPC_SECRET"):
    os.environ.setdefault(n, awx.env(n) or "")
from ringfence import metal  # noqa: E402

SHOW = ("mandate", "principal", "payee", "per-payment-cap", "budget", "max-occurrences", "expiry", "bound")


def cli(args, cwd):
    rc, out = metal.run_cli([*args, *metal.NET], cwd, timeout=180)
    f = metal.parse(out)
    if rc:
        sys.exit(f"metal: {f.get('error') or f.get('reason') or rc}")
    return f


def main():
    a = argparse.ArgumentParser()
    for k in ("--device", "--principal", "--payee", "--cap", "--to"):
        a.add_argument(k, required=True)
    a.add_argument("--count", type=int, default=1)
    a.add_argument("--days", type=int, default=30)
    a.add_argument("--yes", action="store_true")
    o = a.parse_args()
    dev = Path(o.device).resolve()
    key = str(dev / "owner.json")  # absolute: the CLI runs inside the credential's own directory
    for i in range(o.count):
        name = f"harbour-{int(time.time())}-{i}"
        wd = dev / "out" / name
        cli(["mandate", "credential", "create", "--principal", o.principal, "--payee", o.payee, "--cap", o.cap, "--budget", o.cap,
             "--max-occurrences", "1", "--expires-in", str(o.days * 86400), "--key", key, "--out", "m.json",
             "--description", f"Harbour payroll top-up {name}"], wd)
        st = cli(["mandate", "status", "--credential", "m.json"], wd)  # read back from the credential, not from what we asked for
        print(f"\n{name}\n" + "\n".join(f"  {k:16} {st.get(k)}" for k in SHOW))
        if st.get("payee", "").lower() != o.payee.lower() or st.get("max-occurrences") != "1":
            sys.exit("the credential does not say what was asked: not binding it")
        if not o.yes and input("bind these terms on Harbour's account? type BIND: ").strip() != "BIND":
            sys.exit("not bound")
        b = cli(["mandate", "bind", "--credential", "m.json", "--key", key], wd)
        print(f"  bound            {b.get('bound')}\n  bind tx          {metal.EXPLORER}{b.get('transaction')}")
        dest = Path(o.to) / name
        dest.mkdir(parents=True)
        for f in ("m.json", "m.key.json"):  # the credential and the key that may pull within it; no owner or issuer key
            shutil.copy2(wd / f, dest / f)
        print(f"  handed to server {dest}")


if __name__ == "__main__":
    main()
