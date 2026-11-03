"""One-time, idempotent Metal treasury setup for Harbour. Plays Harbour's finance lead (the owner key is Harbour's) and
creates the platform's settlement address. Needs METAL_RPC_URL and METAL_RPC_SECRET in the environment.
Usage: python scripts/metal_setup.py [USDZ_TARGET=900]   Faucet: 100 USDZ per grant, about one a minute, 10 a day per IP."""
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ringfence import metal  # noqa: E402

for n in metal.SECRETS:  # a Windows shell started before setx does not see them
    if not os.environ.get(n) and sys.platform == "win32":
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
            os.environ[n] = winreg.QueryValueEx(k, n)[0]

target = int(sys.argv[1]) if len(sys.argv) > 1 else 900
m = metal.Metal()
d = m.dir
d.mkdir(parents=True, exist_ok=True)
sf = d / "state.json"
st = json.loads(sf.read_text()) if sf.exists() else {}
save = lambda: sf.write_text(json.dumps(st, indent=1))  # noqa: E731

if "principal" not in st:
    f = m.call(["account", "create", "--out", "owner.json"])
    st.update(principal=f["account"], owner=f["owner"], funded_usdz=0)
    save()
    print("[Harbour's finance lead] created Harbour's Metal account", st["principal"])
if "settlement" not in st:
    rc, out = m.runner(["key", "create", "--out", "settlement.json"], d)
    st["settlement"] = metal.parse(out)["address"]
    save()
    print("[platform] created the settlement address", st["settlement"])
for p in (d / "owner.json", d / "settlement.json"):
    try:
        p.chmod(0o600)
    except OSError:
        pass

while st.get("funded_usdz", 0) < target:
    rc, out = m.runner(["fund", st["principal"], "--network", "testnet"], d)
    if rc == 0:
        st["funded_usdz"] = st.get("funded_usdz", 0) + 100
        save()
        print(f"[faucet] funded Harbour's account, total granted {st['funded_usdz']} USDZ")
    elif wait := re.search(r"retry in (\d+) s", out):
        time.sleep(int(wait.group(1)) + 2)
    else:
        sys.exit(f"faucet refused: {out.strip()[:200]}")
print("ready: set RF_METAL=1 for the demo")
