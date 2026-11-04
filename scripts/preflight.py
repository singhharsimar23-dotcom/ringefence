"""Read-only pre-demo check. Prints one line per check and GO or NO-GO. Moves no money, writes nothing.
Usage: python scripts/preflight.py [--url https://host]   (default http://127.0.0.1:8000)
Secrets are never printed: only OK/FAIL and public numbers."""
import argparse
import json
import sys
import time
from decimal import Decimal
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ringfence.config import ROOT, env  # noqa: E402  (reads HKCU\Environment on Windows)

RESULTS = ROOT / "docs" / "gauntlet" / "results.json"
MAX_RESULTS_AGE_DAYS = 14
KESTREL_USD_BASELINE = Decimal("10000000")
HARBOUR_AUD_MIN = Decimal("0")  # Harbour must start short: a zero AUD balance stages the top-up story


def login(base: str, acct: str | None) -> httpx.Response:
    h = {"x-client-id": env("AWX_CLIENT_ID"), "x-api-key": env("AWX_API_KEY")}
    if acct:
        h["x-login-as"] = acct
    return httpx.post(f"{base}/api/v1/authentication/login", headers=h, content=b"", timeout=30)


def balances(base: str, token: str) -> dict[str, Decimal]:
    r = httpx.get(f"{base}/api/v1/balances/current", headers={"Authorization": f"Bearer {token}"}, timeout=30)
    r.raise_for_status()
    return {b["currency"]: Decimal(str(b["available_amount"])) for b in r.json()}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", default="http://127.0.0.1:8000")
    a = ap.parse_args()
    results: list[tuple[str, bool, str]] = []

    def check(name: str, fn) -> None:
        try:
            ok, detail = fn()
        except Exception as e:  # a check that cannot run is a NO-GO, never a crash
            ok, detail = False, type(e).__name__
        results.append((name, ok, detail))
        print(f"{'OK  ' if ok else 'FAIL'} {name}: {detail}")

    base = env("AWX_BASE_URL")
    accts = {n: env(k) for n, k in (("platform", "AWX_PLATFORM_ACCOUNT"), ("northwind", "AWX_EMPLOYER_A"),
                                    ("kestrel", "AWX_EMPLOYER_B"), ("harbour", "AWX_EMPLOYER_C"))}
    tokens: dict[str, str] = {}

    def token_for(n: str):
        r = login(base, accts[n])
        if r.status_code in (200, 201):
            tokens[n] = r.json()["token"]
        return r.status_code in (200, 201), f"HTTP {r.status_code}"
    for n in accts:
        check(f"token {n}", lambda n=n: token_for(n))

    def isolation():  # an employer token must not reach another account
        if "northwind" not in tokens:
            return False, "no northwind token"
        r = httpx.get(f"{base}/api/v1/balances/current", timeout=30,
                      headers={"Authorization": f"Bearer {tokens['northwind']}", "x-on-behalf-of": accts["platform"]})
        return r.status_code == 401, f"HTTP {r.status_code} (want 401)"
    check("platform 401 probe", isolation)

    def harbour():
        b = balances(base, tokens["harbour"])
        aud = b.get("AUD", Decimal(0))
        return aud <= HARBOUR_AUD_MIN, f"AUD {aud} (a short Harbour needs 0; press Start over if not)"
    check("harbour AUD", harbour)

    def kestrel():
        usd = balances(base, tokens["kestrel"]).get("USD", Decimal(0))
        return usd <= KESTREL_USD_BASELINE, f"USD {usd} (baseline {KESTREL_USD_BASELINE})"
    check("kestrel baseline", kestrel)

    def metal():
        state = ROOT / "var" / "metal" / "harbour" / "state.json"
        if not state.exists():
            return False, "var/metal/harbour/state.json missing"
        rpc = env("METAL_RPC_URL")
        r = httpx.post(rpc, json={"jsonrpc": "2.0", "id": 1, "method": "eth_blockNumber", "params": []},
                       headers={"x-api-secret": env("METAL_RPC_SECRET", "")}, timeout=20)
        return r.status_code == 200 and "result" in r.json(), f"RPC HTTP {r.status_code} (wallet balance is not read here)"
    check("metal wallet and RPC", metal)

    def anthropic():
        r = httpx.get("https://api.anthropic.com/v1/models", timeout=20,
                      headers={"x-api-key": env("ANTHROPIC_API_KEY"), "anthropic-version": "2023-06-01"})
        return r.status_code == 200, f"HTTP {r.status_code}"
    check("anthropic key", anthropic)

    def healthz():
        r = httpx.get(f"{a.url.rstrip('/')}/healthz", timeout=20)
        j = r.json()
        return r.status_code == 200 and j.get("ok") is True, f"HTTP {r.status_code}, head {j.get('head')}, queue {j.get('queue')}"
    check("/healthz", healthz)

    def gauntlet():
        if not RESULTS.exists():
            return False, f"{RESULTS.relative_to(ROOT)} missing"
        age = (time.time() - RESULTS.stat().st_mtime) / 86400
        json.loads(RESULTS.read_text(encoding="utf-8"))
        return age <= MAX_RESULTS_AGE_DAYS, f"{age:.1f} days old (max {MAX_RESULTS_AGE_DAYS})"
    check("gauntlet results", gauntlet)

    go = all(ok for _, ok, _ in results)
    print("GO" if go else "NO-GO")
    return 0 if go else 1


if __name__ == "__main__":
    raise SystemExit(main())
