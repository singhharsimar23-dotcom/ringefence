"""Idempotent sandbox setup. Re-runnable: python -m ringfence.setup_demo [--backend fake|live] [--no-drain]

Per employer: make sure the demo global accounts exist, create the contractors' beneficiaries and the fee
beneficiary in THAT tenant's own account, write var/registry.json. Optionally sell each tenant's AUD back to
USD inside its own account, so Harbour's shortfall is exactly its payroll need.
"""
from __future__ import annotations

import argparse
import time

from . import beneficiaries as ben
from . import fx
from .awx import Awx, build_backend
from .config import EMPLOYERS

# tenant -> (country, currency) of the global account the demo needs
NEEDED_GA = {"kestrel": ("US", "USD"), "harbour": ("AU", "AUD")}
DRAIN_TENANTS = ("northwind", "harbour")  # the tenants that must start with AUD 0


def setup(awx: Awx, drain: bool = True) -> dict:
    reg = ben.load_registry()
    for t in EMPLOYERS:
        c = awx.for_tenant(t)
        gas = ben.paged(c, "/global_accounts")
        need = NEEDED_GA.get(t)
        if need and not any(ben.ga_record(g)["currency"] == need[1] for g in gas):
            gas.append(c.post("/global_accounts/create", {
                "request_id": f"rf-ga-{t}-{need[1].lower()}", "country_code": need[0], "nick_name": f"{t} {need[1]}",
                "required_features": [{"currency": need[1], "transfer_method": "LOCAL"}]}))
        reg["tenants"][t] = {**ben.ensure_beneficiaries(c, t), "gas": [ben.ga_record(g) for g in gas]}
        if drain and t in DRAIN_TENANTS:
            sold = fx.drain(c, "AUD", "USD", f"rf-drain-{t}-{int(time.time())}")
            reg["tenants"][t]["drained_aud"] = str(sold)
    ben.save_registry(reg)
    return reg


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["fake", "live"])
    ap.add_argument("--no-drain", action="store_true")
    a = ap.parse_args()
    awx, _ = build_backend(a.backend)
    reg = setup(awx, drain=not a.no_drain)
    for t, r in reg["tenants"].items():
        print(f"{t}: {len(r['beneficiaries'])} contractors, fee beneficiary {r['fee_beneficiary'][:8]}..., "
              f"{len(r['gas'])} global accounts, drained AUD {r.get('drained_aud', '-')}")


if __name__ == "__main__":
    main()
