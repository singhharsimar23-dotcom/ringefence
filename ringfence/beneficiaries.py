"""Beneficiary registry: payloads per corridor, per-tenant ids (var/registry.json), global-account records.

Each tenant has its OWN beneficiaries (ids are never shared). A contractor's beneficiary id is resolved from
this tenant's registry, never taken from the model or from an email.
"""
from __future__ import annotations

import hashlib
import json
import os
from typing import Any

from . import seed
from .awx import AwxError, TenantClient
from .config import var_dir

# A playground world shares one Airwallex account with other worlds: its nicknames carry the world id so a
# beneficiary made for someone else's "ada" is never reused (it could hold a different bank).
NICK_PREFIX = "rf:" + (os.environ["RF_WORLD"][:6] + ":" if os.environ.get("RF_WORLD") else "")


def _bank_details(bank: dict, ccy: str, account_name: str) -> dict:
    d = {"bank_country_code": bank["country"], "account_currency": ccy, "account_name": account_name,
         "bank_name": bank["bank_name"]}
    if "iban" in bank:
        d.update(iban=bank["iban"], swift_code=bank["swift_code"])
    else:
        d.update(account_routing_type1=bank["routing_type"], account_routing_value1=bank["routing_value"],
                 account_number=bank["account_number"])
    if "category" in bank:
        d["bank_account_category"] = bank["category"]  # US: exactly "Checking" / "Savings" (code 016 otherwise)
    return d


def contractor_payload(c: dict) -> dict:
    first, _, last = c["name"].partition(" ")
    return {"nickname": NICK_PREFIX + c["id"], "transfer_methods": [c["method"]], "beneficiary": {
        "entity_type": "PERSONAL", "first_name": first, "last_name": last, "address": c["address"],
        "bank_details": _bank_details(c["bank"], c["currency"], c["name"])}}


def fee_payload() -> dict:
    f = seed.load()["fee_beneficiary"]
    return {"nickname": NICK_PREFIX + "fee", "transfer_methods": ["LOCAL"], "beneficiary": {
        "entity_type": "COMPANY", "company_name": f["company_name"], "address": f["address"],
        "bank_details": _bank_details(f["bank"], f["bank"]["currency"], f["company_name"])}}


def bank_key(bank_details: dict) -> str:
    """What identifies the destination account: the IBAN, else the account number."""
    return str(bank_details.get("iban") or bank_details.get("account_number") or "")


PIN_KEYS = ("bank_country_code", "account_currency", "iban", "swift_code", "account_routing_type1", "account_routing_value1",
            "account_routing_type2", "account_routing_value2", "account_number")  # every field that can pick the bank


def fingerprint(bank_details: dict) -> str:
    """The destination itself, not the id that points at it: Airwallex lets anyone with beneficiary:write repoint an id
    in place (POST /beneficiaries/{id}/update keeps the id; verified live 6 Nov), so approving an id approves nothing."""
    s = json.dumps([str(bank_details.get(k) or "").replace(" ", "").upper() for k in PIN_KEYS])
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def stored(payload: dict) -> dict:
    """The bank details as Airwallex keeps them for this create payload, so a pin matches the live record exactly."""
    bd = dict(payload["beneficiary"]["bank_details"])
    if bd.get("iban") and payload.get("transfer_methods") == ["LOCAL"]:
        bd.pop("swift_code", None)  # Airwallex drops it for a LOCAL IBAN payee, on the beneficiary and the transfer (DE, live 6 Nov)
    return bd


def paged(c: TenantClient, path: str) -> list[dict]:
    out, page = [], 0
    while True:
        r = c.get(path, {"page_num": page, "page_size": 100})
        out += r["items"]
        if not r.get("has_more"):
            return out
        page += 1


def ga_record(g: dict) -> dict:
    feat = next((f for f in g.get("supported_features", [])
                 if f.get("type") == "DEPOSIT" and f.get("transfer_method") == "LOCAL" and f.get("routing_codes")), {})
    rc = (feat.get("routing_codes") or [{}])[0]
    return {"id": g["id"], "country": g.get("country_code"), "currency": g["required_features"][0]["currency"],
            "account_number": g.get("account_number"), "iban": g.get("iban"),
            "routing_type": rc.get("type"), "routing_value": rc.get("value")}


