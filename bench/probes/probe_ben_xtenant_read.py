"""READ-ONLY: is a beneficiary id from one employer usable/readable under another employer's token? How do list filters match?
Prints status codes, nicknames and last-4 only. No writes."""
import sys, json
sys.path.insert(0, "scripts")
import awx

A, B = awx.env("AWX_EMPLOYER_A"), awx.env("AWX_EMPLOYER_B")
reg = json.load(open("var/registry.json"))["tenants"]
ada = reg["northwind"]["beneficiaries"]["ada"]
noah = reg["kestrel"]["beneficiaries"]["noah"]

def show(label, code, d):
    if isinstance(d, dict) and "items" in d:
        print(label, code, "n=", len(d["items"]), "total=", d.get("total_count"),
              [(i.get("nickname"), (i.get("beneficiary", {}).get("bank_details", {}).get("account_number") or i.get("beneficiary", {}).get("bank_details", {}).get("iban") or "")[-4:]) for i in d["items"][:8]])
    elif isinstance(d, dict) and "beneficiary" in d:
        bd = d["beneficiary"]["bank_details"]
        print(label, code, d.get("nickname"), (bd.get("account_number") or bd.get("iban") or "")[-4:], bd.get("account_name"))
    else:
        print(label, code, str(d)[:200])

show("B token GET A/ada:", *awx.call("GET", f"/beneficiaries/{ada}", login_as=B))
show("A token GET A/ada:", *awx.call("GET", f"/beneficiaries/{ada}", login_as=A))
show("A token GET B/noah:", *awx.call("GET", f"/beneficiaries/{noah}", login_as=A))
show("B token GET bogus uuid:", *awx.call("GET", "/beneficiaries/00000000-0000-4000-8000-000000000000", login_as=B))
for q in ("nickname=rf:ada", "nickname=ada", "nickname=rf", "name=Ada", "name=ada"):
    show(f"A list ?{q}:", *awx.call("GET", f"/beneficiaries?{q}&page_num=0&page_size=20", login_as=A))
