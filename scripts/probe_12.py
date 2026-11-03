"""P12: one live world on the playground account, "Weekly pay" preset, run to PAID, then re-check. Prints timings.
Usage: uv run python scripts/probe_12.py https://<host>   (needs a free live slot; takes about 2 minutes)"""
import re
import sys
import time
from pathlib import Path

import httpx

base = sys.argv[1].rstrip("/")
text = re.search(r'text:\s*"([^"]+)"', (Path(__file__).parent.parent / "static" / "copy.js").read_text(encoding="utf-8")).group(1)
c = httpx.Client(base_url=base, timeout=60)
t0 = time.time()
lap = lambda s: print(f"{time.time() - t0:6.1f}s  {s}", flush=True)  # noqa: E731


def wait(fn, ok, what, limit=240):
    end = time.time() + limit
    while time.time() < end:
        v = fn()
        if ok(v):
            return v
        time.sleep(2)
    raise SystemExit(f"timeout: {what}")


draft = c.post("/api/play/draft", json={"text": text}).json()
spec = draft["spec"]
spec["employers"] = spec["employers"][:1]
lap(f"draft via {draft['source']}")
if len(sys.argv) > 2:  # resume a world a previous run left waiting for approval
    wid = sys.argv[2]
else:
    w = c.post("/api/play/worlds", json={"spec": spec, "backend": "live"})
    w.raise_for_status()
    wid = w.json()["wid"]
lap(f"world {wid} created")
wait(lambda: c.get(f"/api/play/worlds/{wid}").json(), lambda v: v["status"] == "ready", "ready")
lap("world ready")
api = f"/play/{wid}/api"
if len(sys.argv) < 3:
    c.post(f"{api}/start", json={"user": "operator"}).raise_for_status()
st = wait(lambda: c.get(f"{api}/state").json(), lambda s: any(ln["state"] == "AWAITING_APPROVAL" and ln["diff"] for ln in s["lanes"].values()), "approval")
lap("first agent result: awaiting approval")
slot, lane = next((k, v) for k, v in st["lanes"].items() if v["state"] == "AWAITING_APPROVAL" and v["diff"])
who = next(u["id"] for u in st["users"] if u["role"] == lane["diff"]["approver_role"])
c.post(f"{api}/approve", json={"user": who, "tenant": slot}).raise_for_status()
st = wait(lambda: c.get(f"{api}/state").json(), lambda s: all(ln["state"] == "DONE" for ln in s["lanes"].values()), "DONE", 300)
lap("all lines PAID, run DONE")
tl = c.get(f"{api}/timeline?after=0").json()
tid = next(r["detail"]["transfer_id"] for r in tl if r["detail"].get("transfer_id"))
rc = c.get(f"{api}/recheck/{tid}").json()
lap(f"re-check status {rc['status']} (ledger says {[ln['pill'] for ln in st['lanes'][slot]['lines']]})")
proof = c.get(f"{api}/proof").json()
lap(f"proof ok={proof['report']['ok']} certs={ {k: v['valid'] for k, v in proof['certs'].items()} }")
