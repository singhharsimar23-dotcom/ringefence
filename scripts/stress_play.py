"""Playground stress: 20 concurrent world requests against the real manager with real (fake-backend) child processes.
Checks that the caps hold, a world killed mid-run is marked failed and frees its slot, and the reaper never ends a
world that is paying out. Usage: uv run python scripts/stress_play.py   (about 30 seconds, no keys needed)"""
import os
import sys
import tempfile
import threading
import time
from pathlib import Path

os.environ["RF_VAR"] = tempfile.mkdtemp(prefix="rf-stress-")
os.environ["RF_AGENT"] = "scripted"
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ringfence import copy  # noqa: E402
from ringfence import playground as P  # noqa: E402

SPEC = {"employers": [{"name": "Stress Co", "pays_from": "GBP",
                       "people": [{"name": "Ada Lovelace", "country": "GB", "hours": "40", "rate": "50"}]}]}
m = P.Manager(live_probe=lambda: False)
results, lock = [], threading.Lock()


def one(i: int) -> None:
    spec = P.Spec.model_validate({"employers": [{**SPEC["employers"][0], "name": f"Stress {i} Co"}]})
    try:
        w = m.create(spec, "fake", f"10.0.0.{i}")
        out = ("ok", w.wid)
    except P.PlayError as e:
        out = (e.status, e.detail)
    with lock:
        results.append(out)


threads = [threading.Thread(target=one, args=(i,)) for i in range(20)]
[t.start() for t in threads]
[t.join() for t in threads]
ok = [r[1] for r in results if r[0] == "ok"]
refused = [r for r in results if r[0] != "ok"]
print(f"accepted {len(ok)}, refused {len(refused)}")
assert len(ok) == m.fake_max + m.queue_max, "caps: running + queue must equal what was accepted"
assert all(r == (429, copy.PLAY_FULL) for r in refused), refused

deadline = time.time() + 60
while time.time() < deadline and sum(1 for w in m.worlds.values() if w.status == "ready") < m.fake_max:
    time.sleep(0.5)
ready = [w for w in m.worlds.values() if w.status == "ready"]
assert len(ready) == m.fake_max, [w.status for w in m.worlds.values()]
print("two worlds ready")

victim = ready[0]
queued_before = len(m.queue)
victim.proc.kill()
deadline = time.time() + 20
while time.time() < deadline and victim.status != "failed":
    time.sleep(0.5)
assert victim.status == "failed" and victim.error == copy.WORLD_STOPPED, victim.status
assert len(m.queue) == queued_before - 1, "the freed slot should have gone to the next in line"
print("killed world marked failed, slot freed to the queue")

# the reaper must not end a world that is paying out
other = next(w for w in m.worlds.values() if w.status == "ready")
real_probe = m.probe
m.probe = lambda w: {"lanes": {"northwind": {"state": "RELEASING"}}} if w is other else real_probe(w)
other.created -= m.total_s + 1  # past the 30 minute ceiling
m.reap()
assert other.status == "ready" and other.extra == 120, (other.status, other.extra)
m.probe = real_probe
other.created -= 300  # the two extra minutes have run out
m.reap()
print("reaper held a RELEASING world, then ended it once it was quiet:", other.status)
assert other.status == "expired"
m.shutdown()
assert not Path(os.environ["RF_VAR"], "play").exists()
print("PASS")
