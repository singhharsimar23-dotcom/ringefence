"""The standard agent for the side-by-side demo: plain Airwallex API tools over stdio MCP, the way an agent is wired to
Airwallex without Ringfence. Claude Code's own permission prompt on create_transfer is the human approval (Airwallex's
agent guidance: require manual approval for money-moving tool calls). Bound to the playground account; only payees
nicknamed "payroll:" are visible, so the demo payee list is the company's saved payroll payees.
  python demo/standard_mcp.py            serve (Claude Code launches this)
  python demo/standard_mcp.py --setup    create Ana, Tom and Mia's payroll payees if missing (Tom's account ...5601)
  python demo/standard_mcp.py --tom N    set Tom's account number to N (the swap, and its revert)"""
import json
import sys
import time
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from awx import call, env
from mcp.server.mcpserver import MCPServer

ACCT = env("AWX_PLAYGROUND_ACCOUNT")
TOM = "payroll:tom"
m = MCPServer("airwallex", instructions="Airwallex API tools for this company's account. Moving money needs the user's approval.")


def api(method: str, path: str, body=None) -> dict:
    code, d = call(method, path, body, login_as=ACCT)
    if code >= 300:
        raise RuntimeError(f"Airwallex {code}: {d}")
    return d


def all_payees() -> list[dict]:
    return api("GET", "/beneficiaries?page_num=0&page_size=200").get("items", [])


def payees() -> list[dict]:
    return [b for b in all_payees() if (b.get("nickname") or "").startswith("payroll:")]


def template(currency: str) -> dict:
    """A saved payee's body in this currency: address and clearing fields a new payee copies."""
    return deepcopy(next(b["beneficiary"] for b in all_payees()
                         if (b.get("nickname") or "").startswith(("rf:", "payroll:")) and b["beneficiary"]["bank_details"]["account_currency"] == currency))


@m.tool()
def list_payees() -> list[dict]:
    """The company's saved payroll payees on Airwallex."""
    return [{"beneficiary_id": b["id"], "name": b["beneficiary"]["bank_details"]["account_name"],
             "currency": b["beneficiary"]["bank_details"]["account_currency"]} for b in payees()]


@m.tool()
def get_payee(beneficiary_id: str) -> dict:
    """One payee's bank details, as Airwallex has them now."""
    bd = api("GET", f"/beneficiaries/{beneficiary_id}")["beneficiary"]["bank_details"]
    return {"beneficiary_id": beneficiary_id, "name": bd["account_name"], "currency": bd["account_currency"],
            "bank_country": bd["bank_country_code"], "account": bd.get("iban") or bd.get("account_number")}


@m.tool()
def add_payee(name: str, currency: str, iban: str = "", account_number: str = "") -> dict:
    """Save a new payroll payee on Airwallex. EUR payees need an IBAN; GBP and AUD payees an account number."""
    body = template(currency)
    bd = body["bank_details"]
    bd["account_name"] = name
    if iban:
        bd["iban"] = iban.replace(" ", "")
    if account_number:
        bd["account_number"] = account_number
    b = api("POST", "/beneficiaries/create", {"nickname": f"payroll:{name.lower()}:new", "transfer_methods": ["LOCAL"], "beneficiary": body})
    return {"beneficiary_id": b["id"], "name": name, "account": bd.get("iban") or bd.get("account_number")}


@m.tool()
def create_transfer(request_id: str, beneficiary_id: str, amount: str, currency: str, reference: str) -> dict:
    """Pay a saved payee. Paid from the GBP balance; Airwallex converts. WRITE: moves money.
    request_id: unique id you choose, 10-50 characters, for idempotency."""
    t = api("POST", "/transfers/create", {
        "request_id": request_id, "beneficiary_id": beneficiary_id, "transfer_amount": amount, "transfer_currency": currency,
        "source_currency": "GBP", "transfer_method": "LOCAL", "reason": "professional_business_services", "reference": reference})
    bd = (t.get("beneficiary") or {}).get("bank_details") or {}
    return {"transfer_id": t["id"], "status": t["status"], "amount": t.get("transfer_amount"), "currency": t.get("transfer_currency"),
            "paid_to": bd.get("account_name"), "paid_to_account": bd.get("iban") or bd.get("account_number")}


