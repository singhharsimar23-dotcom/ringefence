"""Alta settlement world setup: turn an employer's contractors into wallet payees. Offline, no CLI, no keys.

The registry is the one the executor already reads (beneficiaries, pins, payees, gas). A wallet payee is a beneficiary whose
bank_details.account_number is a 0x address; its pin is the same fingerprint the bank payees use, so a repointed wallet is
drift exactly like a repointed bank account."""
from __future__ import annotations

from . import beneficiaries as ben


def wallet_payee(name: str, address: str) -> dict:
    return {"entity_type": "COMPANY", "company_name": name,
            "bank_details": {"account_number": address, "account_currency": "USD", "bank_country_code": "ZZ"}}


def overlay(tenant: str, wallets: dict[str, str], principal: str, names: dict[str, str] | None = None) -> dict:
    """Point `tenant`'s contractors at on-chain wallets and register the employer's own Alta account (so paying it is refused)."""
    reg = ben.load_registry()
    t = reg["tenants"][tenant]
    for cid, addr in wallets.items():
        bid = f"alta-{tenant}-{cid}"
        p = wallet_payee((names or {}).get(cid, cid), addr)
        t["beneficiaries"][cid], t["payees"][bid] = bid, p
        t["pins"][bid] = ben.fingerprint(p["bank_details"])
    if principal not in {g.get("account_number") for g in t["gas"]}:
        t["gas"].append({"id": f"alta-{tenant}", "country": "ZZ", "currency": "USD", "account_number": principal,
                         "iban": None, "routing_type": None, "routing_value": None})
    ben.save_registry(reg)
    return reg
