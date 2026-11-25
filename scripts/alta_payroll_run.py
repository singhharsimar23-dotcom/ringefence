"""One payroll, end to end, on the Alta testnet: approve, sign on the device, preflight, pay, verify, certify.

  python scripts/alta_payroll_run.py --go

What is real: the human approval record, the device (separate key file, never given to the server), the credentials, the
pulls and the chain payments. What is simulated, and labelled so: the Airwallex side (the fee charge) runs on the offline
fake. Spend, printed first: 0.11 + 0.10 USDZ of payments, two binds of gas. Writes docs/alta/payroll-<date>/ with the approved
batch, the credential files (never the pull keys) and the signed certificate, so anyone can run scripts/alta_audit.py on it."""
import argparse
import json
import os
import shutil
import sys
import tempfile
import time
from datetime import date, timedelta
from decimal import Decimal as D
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "scripts"), str(ROOT / "tests")]
import awx as awx_env

from ringfence import store

for n in ("METAL_RPC_URL", "METAL_RPC_SECRET"):
    os.environ.setdefault(n, awx_env.env(n) or "")
OWNER = ROOT / "var" / "metal" / "harbour_device" / "owner.json"
STATE = ROOT / "var" / "metal" / "harbour" / "state.json"
HOURS = {"noah": D("0.02"), "zoe": D("0.016")}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--go", action="store_true")
    if not ap.parse_args().go:
        print(__doc__)
        return 0
    os.environ["RF_VAR"] = tempfile.mkdtemp(prefix="rf-alta-payroll-")
    from helpers import RUN, new_run

    from ringfence import alta_release, alta_setup, alta_verify, fees, metal
    from ringfence.alta import AltaAwx, Chain
    from ringfence.alta_device import Device
    from ringfence.awx import Awx
    from ringfence.config import tenants
    from ringfence.executor import Executor
    from ringfence.fake_awx import FakeAirwallex
    from ringfence.ledger import Ledger

    st = json.loads(STATE.read_text(encoding="utf-8"))
    attacker = json.loads((ROOT / "var" / "alta" / "attacks" / "attacker.addr").read_text())["account"]
    wallets = {"noah": st["settlement"], "zoe": attacker}
    work = ROOT / "var" / "alta" / "payroll" / time.strftime("%Y%m%d-%H%M%S")
    creds = work / "server_creds"
    fake = FakeAirwallex({k: t.account_id for k, t in tenants(fake=True).items()})
    inner = Awx(transport=fake.transport, tenant_map=tenants(fake=True), sleep=lambda s: None)
    L = Ledger()
    new_run(inner, L, "kestrel", HOURS, approve=True)
    alta_setup.overlay("kestrel", wallets, st["principal"])
    with L.tx() as tx:
        for cid in HOURS:
            ln = store.get_line(tx, RUN, "kestrel", cid)
            store.set_line(tx, RUN, "kestrel", cid, ln["state"], beneficiary_id=f"alta-kestrel-{cid}")
    _reapprove(L, RUN)
    chain = Chain(metal.run_cli, creds)
    world = AltaAwx(inner, chain, L)
    batch = alta_release.export(L, RUN, "kestrel")
    print("approved batch", batch["batch_hash"][:16], [(x["contractor_id"], x["amount"], x["usdz"]) for x in batch["lines"]])

    dev = Device(metal.run_cli, OWNER, work / "device", wallets, st["principal"])
    for t in dev.sign(batch, creds):
        print("bound", t["contractor_id"], t["payee"][:10], t["usdz"], "USDZ")
    print("preflight problems:", alta_release.problems(L, chain, RUN, "kestrel"))

    ex = Executor(world, L, sleep=lambda s: None, on_done=lambda r, t: fees.charge(world, L, r, t))
    orch = type("O", (), {"L": L, "advance": lambda self, r, t: ex.release(r, t)})()
    for _ in range(2):  # the first advance releases, the second settles
        print(alta_release.release(orch, chain, RUN, "kestrel")["released"])
    for e in list(L.entries(run_id=RUN))[-14:]:
        print("  ledger", e["kind"], json.dumps(e["payload"], default=str)[:230])
    rep = alta_verify.report(L, chain, RUN, "kestrel")
    cert = alta_verify.certificate(L, rep)
    for x in rep["lines"]:
        print(x["contractor_id"], "PASS" if x["ok"] else "FAIL", x["state"], x["spent_usdz"], "USDZ")

    if cert["body"]["result"] != "PASS":  # never record an unsettled payroll as the proof
        print("not settled, nothing written:", cert["body"]["result"], alta_release.problems(L, chain, RUN, "kestrel"))
        return 1
    out = ROOT / "docs" / "alta" / f"payroll-{date.today().isoformat()}"
    shutil.rmtree(out, ignore_errors=True)
    (out / "creds").mkdir(parents=True)
    for x in batch["lines"]:
        d = out / "creds" / x["request_id"]
        d.mkdir()
        shutil.copy(creds / x["request_id"] / "m.json", d / "m.json")  # the credential, never m.key.json (the pull key)
    (out / "export.json").write_text(json.dumps(batch, indent=1), encoding="utf-8")
    (out / "book.json").write_text(json.dumps(wallets, indent=1), encoding="utf-8")
    (out / "report.json").write_text(json.dumps(rep, indent=1, default=str), encoding="utf-8")
    alta_verify.write(cert, out)
    print("wrote", out, "result", cert["body"]["result"])
    return 0 if rep["ok"] else 1


def _reapprove(L, run_id):
    from ringfence.config import clock
    from ringfence.executor import current_batch_hash
    from ringfence.mandate import Approval, sign_approval
    run = store.get_run(L, run_id, "kestrel")
    now = clock.utc_now()
    a = Approval(run_id, "kestrel", run["round"], current_batch_hash(L, run_id, "kestrel", run["round"]), "approver",
                 store.latest_mandate(L, "kestrel").mandate.approver_role, now, now + timedelta(hours=2))
    with L.tx() as tx:
        store.save_approval(tx, sign_approval(a))
        tx.append("APPROVED", {"approver": "approver", "round": run["round"]}, run_id, "kestrel")


if __name__ == "__main__":
    raise SystemExit(main())