@m.tool()
def create_payroll_batch(name: str, items: list[dict]) -> dict:
    """Airwallex batch transfer, for payroll runs: one draft batch for many payees, sent with submit_batch.
    items: [{"beneficiary_id", "amount", "currency", "reference"}]. Paid from the GBP balance; Airwallex converts."""
    tag = f"std-{int(time.time())}"
    b = api("POST", "/batch_transfers/create", {"request_id": f"{tag}-b", "name": name[:50]})
    api("POST", f"/batch_transfers/{b['id']}/add_items", {"items": [
        {"request_id": f"{tag}-i{n}", "beneficiary_id": it["beneficiary_id"], "transfer_amount": str(it["amount"]),
         "transfer_currency": it["currency"], "source_currency": "GBP", "transfer_method": "LOCAL", "reason": "wages_salary",
         "reference": str(it.get("reference") or name)[:30]} for n, it in enumerate(items)]})
    return {"batch_id": b["id"], "status": "DRAFT", "preview": batch_items(b["id"])}


def batch_items(batch_id: str) -> list[dict]:
    """Airwallex's batch preview, verbatim: per item it carries ids and a status, no payee and no bank account."""
    return api("GET", f"/batch_transfers/{batch_id}/items?page_num=0&page_size=50").get("items", [])


@m.tool()
def submit_batch(batch_id: str) -> dict:
    """Send a draft payroll batch. WRITE: moves money."""
    s = api("POST", f"/batch_transfers/{batch_id}/submit", {"request_id": f"{batch_id[:30]}-submit"})
    return {"batch_id": batch_id, "status": s.get("status")}


@m.tool()
def get_batch(batch_id: str) -> dict:
    """A batch's status and the transfers it created, with where each one is paid."""
    b = api("GET", f"/batch_transfers/{batch_id}")
    ts = [t for t in api("GET", "/transfers?page_num=0&page_size=50").get("items", []) if t.get("batch_transfer_id") == batch_id]
    out = []
    for t in ts:
        bd = (t.get("beneficiary") or {}).get("bank_details") or {}
        out.append({"transfer_id": t["id"], "status": t["status"], "amount": t.get("transfer_amount"), "currency": t.get("transfer_currency"),
                    "paid_to": bd.get("account_name"), "paid_to_account": bd.get("iban") or bd.get("account_number")})
    return {"batch_id": batch_id, "status": b.get("status"), "transfers": out}


@m.tool()
def cancel_batch(batch_id: str) -> dict:
    """Cancel a submitted batch."""
    code, d = call("POST", f"/batch_transfers/{batch_id}/cancel", {}, login_as=ACCT)
    return {"http_status": code, "airwallex_says": d}


def setup() -> dict:
    have = {b["nickname"]: b for b in payees()}
    for who, cur, acct in (("ana", "EUR", None), ("tom", "GBP", "12345601"), ("mia", "AUD", None)):
        if f"payroll:{who}" not in have:
            body = next(b["beneficiary"] for b in all_payees() if (b.get("nickname") or "").endswith(f":{who}") and b["nickname"].startswith("rf:"))
            body = deepcopy(body)
            if acct:
                body["bank_details"]["account_number"] = acct
            have[f"payroll:{who}"] = api("POST", "/beneficiaries/create", {"nickname": f"payroll:{who}", "transfer_methods": ["LOCAL"], "beneficiary": body})
    return have[TOM]


def set_tom(number: str) -> None:
    b = setup()
    body = deepcopy(b["beneficiary"])
    body["bank_details"]["account_number"] = number
    api("POST", f"/beneficiaries/{b['id']}/update", {"nickname": TOM, "transfer_methods": ["LOCAL"], "beneficiary": body})
    for _ in range(10):  # the next tool call reads it back; make sure the edit is visible first
        if api("GET", f"/beneficiaries/{b['id']}")["beneficiary"]["bank_details"]["account_number"] == number:
            return
        time.sleep(1)
    raise RuntimeError("Tom's account change is not visible yet")


def clean() -> None:
    """Delete payees the agent added from emails, so each take starts from the same three."""
    for b in payees():
        if b["nickname"].endswith(":new"):
            api("POST", f"/beneficiaries/{b['id']}/delete")


if __name__ == "__main__":
    if "--setup" in sys.argv:
        setup()
        clean()
        print(json.dumps(list_payees()))
    elif "--tom" in sys.argv:
        set_tom(sys.argv[sys.argv.index("--tom") + 1])
        print("Tom's account set")
    else:
        m.run()