def ensure_beneficiaries(c: TenantClient, tenant: str) -> dict[str, Any]:
    """Idempotent: match this tenant's existing beneficiaries by nickname, create the missing ones."""
    have = {b.get("nickname"): b["id"] for b in paged(c, "/beneficiaries") if b.get("nickname")}

    def get_or_create(payload: dict) -> str:
        nick = payload["nickname"]
        if nick not in have:
            try:
                have[nick] = c.post("/beneficiaries/create", payload)["id"]
            except AwxError as e:
                raise RuntimeError(f"{tenant}/{nick}: {e}") from None
        return have[nick]

    want = {s["id"]: contractor_payload(s) for s in seed.contractor_seeds(tenant)}
    out = {"beneficiaries": {cid: get_or_create(p) for cid, p in want.items()}, "fee_beneficiary": get_or_create(fee_payload())}
    # pinned from what we MEANT to create, not from what is there now: an id already repointed is caught at release
    out["pins"] = {out["beneficiaries"][cid]: fingerprint(stored(p)) for cid, p in want.items()}
    out["pins"][out["fee_beneficiary"]] = fingerprint(stored(fee_payload()))
    return out


def drifted(c: TenantClient, tenant: str, lines: list[dict]) -> list[dict]:
    """Lines whose beneficiary, read live with this tenant's token, no longer holds the account a human approved.
    No pin counts as drifted (fail closed). An unreadable beneficiary is left to the gate, which denies it."""
    pins, out = load_registry().get("tenants", {}).get(tenant, {}).get("pins", {}), []
    for ln in lines:
        bid = ln["beneficiary_id"]
        try:
            bd = c.get(f"/beneficiaries/{bid}")["beneficiary"]["bank_details"]
        except AwxError:
            continue
        if fingerprint(bd) != pins.get(bid):
            out.append({"contractor_id": ln["contractor_id"], "beneficiary_id": bid, "approved": pins.get(bid),
                        "live": fingerprint(bd), "live_last4": bank_key(bd)[-4:]})
    return out


# -- var/registry.json -------------------------------------------------------------------------
def _path():
    return var_dir() / "registry.json"


def load_registry() -> dict:
    p = _path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"tenants": {}}


def save_registry(reg: dict) -> None:
    _path().write_text(json.dumps(reg, indent=1, sort_keys=True), encoding="utf-8")


def resolve(reg: dict, tenant: str, contractor_id: str) -> str | None:
    """THIS tenant's beneficiary id for the contractor (None if unknown)."""
    return reg.get("tenants", {}).get(tenant, {}).get("beneficiaries", {}).get(contractor_id)


def all_ga_keys(reg: dict) -> set[str]:
    """Account numbers and IBANs of every employer's own global accounts (gate check 7)."""
    out: set[str] = set()
    for t in reg.get("tenants", {}).values():
        for g in t.get("gas", []):
            out |= {k for k in (g.get("account_number"), g.get("iban")) if k}
    return out


# -- bank-detail changes: quarantine until a DIFFERENT approver confirms by phone (BUILD_SPEC 4.9) ----------
BANK_KEYS = {"country", "bank_name", "routing_type", "routing_value", "account_number", "iban", "swift_code", "category"}


def _check_bank(bank: Any) -> dict:
    ok = isinstance(bank, dict) and bank and set(bank) <= BANK_KEYS and all(isinstance(v, str) and v for v in bank.values())
    has_acct = ok and ("iban" in bank and "swift_code" in bank or {"routing_type", "routing_value", "account_number"} <= set(bank))
    if not (ok and has_acct and "country" in bank and "bank_name" in bank):
        raise ValueError("bank details must be typed strings: country, bank_name and either iban+swift_code or routing+account")
    return bank


VERIFY_KEYS = ("account_name", "account_number", "account_routing_type1", "account_routing_value1", "bank_country_code",
               "iban", "swift_code")


def name_match(c: TenantClient, payload: dict) -> str:
    """Airwallex confirmation of payee: is the account at the bank in the contractor's name? FULL_MATCH, PARTIAL_MATCH
    or NOT_MATCHED; otherwise the verify code (INVALID, CANNOT_VERIFY) or UNAVAILABLE. Only NOT_MATCHED blocks.
    shortcut: INVALID does not block because the sandbox calls every non-test account INVALID; block it in production."""
    b = payload["beneficiary"]
    try:
        r = c.post("/beneficiaries/verify_account", {"entity_type": b["entity_type"], "transfer_method": payload["transfer_methods"][0],
                                                     "bank_details": {k: b["bank_details"][k] for k in VERIFY_KEYS if k in b["bank_details"]}})
    except AwxError:
        return "UNAVAILABLE"
    return str((r.get("details") or {}).get("account_name_match_result") or r.get("code") or "UNAVAILABLE")


