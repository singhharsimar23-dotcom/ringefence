"""Phase 0 spike for the Alta settlement build (docs/ALTA_SETTLEMENT.md). Answers the open questions against the live
testnet BEFORE any adapter code exists. Prints the spend first and does nothing without --go.

Spend: every paying step moves 0.01 USDZ from Harbour's test account to the platform settlement wallet (both ours);
the facilitator pays gas for pulls, the owner key pays for bind/revoke. Expect about 0.05 USDZ moved and under 15 bind
or revoke transactions. Nothing here touches Airwallex. All CLI output goes through metal.scrub.

  python scripts/probe_alta.py --go [--only 1,5,7]    # report: var/alta/probe/<ts>/report.json
"""
import argparse
import base64
import json
import os
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import awx

for n in ("METAL_RPC_URL", "METAL_RPC_SECRET"):
    os.environ.setdefault(n, awx.env(n) or "")
from ringfence import metal

OWNER_DIR = ROOT / "var" / "metal" / "harbour_device"  # holds Harbour's owner key (device side, never the server's)
STATE = ROOT / "var" / "metal" / "harbour" / "state.json"
AMT = "0.01"
EXPLAIN = {
    1: "is --description inside the signed credential, and does a 118-char rf:<hash>:<request_id> survive intact",
    2: "revoke needs the owner key: the pull key alone cannot revoke",
    3: "pending (exit 3) output: observed only if it happens, cannot be forced",
    4: "held (exit 4) output: observed only if it happens, needs a receive policy on the payee",
    5: "a refused pull with --record-refusal must not consume the single occurrence",
    6: "refusal code for an insufficient balance",
    7: "re-pull after paid: same payment id, new payment id, fresh HOME",
    8: "gas per bind and revoke; can bound mandates on a principal be listed",
    9: "Alta's own MCP under a line credential: mandate_pull to another address is refused",
}


