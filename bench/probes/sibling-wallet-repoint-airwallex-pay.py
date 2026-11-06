"""LIVE probe: in-place repoint of a saved payee from BANK_ACCOUNT to an Airwallex Pay DIGITAL_WALLET
pointing at a sibling employer's own Airwallex account, over the rail Airwallex itself recommends for
account-to-account payouts (Transfers via Airwallex Pay: Flight time Instant, No limit, funds deducted
immediately). Northwind pays, Kestrel (a different employer under the same entity) is credited.

Writes ONLY on Northwind. Reads on Kestrel. One GBP 1.00 move, cancelled/attempted-cancelled after.
Account numbers never printed in full (last 4 only). Run: uv run python bench/probes/<this>.py
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from scripts.awx import BASE, env, token  # noqa: E402

VER = "2025-04-25"  # DIGITAL_WALLET beneficiary type was added in this API version
NW = env("AWX_EMPLOYER_A")  # Northwind - pays
KE = env("AWX_EMPLOYER_B")  # Kestrel - sibling employer, credited
SLUG = f"PRB-dw-{int(time.time())}"
out: list[str] = []


def say(*a):
    line = " ".join(str(x) for x in a)
    print(line)
    out.append(line)


def client(acct: str) -> httpx.Client:
    return httpx.Client(base_url=f"{BASE}/api/v1", timeout=60,
                        headers={"Authorization": f"Bearer {token(acct)}", "x-api-version": VER})


def req(c: httpx.Client, method: str, path: str, body=None):
    r = c.request(method, path, json=body)
    data = r.json() if r.content and "json" in r.headers.get("content-type", "") else r.text
    return r.status_code, data


def main():
    nw, ke = client(NW), client(KE)
    created_bid = None
    mine: list[str] = []  # every beneficiary id we create (DIGITAL_WALLET payees are not returned by GET /beneficiaries)
    try:
        # 1) Kestrel's own Airwallex account number + name (the digital-wallet payee identity)
        code, info = req(ke, "GET", "/account")
        say("Kestrel GET /account:", code)
        code, wi = req(ke, "GET", "/account/wallet_info")
        say("Kestrel GET /account/wallet_info:", code,
            "keys=", list(wi) if isinstance(wi, dict) else wi)
        ke_num = (wi.get("account_number") if isinstance(wi, dict) else None) or ""
        ke_name = (wi.get("account_name") if isinstance(wi, dict) else None) or ""
        say("  Kestrel wallet acct last4=", ke_num[-4:], "name=", repr(ke_name))
        if not ke_num:
            say("NO wallet_info account_number; cannot aim the wallet transfer. Abort rail test.")
            return

        # 3) Northwind: a normal approved-looking BANK_ACCOUNT payee
        payload = {"nickname": SLUG, "transfer_methods": ["LOCAL"], "beneficiary": {
            "type": "BANK_ACCOUNT", "entity_type": "COMPANY", "company_name": "Acme Contractor Ltd",
            "address": {"country_code": "GB", "city": "London", "street_address": "1 Test St", "postcode": "EC1A 1AA"},
            "bank_details": {"bank_country_code": "GB", "account_currency": "GBP", "account_name": "Acme Contractor Ltd",
                             "bank_name": "HSBC", "account_routing_type1": "sort_code",
                             "account_routing_value1": "040004", "account_number": "12345678"}}}
        code, b = req(nw, "POST", "/beneficiaries/create", payload)
        say("Northwind create BANK_ACCOUNT payee:", code, b if code >= 400 else "")
        if code >= 400:
            return
        created_bid = b["id"]
        mine.append(created_bid)
        code, g = req(nw, "GET", f"/beneficiaries/{created_bid}")
        bd = (g.get("beneficiary") or {}).get("bank_details") or {}
        say("  before: id=", created_bid, "type=", (g.get("beneficiary") or {}).get("type"),
            "bank last4=", str(bd.get("account_number") or "")[-4:])

        # 4) Repoint IN PLACE to an Airwallex Pay digital wallet pointing at Kestrel
        upd = {"transfer_methods": ["LOCAL"], "beneficiary": {
            "type": "DIGITAL_WALLET",
            "digital_wallet": {"account_name": ke_name or "Sandbox Business",
                               "id_type": "account_number", "id_value": ke_num, "provider": "AIRWALLEX"}}}
        code, u = req(nw, "POST", f"/beneficiaries/{created_bid}/update", upd)
        say("Northwind update -> DIGITAL_WALLET:", code, u if code >= 400 else "")
        flipped_in_place = False
        if code < 400:
            code, g2 = req(nw, "GET", f"/beneficiaries/{created_bid}")
            ben2 = g2.get("beneficiary") or {}
            say("  after update: id==orig?", g2.get("id") == created_bid, "type=", ben2.get("type"),
                "has bank_details?", "bank_details" in ben2, "has digital_wallet?", "digital_wallet" in ben2)
            flipped_in_place = ben2.get("type") == "DIGITAL_WALLET" and "bank_details" not in ben2
        target_bid = created_bid

        # 5) If the in-place flip is refused, fall back to a fresh DIGITAL_WALLET payee (rail still matters)
        if not flipped_in_place:
            say("In-place flip refuted or partial; creating a fresh DIGITAL_WALLET payee.")
            dwp = {"nickname": SLUG + "-dw", "transfer_methods": ["LOCAL"], "beneficiary": {
                "type": "DIGITAL_WALLET",
                "digital_wallet": {"account_name": ke_name or "Sandbox Business", "id_type": "account_number",
                                   "id_value": ke_num, "provider": "AIRWALLEX"}}}
            code, b2 = req(nw, "POST", "/beneficiaries/create", dwp)
            say("Northwind create DIGITAL_WALLET payee:", code, b2 if code >= 400 else "")
            if code >= 400:
                return
            target_bid = b2["id"]
            mine.append(target_bid)

        # 6) Snapshot GBP both sides
        def gbp(c):
            _, bal = req(c, "GET", "/balances/current")
            return next((r.get("available_amount") for r in bal if r.get("currency") == "GBP"), None) if isinstance(bal, list) else bal
        nw0, ke0 = gbp(nw), gbp(ke)
        say("GBP before: Northwind=", nw0, "Kestrel=", ke0)

        # 7) Pay GBP 1.00 over Airwallex Pay and time it to terminal, then try to cancel
        rid = f"prb-dw-{int(time.time())}"
        tbody = {"request_id": rid, "beneficiary_id": target_bid, "source_currency": "GBP",
                 "transfer_currency": "GBP", "transfer_amount": "1.00", "transfer_method": "LOCAL",
                 "fee_paid_by": "PAYER", "reason": "wages_salary", "reference": SLUG}
        t0 = time.time()
        code, t = req(nw, "POST", "/transfers/create", tbody)
        say("transfer create:", code, "status=", t.get("status") if isinstance(t, dict) else t)
        if code >= 400:
            return
        tid = t["id"]
        terminal = {"PAID", "SETTLED", "FAILED", "CANCELLED"}
        last = t.get("status")
        for _ in range(40):  # ~20s
            code, tg = req(nw, "GET", f"/transfers/{tid}")
            last = tg.get("status") if isinstance(tg, dict) else last
            if last in terminal:
                break
            time.sleep(0.5)
        say("time to", last, "=", round(time.time() - t0, 2), "s")
        ben_snap = (tg.get("beneficiary") or {}) if isinstance(tg, dict) else {}
        say("transfer beneficiary snapshot keys=", list(ben_snap),
            "has bank_details?", "bank_details" in ben_snap)

        rc = nw.post(f"/transfers/{tid}/cancel", content=b"")
        cx = rc.json() if rc.content and "json" in rc.headers.get("content-type", "") else rc.text
        say("cancel attempt:", rc.status_code, cx)
        code, tg2 = req(nw, "GET", f"/transfers/{tid}")
        say("status after cancel attempt:", tg2.get("status") if isinstance(tg2, dict) else tg2)

        nw1, ke1 = gbp(nw), gbp(ke)
        say("GBP after: Northwind=", nw1, "Kestrel=", ke1)
        say("RESULT flipped_in_place=", flipped_in_place, "final_status=",
            tg2.get("status") if isinstance(tg2, dict) else None)
    finally:
        # cleanup: delete every beneficiary we created (POST .../delete; DIGITAL_WALLET payees are not listed)
        for bid in dict.fromkeys(mine):
            dc, _ = req(nw, "POST", f"/beneficiaries/{bid}/delete", {})
            say("deleted beneficiary", bid, dc)
        Path(__file__).with_suffix(".out.txt").write_text("\n".join(out), encoding="utf-8")


if __name__ == "__main__":
    main()
