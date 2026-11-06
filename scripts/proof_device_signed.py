"""Server side of the Metal custody fix, live on testnet. The server holds NO Harbour owner key, only what
scripts/harbour_device.py handed it. It pulls within that credential, then plays the owner of this server:
  1. pull the shortfall              -> paid
  2. pull the same credential again  -> refused on chain (one occurrence)
  3. pull to a lookalike wallet      -> refused on chain (payee not listed)
  4. use the one funded key it still has (the platform treasury key) to write a mandate on HARBOUR's account,
     payee = the lookalike, cap = Harbour's whole balance, and bind it   -> Metal refuses the bind
Then the pulled USDZ goes back to Harbour. All output passes through metal.scrub.
  python scripts/proof_device_signed.py [amount=0.05]"""
import os
import sys
import time
from decimal import Decimal
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import awx  # noqa: E402

for n in ("METAL_RPC_URL", "METAL_RPC_SECRET"):
    os.environ.setdefault(n, awx.env(n) or "")
from ringfence import metal  # noqa: E402

amt = Decimal(sys.argv[1] if len(sys.argv) > 1 else "0.05")
m, ts = metal.Metal(), int(time.time())
c = m.cfg()
fake = metal.lookalike(c["settlement"])
rd = m.dir / "runs" / f"devsig-{ts}"
tk = m.treasury_key()


def show(label, rc, f):
    tx = f.get("transaction")
    print(f"{label:58} exit {rc}  {f.get('outcome') or f.get('error') or f.get('bound') or ''}"
          + (f"  {f.get('reason')}" if f.get("reason") else "") + (f"\n{'':58} {metal.EXPLORER}{tx}" if tx else ""))


def cli(args, cwd=rd):
    rc, out = metal.run_cli([*args, *metal.NET], cwd, timeout=240)
    return rc, metal.parse(out)


print("server holds Harbour's owner key:", m.mints(), " (the fix: False)")
assert not m.mints(), "move owner.json to Harbour's device first"
bound = m._mandate(rd, amt, rd.name, 3600)
print("credential from Harbour's device:", bound["bound"])

show("1 pull the shortfall to the settlement wallet", *cli(["mandate", "pull", "--credential", "m.json", "--to", c["settlement"],
                                                            "--amount", str(amt), "--payment-id", rd.name]))
show("2 same credential, pull again (new payment id)", *cli(["mandate", "pull", "--credential", "m.json", "--to", c["settlement"],
                                                             "--amount", str(amt), "--payment-id", rd.name + "-again",
                                                             "--record-refusal", "--key", tk]))
show(f"3 pull to lookalike {fake[:8]}..{fake[-4:]}", *cli(["mandate", "pull", "--credential", "m.json", "--to", fake,
                                                         "--amount", str(amt), "--record-refusal", "--key", tk]))
ev = rd.parent / f"{rd.name}-evil"
rc, f = cli(["mandate", "credential", "create", "--principal", c["principal"], "--payee", fake, "--cap", str(amt), "--budget", str(amt),
             "--max-occurrences", "1", "--expires-in", "3600", "--key", tk, "--out", "evil.json",
             "--description", "probe: bind by a key that is not the owner"], ev)
show("4a server writes a mandate on Harbour's account", rc, f)
show("4b ...and binds it with the funded treasury key", *cli(["mandate", "bind", "--credential", "evil.json", "--key", tk], ev))
show("   status of that mandate", *cli(["mandate", "status", "--credential", "evil.json"], ev))

try:
    m.recycle({"run_dir": rd.name, "usdz": str(amt)})
    print("pulled USDZ sent back to Harbour")
except metal.MetalError as e:  # a settlement that is a bare key (old setup) has no account to sign the return mandate
    print("not sent back (stays in our own settlement wallet):", metal.scrub(str(e))[:160])