class Probe:
    def __init__(self, base: Path):
        self.base, self.report, self.n = base, {}, 0
        st = json.loads(STATE.read_text(encoding="utf-8"))
        self.principal, self.payee = st["principal"], st["settlement"]
        self.owner = str(OWNER_DIR / "owner.json")
        self.treasury = str(metal.Metal().treasury_key())

    def cli(self, label: str, args: list[str], cwd: Path, env: dict | None = None):
        old = {k: os.environ.get(k) for k in (env or {})}
        os.environ.update(env or {})
        try:
            rc, out = metal.run_cli([*args, *metal.NET], cwd, timeout=180)
        except metal.MetalError as e:
            rc, out = -1, str(e)
        finally:
            for k, v in old.items():
                os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)
        f = metal.parse(out)
        print(f"  [{label}] exit {rc} {f.get('outcome') or f.get('reason') or f.get('error') or ''}")
        return rc, f, out

    def mint(self, name: str, desc: str, cap=AMT, payee=None, occ="1", bind=True):
        """One credential in its own dir, signed by the owner key, optionally bound. Returns (dir, bind fields)."""
        self.n += 1
        d = self.base / f"{self.n:02d}-{name}"
        rc, _, out = self.cli("create", ["mandate", "credential", "create", "--principal", self.principal, "--payee", payee or self.payee,
                                         "--cap", cap, "--budget", cap, "--max-occurrences", occ, "--expires-in", "3600",
                                         "--key", self.owner, "--out", "m.json", "--description", desc], d)
        assert rc == 0, out[:300]
        b = {}
        if bind:
            rc, b, out = self.cli("bind", ["mandate", "bind", "--credential", "m.json", "--key", self.owner], d)
            assert rc == 0, out[:300]
        return d, b

    def status(self, d: Path, cred="m.json"):
        return self.cli("status", ["mandate", "status", "--credential", cred], d)

    def pull(self, d: Path, amount=AMT, to=None, pid=None, record=False, env=None):
        a = ["mandate", "pull", "--credential", "m.json", "--to", to or self.payee, "--amount", amount]
        if pid:
            a += ["--payment-id", pid]
        if record:
            a += ["--record-refusal", "--key", self.treasury]
        return self.cli("pull", a, d, env)

    # ---- the nine questions ----
    def q1(self):
        desc = "rf:" + "ab" * 32 + ":" + ("rf-" + "x" * 47)
        assert len(desc) == 3 + 64 + 1 + 50
        d, _ = self.mint("desc", desc, bind=True)
        _, st, out = self.status(d)
        kept = desc in out or st.get("description") == desc
        cred = json.loads((d / "m.json").read_text(encoding="utf-8"))
        parts = cred["layer2"].split("~")
        # the description is the `prompt_summary` of a layer-2 SD-JWT disclosure: find it, change one character, re-encode
        hit = None
        for i, part in enumerate(parts):
            try:
                arr = json.loads(base64.urlsafe_b64decode(part + "=" * (-len(part) % 4)))
            except ValueError:
                continue
            if isinstance(arr, list) and len(arr) == 2 and isinstance(arr[1], dict) and arr[1].get("prompt_summary") == desc:
                arr[1]["prompt_summary"] = desc[:-1] + "Z"
                parts[i] = base64.urlsafe_b64encode(json.dumps(arr, separators=(",", ":")).encode()).decode().rstrip("=")
                hit = i
        in_file = hit is not None
        t = d.parent / (d.name + "-tamper")
        t.mkdir()
        (t / "m.key.json").write_bytes((d / "m.key.json").read_bytes())
        (t / "m.json").write_text(json.dumps({**cred, "layer2": "~".join(parts)}), encoding="utf-8")
        rc_s, _, _ = self.status(t)
        rc_p, fp, out_p = self.pull(t)
        # a 'paid' here would spend the occurrence of the TAMPERED copy only if the chain accepted it: that is the finding
        return {"survives_in_status": kept, "description_found_in_layer2_disclosure": in_file, "full_length": len(desc),
                "tampered_status_exit": rc_s, "tampered_pull_exit": rc_p, "tampered_pull": fp.get("outcome") or fp.get("reason"),
                "tampered_output": out_p[:300],
                "description_is_signed": rc_s != 0 or rc_p != 0,
                "fallback_needed": not (rc_s != 0 or rc_p != 0)}

    def q2(self):
        d, _ = self.mint("revoke", "probe revoke")
        rc, _, out = self.cli("revoke with the pull key only", ["mandate", "revoke", "--credential", "m.json", "--key", str(d / "m.key.json")], d)
        rc_o, fo, _ = self.cli("revoke with the owner key", ["mandate", "revoke", "--credential", "m.json", "--key", self.owner], d)
        _, fp, _ = self.pull(d)
        return {"pull_key_can_revoke": rc == 0, "pull_key_output": out[:200], "owner_revoke_exit": rc_o,
                "owner_revoke_tx": fo.get("transaction"), "pull_after_revoke": fp.get("reason") or fp.get("outcome")}

    def q5(self):
        d, _ = self.mint("refuse", "probe refusal keeps occurrence")
        _, f1, _ = self.pull(d, amount="0.02", record=True)  # above the cap: refused, recorded on chain
        _, st1, _ = self.status(d)
        rc2, f2, _ = self.pull(d, pid="probe-after-refusal")
        _, st2, _ = self.status(d)
        return {"refusal": f1.get("reason"), "refusal_tx": f1.get("transaction"), "payments_after_refusal": st1.get("payments"),
                "then_pull_exit": rc2, "then_pull": f2.get("outcome"), "pay_tx": f2.get("transaction"),
                "payments_after_pay": st2.get("payments"), "occurrence_survives_refusal": rc2 == 0}

    def q6(self):
        with tempfile.TemporaryDirectory() as t:
            poor = Path(t) / "poor.json"
            rc, f, out = self.cli("new unfunded account", ["account", "create", "--out", str(poor)], self.base / "poor")
            if rc != 0:
                return {"error": out[:200]}
            addr = f.get("account")
            d = self.base / "06-poor"
            self.cli("create", ["mandate", "credential", "create", "--principal", addr, "--payee", self.payee, "--cap", AMT, "--budget", AMT,
                                "--max-occurrences", "1", "--expires-in", "3600", "--key", str(poor), "--out", "m.json"], d)
            rb, _, ob = self.cli("bind", ["mandate", "bind", "--credential", "m.json", "--key", str(poor)], d)
            rp, fp, op = self.pull(d, pid="probe-poor")
            return {"bind_exit_unfunded": rb, "bind_output": ob[:200], "pull_exit": rp, "reason": fp.get("reason") or fp.get("outcome"),
                    "output": op[:300]}

    def q7(self):
        d, _ = self.mint("repull", "probe re-pull")
        _, a, _ = self.pull(d, pid="probe-same")
        _, b, _ = self.pull(d, pid="probe-same")
        _, c, _ = self.pull(d, pid="probe-new")
        home = Path(tempfile.mkdtemp(prefix="probe-home-"))
        _, e, _ = self.pull(d, pid="probe-fresh-home", env={"HOME": str(home), "USERPROFILE": str(home)})
        _, st, _ = self.status(d)
        return {"first": a.get("outcome"), "same_id_again": b.get("outcome"), "new_id": c.get("outcome") or c.get("reason"),
                "fresh_home_new_id": e.get("outcome") or e.get("reason"), "payments_total": st.get("payments"),
                "safe": st.get("payments") == "1"}

    def q8(self):
        _, b = self.mint("gas", "probe gas")
        return {"bind_fields": {k: v for k, v in b.items() if k in ("transaction", "gas", "gas-used", "fee", "bound")},
                "bind_output_keys": sorted(b), "list_mandates_cmd": "none in `--help`: no list/ls subcommand (checked 0.3.3)",
                "note": "read the bind tx on the explorer for gas; a balance read needs `status <txHash>` or a direct RPC call"}

    def q9(self):
        d, _ = self.mint("mcp", "probe alta mcp")
        cmd = [*metal._cli_cmd(), "mcp", "--mandate", "m.json"]
        init = {"jsonrpc": "2.0", "id": 1, "method": "initialize",
                "params": {"protocolVersion": "2024-11-05", "capabilities": {}, "clientInfo": {"name": "probe", "version": "0"}}}
        call = {"jsonrpc": "2.0", "id": 2, "method": "tools/call",
                "params": {"name": "mandate_pull", "arguments": {"to": "0x" + "11" * 20, "amount": AMT, "paymentId": "probe-mcp", "network": "testnet"}}}
        msgs = "\n".join(json.dumps(m) for m in (init, {"jsonrpc": "2.0", "method": "notifications/initialized"}, call)) + "\n"
        import subprocess
        try:
            p = subprocess.run(cmd, check=False, input=msgs, cwd=d, capture_output=True, text=True, timeout=120, encoding="utf-8")
            out = metal.scrub(p.stdout + p.stderr)
        except (subprocess.TimeoutExpired, OSError) as e:
            return {"error": type(e).__name__}
        _, st, _ = self.status(d)
        return {"tool_output_tail": out[-600:], "payments_after": st.get("payments"),
                "refused_other_address": "payee" in out.lower() and st.get("payments") == "0"}


