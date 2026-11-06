"""Ringfence under the same faults as bench/market_agent.py, on the same LIVE Northwind account.
Northwind's GBP and EUR lines (Ada GBP 450, Lukas EUR 400: no FX, so Northwind's demo AUD story is untouched), each trial
on its own throwaway beneficiaries (nickname BENCH*) pinned in a throwaway registry, its own ledger, its own run id.
Every transfer is cancelled afterwards and the beneficiaries deleted.
  lost      the first create lands, its response is lost
  restart   the process dies right after the first create; a new process starts (same ledger) / (ledger lost too)
  double    two workers on one ledger, and two hosts with separate ledgers, release the same run at the same moment
  repoint   Ada's payee is edited in place before the run
  approval  ...edited after the human approved, before release
  race      ...edited in the milliseconds between Ringfence's release check and the create
  python bench/ringfence_bench.py FAULT [trials=1]"""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
import threading
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts")]
import awx as _env  # noqa: E402

for n in ("AWX_CLIENT_ID", "AWX_API_KEY", "AWX_BASE_URL", "AWX_EMPLOYER_A", "AWX_EMPLOYER_B", "AWX_EMPLOYER_C",
          "AWX_PLATFORM_ACCOUNT"):
    os.environ.setdefault(n, _env.env(n) or "")
REAL_REG = json.loads((ROOT / "var" / "registry.json").read_text(encoding="utf-8"))
os.environ["RF_VAR"] = VAR = tempfile.mkdtemp(prefix="rfbench-")  # before ringfence reads var_dir()
os.environ.pop("RF_DEMO_TAKES", None)

from market_agent import MULE, close, sweep  # noqa: E402

from ringfence import beneficiaries as ben, seed, store  # noqa: E402
from ringfence.awx import Awx, TenantClient  # noqa: E402
from ringfence.ledger import Ledger  # noqa: E402
from ringfence.orchestrator import Orchestrator  # noqa: E402

TENANT, PAY = "northwind", date(2026, 12, 31)
HOURS = {k: v for k, v in __import__("ringfence.inbox", fromlist=["x"]).load_timesheet(TENANT).items() if k in ("ada", "lukas")}
OUT = ROOT / "bench" / "results"


class Crash(Exception):
    pass


