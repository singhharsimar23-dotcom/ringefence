"""Read-only probe for the mcp-multi-account lens. GETs only; prints no tokens.
Checks, per employer token (x-login-as, as the official MCP's AIRWALLEX_SANDBOX_ACCOUNT_ID does):
  1. /account/wallet_info: does each sibling employer have an Airwallex Pay account number (instant, no-limit rail)?
  2. /balances/current: which currencies is each employer genuinely short in (available == 0)?
  3. /beneficiaries: payee names present in BOTH Northwind and Kestrel (the 'contractor in both' condition).
  4. one /transfers item: does a transfer object say which account paid it?
  5. token claim NAMES (+ api version claim if any), never the token.
Usage: uv run python bench/probes/probe_mcp_multi_account_readonly.py
"""
import base64
import json
import os
import sys
from decimal import Decimal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "scripts"))
import awx  # noqa: E402  (scripts/awx.py: env() registry fallback, token(), call())

ACCTS = {k: awx.env(v) for k, v in (("northwind", "AWX_EMPLOYER_A"), ("kestrel", "AWX_EMPLOYER_B"),
                                     ("harbour", "AWX_EMPLOYER_C"), ("platform", "AWX_PLATFORM_ACCOUNT"))}


def names(acct):
    code, r = awx.call("GET", "/beneficiaries?page_num=0&page_size=200", login_as=acct)
    out = {}
    for b in (r.get("items", []) if code == 200 else []):
        ben = b.get("beneficiary", {})
        n = ben.get("company_name") or " ".join(x for x in (ben.get("first_name"), ben.get("last_name")) if x) or b.get("nickname")
        out.setdefault(n, []).append({"id": b["id"][:8], "type": ben.get("type"),
                                      "last4": str((ben.get("bank_details") or {}).get("account_number") or (ben.get("bank_details") or {}).get("iban") or "")[-4:]})
    return code, out


for name, acct in ACCTS.items():
    print(f"== {name} {acct}")
    code, wi = awx.call("GET", "/account/wallet_info", login_as=acct)
    print("  wallet_info", code, {k: (v if k == "account_name" else str(v)[-4:]) for k, v in wi.items()} if code == 200 else wi)
    code, bal = awx.call("GET", "/balances/current", login_as=acct)
    if code == 200:
        zero = sorted(b["currency"] for b in bal if Decimal(str(b["available_amount"])) == 0)
        print("  balance currencies:", len(bal), "zero-available:", zero[:25])
    tok = awx.token(acct)
    claims = json.loads(base64.urlsafe_b64decode(tok.split(".")[1] + "=="))
    print("  token claim names:", sorted(claims), {k: claims[k] for k in claims if "version" in k.lower()})
    del tok

cn, n_names = names(ACCTS["northwind"])
ck, k_names = names(ACCTS["kestrel"])
both = sorted(set(n_names) & set(k_names), key=str)
print("beneficiaries northwind/kestrel:", cn, ck, len(n_names), len(k_names), "names in both:", len(both))
for n in both[:12]:
    print("  ", n, "N:", n_names[n], "K:", k_names[n])

code, ts = awx.call("GET", "/transfers?page_num=0&page_size=10", login_as=ACCTS["northwind"])
if code == 200 and ts.get("items"):
    t = ts["items"][0]
    print("transfer keys:", sorted(t))
    print("  account-identifying keys:", [k for k in t if "account" in k.lower() or k in ("payer", "source")])
    print("  payer:", json.dumps(t.get("payer"))[:300])