def main():
    a = argparse.ArgumentParser()
    a.add_argument("--go", action="store_true")
    a.add_argument("--only", default="")
    o = a.parse_args()
    want = [int(x) for x in o.only.split(",") if x] or [1, 2, 5, 6, 7, 8, 9]
    print(__doc__.split("\n\n")[1].strip())
    for k in sorted(EXPLAIN):
        print(f"  {k}. {EXPLAIN[k]}{'' if k in want or k in (3, 4) else '  (skipped)'}")
    if not o.go:
        sys.exit("\nnothing run: pass --go to spend")
    base = ROOT / "var" / "alta" / "probe" / time.strftime("%Y%m%d-%H%M%S")
    base.mkdir(parents=True)
    p = Probe(base)
    for k in want:
        print(f"\n== {k}. {EXPLAIN[k]}")
        try:
            p.report[k] = getattr(p, f"q{k}")()
        except (AssertionError, metal.MetalError) as e:
            p.report[k] = {"error": metal.scrub(str(e))[:300]}
        print("  ->", json.dumps(p.report[k])[:400])
    p.report["3_4"] = "pending/held cannot be forced here: record the real output if either ever appears"
    (base / "report.json").write_text(json.dumps(p.report, indent=1), encoding="utf-8")
    ks = p.report.get(5, {}), p.report.get(7, {})
    print("\nreport:", base / "report.json")
    if not ks[0].get("occurrence_survives_refusal") or not ks[1].get("safe"):
        print("KILL CRITERIA HIT (item 5 or 7): stop and report to the founder before building the adapter")
        sys.exit(2)


if __name__ == "__main__":
    main()
