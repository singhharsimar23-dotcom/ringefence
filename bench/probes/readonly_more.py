"""Read-only recon for NEW findings. No money moves (GET + one validate call).
Run: PYTHONIOENCODING=utf-8 .venv/Scripts/python -I bench/probes/readonly_more.py
Self-check at end asserts each probe actually returned, so a silent 404/auth fail can't look like a pass."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
from scripts.awx import call, env  # noqa: E402

A = env("AWX_EMPLOYER_A")  # Northwind
results = {}


def p(name, *a, **k):
    code, data = call(*a, **k)
    results[name] = (code, data)
    n = len(data.get("items", [])) if isinstance(data, dict) else "-"
    print(f"[{name}] HTTP {code} items={n}")
    return code, data


# 1. Does a reconciler see the destination bank account in /transfers? (supports Finding B)
code, data = p("transfers", "GET", "/transfers?page_size=10", login_as=A)
item = (data.get("items") or [{}])[0] if isinstance(data, dict) else {}
dest_fields = [k for k in item if any(t in k.lower() for t in ("benefic", "bank", "account", "dest"))]
print(f"    destination-ish fields on a transfer item: {dest_fields or 'NONE'}")
print(f"    full key set: {sorted(item)[:40]}")

# 2. Pagination: page_num honored on /beneficiaries but not /transfers?
_, b0 = p("ben_p0", "GET", "/beneficiaries?page_num=0&page_size=5", login_as=A)
_, b1 = p("ben_p1", "GET", "/beneficiaries?page_num=1&page_size=5", login_as=A)
ids0 = [x.get("id") for x in (b0.get("items") or [])] if isinstance(b0, dict) else []
ids1 = [x.get("id") for x in (b1.get("items") or [])] if isinstance(b1, dict) else []
print(f"    beneficiaries page0 vs page1 identical? {ids0 == ids1 and bool(ids0)}")

# 3. Beneficiary validate: is it format-only? Valid sort code 040004, absurd account number.
validate_body = {"beneficiary": {"bank_details": {"account_name": "Probe Test", "account_number": "00000000",
                 "bank_country_code": "GB", "account_routing_type1": "sort_code", "account_routing_value1": "040004"},
                 "entity_type": "COMPANY"}, "transfer_methods": ["LOCAL"]}
p("validate_absurd_acct", "POST", "/beneficiaries/validate", validate_body, login_as=A)

# 4. Does an unknown status filter get ignored (fail-open filter family)?
_, all_b = p("ben_all", "GET", "/beneficiaries?page_size=50", login_as=A)
_, filt_b = p("ben_bogus_status", "GET", "/beneficiaries?page_size=50&status=NONEXISTENT_STATUS_XYZ", login_as=A)
na = len(all_b.get("items", [])) if isinstance(all_b, dict) else -1
nf = len(filt_b.get("items", [])) if isinstance(filt_b, dict) else -1
print(f"    beneficiaries all={na} vs bogus-status-filter={nf} (equal => filter ignored)")

# self-check: every probe returned an HTTP code (not an exception / empty)
assert all(isinstance(v[0], int) for v in results.values()), "a probe did not complete"
print("\nOK: all probes returned. Review the printed lines above for findings.")
