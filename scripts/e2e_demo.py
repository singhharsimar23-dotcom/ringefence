"""Three-employer demo, end to end over HTTP. Exit 0 only if every lane is DONE, the report is ok and certs are valid.
Usage: uv run python scripts/e2e_demo.py [http://127.0.0.1:8000]   (start the app with --backend fake for offline use)"""
import json
import sys
import time
import urllib.error
import urllib.request

H = (sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000").rstrip("/")


def call(method, path, body=None):
    time.sleep(1.2)  # the public throttle allows one POST per second
    req = urllib.request.Request(H + path, method=method, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=150) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def lanes():
    return {t: ln["state"] for t, ln in call("GET", "/api/state")[1]["lanes"].items()}


def wait(pred, what, tries=40):
    for _ in range(tries):
        lane = lanes()
        if pred(lane):
            return lane
        time.sleep(3)
    sys.exit(f"FAIL waiting for {what}: {lane}")


print("reset", call("POST", "/api/reset", {"user": "maya"}))
print("start", call("POST", "/api/start", {"user": "maya"})[0])
print(wait(lambda s: s["northwind"] == "AWAITING_APPROVAL" and s["harbour"] == "AWAITING_FUNDS", "agent plan"))
print("approve northwind", call("POST", "/api/approve", {"user": "priya", "tenant": "northwind"}))
print("topup harbour", call("POST", "/api/scenario/harbour_topup")[0])
print(wait(lambda s: s["harbour"] == "AWAITING_APPROVAL", "harbour funded"))
print("approve harbour", call("POST", "/api/approve", {"user": "lee", "tenant": "harbour"}))
print(wait(lambda s: all(v == "DONE" for v in s.values()), "all DONE", tries=60))
st, p = call("GET", "/api/proof")
ok = st == 200 and p["report"]["ok"] and all(c["valid"] for c in p["certs"].values())
print("proof", st, "report ok" if st == 200 and p["report"]["ok"] else p, {t: c["valid"] for t, c in p.get("certs", {}).items()})
sys.exit(0 if ok else 1)