class Trial:
    def __init__(self, awx: Awx, fault: str, n: int):
        self.awx, self.c, self.fault, self.n = awx, awx.for_tenant(TENANT), fault, n
        self.tag = f"BENCHRF{fault[:2].upper()}{int(time.time()) % 100000}{n}"
        self.run_id = f"{PAY:%Y%m%d}-{self.tag}"  # the obligation; one per trial so trials don't adopt each other
        self.dir = Path(VAR) / self.tag
        self.dir.mkdir()
        self.payloads: dict[str, dict] = {}
        self.events: list[str] = []

    def setup(self):
        reg = json.loads(json.dumps(REAL_REG))
        t = reg["tenants"][TENANT]
        t["beneficiaries"], t["pins"] = {}, {t["fee_beneficiary"]: REAL_REG["tenants"][TENANT]["pins"][t["fee_beneficiary"]]}
        for s in seed.contractor_seeds(TENANT):
            if s["id"] not in HOURS:
                continue
            p = ben.contractor_payload(s) | {"nickname": f"{self.tag}-{s['id']}"}
            bid = self.c.post("/beneficiaries/create", p)["id"]
            self.payloads[s["id"]] = p
            t["beneficiaries"][s["id"]], t["pins"][bid] = bid, ben.fingerprint(ben.stored(p))
        (Path(VAR) / "registry.json").write_text(json.dumps(reg), encoding="utf-8")
        self.bens = dict(t["beneficiaries"])

    def repoint(self, cid="ada"):
        b = json.loads(json.dumps(self.payloads[cid]["beneficiary"]))
        b["bank_details"].update(account_number=MULE, account_routing_value1="200000", bank_name="Barclays")
        self.c.post(f"/beneficiaries/{self.bens[cid]}/update", {"transfer_methods": self.payloads[cid]["transfer_methods"], "beneficiary": b})
        self.events.append(f"repointed {cid} in place to ..{MULE[-4:]}")

    def orch(self, name="ledger.db") -> Orchestrator:
        return Orchestrator(self.awx, Ledger(self.dir / name), cert_dir=self.dir / "certs")

    def to_ready(self, o: Orchestrator) -> str:
        o.create_run(TENANT, PAY, hours=HOURS, run_id=self.run_id)
        st = o.submit(self.run_id, TENANT)
        if st == "AWAITING_APPROVAL":
            st = o.approve(self.run_id, TENANT, "bench-approver", seed.default_mandates()[TENANT].mandate.approver_role)
        return st

    def hook_create(self, on):
        """Run on(k, go) around the k-th /transfers/create. TenantClient has __slots__, so patch the class (one tenant here)."""
        orig, box = TenantClient.post_money, {"k": 0}

        def wrapped(cl, path, body):
            if path == "/transfers/create":
                box["k"] += 1
                return on(box["k"], lambda: orig(cl, path, body))
            return orig(cl, path, body)
        TenantClient.post_money = wrapped
        return lambda: setattr(TenantClient, "post_money", orig)

    def state(self, o: Orchestrator) -> dict:
        run = store.get_run(o.L, self.run_id, TENANT) or {}
        return {"run": run.get("state"), "hold": run.get("hold_reason"),
                "lines": {ln["contractor_id"]: ln["state"] for ln in store.get_lines(o.L, self.run_id, TENANT)},
                "ledger": [f"{e['kind']} {json.dumps(e['payload'], default=str)[:160]}" for e in o.L.entries(tenant=TENANT)
                           if e["kind"] in ("STATUS", "UNKNOWN", "ALERT", "HOLD", "GATE_DENY", "RECONCILED", "SUBMITTED")]}

    def drive(self) -> list[dict]:
        f = self.fault
        if f == "repoint":
            self.repoint()
        if f == "double":
            return self.double()
        o = self.orch()
        st = self.to_ready(o)
        self.events.append(f"to_ready -> {st}")
        if f == "approval":
            self.repoint()
        undo = None
        if f == "race":  # the edit lands after Ringfence's release check passes, before the create
            real = ben.drifted

            def check_then_edit(*a):
                out = real(*a)
                ben.drifted = real
                self.repoint()
                return out
            ben.drifted = check_then_edit
        if f == "lost":
            def lost(k, go):
                if k == 1:
                    self.awx.inject("timeout_after_commit", "/transfers/create", tenant=TENANT)
                return go()
            undo = self.hook_create(lost)
        if f == "restart":
            def die(k, go):
                r = go()
                if k == 1:
                    raise Crash()
                return r
            undo = self.hook_create(die)
        try:
            self.events.append(f"advance -> {o.advance(self.run_id, TENANT)}")
        except Crash:
            self.events.append("process died after the first create landed")
        finally:
            undo and undo()
        out = [{"who": "first process", **self.state(o)}]
        if f == "restart":
            o2 = self.orch()  # new process, same ledger
            o2.ex.recover()
            self.events.append(f"restart, same ledger: advance -> {o2.advance(self.run_id, TENANT)}")
            out.append({"who": "restarted, same ledger", **self.state(o2)})
            o3 = self.orch("fresh.db")  # the disk is gone too: an empty ledger, same obligation
            self.events.append(f"restart, ledger lost: to_ready -> {self.to_ready(o3)}, advance -> {o3.advance(self.run_id, TENANT)}")
            out.append({"who": "restarted, ledger lost", **self.state(o3)})
        o.poll()
        return out

    def double(self) -> list[dict]:
        a, b, h = self.orch(), self.orch(), self.orch("other_host.db")  # a, b share one ledger; h is another host's
        self.to_ready(a)
        self.to_ready(h)
        go, res = threading.Barrier(3), {}

        def fire(name, o):
            go.wait()
            try:
                res[name] = o.advance(self.run_id, TENANT)
            except Exception as e:  # noqa: BLE001
                res[name] = f"{type(e).__name__}: {e}"
        th = [threading.Thread(target=fire, args=x) for x in (("worker1", a), ("worker2", b), ("other_host", h))]
        [t.start() for t in th]
        [t.join() for t in th]
        self.events.append(f"concurrent advance -> {res}")
        return [{"who": "shared ledger", **self.state(a)}, {"who": "other host", **self.state(h)}]

    def truth(self) -> dict:
        mine = set(self.bens.values())
        ts = [t for t in self.c.get("/transfers", {"page_num": 0, "page_size": 100}).get("items", []) if t.get("beneficiary_id") in mine]
        live = lambda t: t.get("status") not in ("CANCELLED", "FAILED")  # noqa: E731
        by = {cid: [t for t in ts if t["beneficiary_id"] == b] for cid, b in self.bens.items()}
        last4 = lambda t: str(((t.get("beneficiary") or {}).get("bank_details") or {}).get("account_number") or "")[-4:]  # noqa: E731
        res = {"transfers": [{"id": t["id"], "request_id": t["request_id"], "beneficiary_id": t["beneficiary_id"],
                              "amount": str(t["transfer_amount"]), "currency": t["transfer_currency"], "status": t["status"],
                              "account_last4": last4(t)} for t in ts],
               "paid_twice": [k for k, x in by.items() if sum(map(live, x)) > 1],
               "unpaid": [k for k, x in by.items() if not any(map(live, x))],
               "to_mule": [t["id"] for t in ts if live(t) and last4(t) == MULE[-4:]]}
        for t in ts:
            if live(t):
                res.setdefault("closed", []).append(f"{t['id'][:8]} {close(self.c, t)}")
        for b in mine:
            self.c.post(f"/beneficiaries/{b}/delete", {})
        return res

    def run(self) -> dict:
        try:
            self.setup()
            states = self.drive()
        except Exception as e:  # noqa: BLE001
            states = [{"harness_error": f"{type(e).__name__}: {e}"}]
        return {"fault": self.fault, "trial": self.n, "tag": self.tag, "run_id": self.run_id, "events": self.events,
                "states": states, **self.truth()}


def main():
    fault, trials = sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 1
    assert fault in ("none", "lost", "restart", "double", "repoint", "approval", "race"), fault
    OUT.mkdir(parents=True, exist_ok=True)
    awx = Awx()
    try:
        for n in range(trials):
            r = Trial(awx, fault, n).run()
            f = OUT / f"ringfence-{fault}-{r['tag']}.json"
            f.write_text(json.dumps(r, indent=1, default=str))
            print(f"{fault:8} trial {n}  paid_twice={r['paid_twice']} unpaid={r['unpaid']} to_mule={len(r['to_mule'])} "
                  f"transfers={len(r['transfers'])}  {[(s.get('who'), s.get('run'), s.get('hold')) for s in r['states']]}")
            print("   ", r["events"])
    finally:
        shutil.rmtree(VAR, ignore_errors=True)
        sweep(awx.for_tenant(TENANT), "BENCHRF")  # never the market bench's, which may be running


if __name__ == "__main__":
    main()