def propose_bank_change(awx, L, tenant: str, contractor_id: str, bank: dict, doc_id: str, requested_by: str) -> dict:
    """Validate with this tenant's token, then QUARANTINE. Existing details stay in force; nothing is created."""
    bank = _check_bank(bank)
    seed_c = next((c for c in seed.contractor_seeds(tenant) if c["id"] == contractor_id), None)
    if seed_c is None:
        raise KeyError(f"{contractor_id} is not a contractor of {tenant}")
    for r in L.query("SELECT id, data FROM quarantine WHERE tenant=? AND contractor_id=? AND status='ACTIVE'",
                     (tenant, contractor_id)):
        if json.loads(r["data"]).get("doc_id") == doc_id:
            return {"id": r["id"], **json.loads(r["data"])}  # same document again: idempotent
    payload = contractor_payload({**seed_c, "bank": bank})
    try:
        awx.for_tenant(tenant).post("/beneficiaries/validate", {"beneficiary": payload["beneficiary"],
                                                                 "transfer_methods": payload["transfer_methods"]})
        valid, why = True, ""
    except AwxError as e:
        valid, why = False, e.message
    rec = {"doc_id": doc_id, "requested_by": requested_by, "bank": bank, "valid": valid, "validation": why,
           "name_match": name_match(awx.for_tenant(tenant), payload)}
    with L.tx() as tx:
        qid = tx.execute("INSERT INTO quarantine(tenant, contractor_id, status, data) VALUES(?,?,?,?)",
                         (tenant, contractor_id, "ACTIVE", json.dumps(rec))).lastrowid
        tx.append("BENEFICIARY_QUARANTINED", {"quarantine_id": qid, "contractor_id": contractor_id, "doc_id": doc_id,
                                              "requested_by": requested_by, "valid": valid, "name_match": rec["name_match"],
                                              "last4": bank.get("account_number", bank.get("iban", ""))[-4:]},
                  None, tenant)
    return {"id": qid, **rec}


def confirm_callback(awx, L, tenant: str, qid: int, approver_id: str, role: str, callback_ref: str) -> str:
    """The phone call happened: a different approver types its reference. Only now is the new beneficiary created."""
    from .store import latest_mandate  # local import: store imports nothing from here
    rows = L.query("SELECT * FROM quarantine WHERE id=? AND tenant=? AND status='ACTIVE'", (qid, tenant))
    if not rows:
        raise LookupError(f"no open quarantine item {qid} for {tenant}")
    rec = json.loads(rows[0]["data"])
    cid, sm = rows[0]["contractor_id"], latest_mandate(L, tenant)
    if sm is None or role != sm.mandate.approver_role:
        raise PermissionError(f"{approver_id} ({role}) may not confirm bank changes for {tenant}")
    if approver_id == rec["requested_by"]:
        raise PermissionError("the person who proposed the change cannot confirm it")
    if len(callback_ref.strip()) < 4 or not rec["valid"]:
        raise ValueError("a phone-callback reference (4+ characters) is required, and the details must have validated")
    if rec.get("name_match") == "NOT_MATCHED":  # a phone call can be faked; the bank's own record of the holder cannot
        raise ValueError("the bank says this account is not in the contractor's name, so it cannot be confirmed")
    seed_c = next(c for c in seed.contractor_seeds(tenant) if c["id"] == cid)
    payload = contractor_payload({**seed_c, "bank": rec["bank"]})
    payload["nickname"] = f"{NICK_PREFIX}{cid}:q{qid}"
    new_id = awx.for_tenant(tenant).post("/beneficiaries/create", payload)["id"]
    reg = load_registry()
    reg["tenants"][tenant]["beneficiaries"][cid] = new_id
    reg["tenants"][tenant].setdefault("pins", {})[new_id] = fingerprint(stored(payload))
    save_registry(reg)
    with L.tx() as tx:
        tx.execute("UPDATE quarantine SET status='CONFIRMED', data=? WHERE id=?",
                   (json.dumps({**rec, "confirmed_by": approver_id, "callback_ref": callback_ref, "beneficiary_id": new_id}), qid))
        tx.append("CALLBACK_CONFIRMED", {"quarantine_id": qid, "contractor_id": cid, "confirmed_by": approver_id,
                                         "callback_ref": callback_ref, "beneficiary_id": new_id}, None, tenant)
    return new_id
