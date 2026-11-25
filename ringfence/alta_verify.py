"""Proof for an Alta run: the ledger and the chain are compared line by line, in both directions, and the result is signed.

For every line of the approved batch the chain's own record of its credential must say what the human approved (payee,
amount, one pull, this batch hash in the signed description), and the payments on the chain must match the ledger: a line
the ledger calls PAID has exactly one payment of exactly its amount, a line it does not call PAID has none, and every
payment on the chain has an INTENT written before it. Limit, stated in the certificate: only credentials this server
holds can be checked; Alta has no command that lists a principal's mandates."""
from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from . import alta, metal, store, verify
from . import beneficiaries as ben
from .alta_device import _spec
from .awx import AwxError, AwxTimeout
from .config import clock
from .mandate import batch_hash, make_request_id

LIMIT = ("Checks the credentials this server holds. Alta has no command that lists a principal's mandates, so a mandate "
         "written outside this server would not appear here.")


def report(L, chain: alta.Chain, run_id: str, tenant: str) -> dict:
    run = store.get_run(L, run_id, tenant)
    ap = store.get_approval(L, run_id, tenant, run["round"])
    payees = ben.load_registry().get("tenants", {}).get(tenant, {}).get("payees", {})
    intents = {e["payload"].get("request_id") for e in L.entries(run_id=run_id, kind="INTENT", tenant=tenant)}
    lines = []
    for ln in store.get_lines(L, run_id, tenant, round=run["round"]):
        rid, checks = ln["request_id"], []

        def check(name, ok, detail="", checks=checks):
            checks.append({"name": name, "ok": bool(ok), "detail": detail})

        try:
            s = chain.status(rid)
            want = alta.usd_to_usdz(Decimal(ln["amount"])) if ln["currency"] == "USD" else None
        except (AwxError, AwxTimeout) as e:
            s, want = None, None
            check("credential_readable", False, str(e)[:80])
        wallet = ((payees.get(ln["beneficiary_id"]) or {}).get("bank_details") or {}).get("account_number", "")
        check("credential_exists", s is not None)
        if s is not None:
            check("bound_by_the_owner", s["bound"])
            check("pays_only_the_pinned_wallet", s["payee"].lower() == wallet.lower() != "")
            check("exactly_this_amount_once", want is not None and s["cap"] == s["budget"] == want and s["occurrences"] == 1)
            check("signed_for_this_approved_batch", ap is not None and s["description"] == f"rf:{ap.batch_hash}:{rid}")
            check("never_paid_twice", s["payments"] <= 1)
            check("ledger_state_matches_chain", (s["payments"] == 1 and s["spent"] == want) if ln["state"] == "PAID"
                  else s["payments"] == 0, f"line {ln['state']}, chain payments {s['payments']}")
            check("every_payment_has_an_intent", s["payments"] == 0 or rid in intents)
        for k in range(1, ln["attempt"]):  # an older attempt that could still pay is a second payment waiting
            old = make_request_id(run_id, tenant, ln["contractor_id"], k)
            if chain.has(old) and (o := chain.status(old)) is not None:
                check("earlier_attempt_cannot_pay", o["revoked"] or o["payments"] > 0 or not o["bound"], old[:12])
        lines.append({"contractor_id": ln["contractor_id"], "request_id": rid, "state": ln["state"],
                      "mandate": (s or {}).get("mandate"), "spent_usdz": str((s or {}).get("spent", 0)),
                      "ok": all(c["ok"] for c in checks), "checks": checks})
    return {"ok": bool(lines) and all(x["ok"] for x in lines), "settled": bool(lines) and all(x["state"] == "PAID" for x in lines),
            "run_id": run_id, "tenant": tenant, "limit": LIMIT,
            "batch_hash": ap.batch_hash if ap else None, "lines": lines}


def audit(export: dict, creds: Path, book: dict | None = None, runner=None) -> list[dict]:
    specs = [_spec(x) for x in export["lines"]]
    out = [{"line": "batch", "ok": batch_hash(export["run_id"], export["tenant"], export["round"], specs) == export["batch_hash"],
            "why": "the lines hash to the approved batch hash"}]
    chain = alta.Chain(runner or metal.run_cli, creds)
    for x in export["lines"]:
        rid, why, ok = x["request_id"], [], True
        s = chain.status(rid)
        want = alta.usd_to_usdz(Decimal(x["amount"]))
        wallet = (book or {}).get(x["contractor_id"]) or x.get("wallet") or (s or {}).get("payee")
        for name, good in (("credential held", s is not None),
                           ("bound", bool(s and s["bound"])),
                           ("payee is the wallet", bool(s and wallet and s["payee"].lower() == wallet.lower())),
                           ("amount once", bool(s and s["cap"] == s["budget"] == want and s["occurrences"] == 1)),
                           ("approved batch in the signed description", bool(s and s["description"] == f"rf:{export['batch_hash']}:{rid}")),
                           ("at most one payment", bool(s and s["payments"] <= 1))):
            if not good:
                ok = False
                why.append(name)
        out.append({"line": x["contractor_id"], "ok": ok, "why": "; ".join(why) or "matches", "payments": (s or {}).get("payments"),
                    "spent_usdz": str((s or {}).get("spent", 0))})
    return out


def certificate(L, rep: dict) -> dict:
    seq, h = L.head()
    return verify.sign({"kind": "alta_settlement", "tenant": rep["tenant"], "run_id": rep["run_id"], "issued_at": clock.utc_now().isoformat(),
                        "result": ("PASS" if rep["settled"] else "INCOMPLETE") if rep["ok"] else "FAIL", "batch_hash": rep["batch_hash"], "limit": LIMIT,
                        "lines": [{"request_id": x["request_id"], "mandate": x["mandate"], "spent_usdz": x["spent_usdz"], "ok": x["ok"]}
                                  for x in rep["lines"]],
                        "checks": [{"line": x["request_id"][:12], "name": c["name"], "ok": c["ok"]} for x in rep["lines"] for c in x["checks"]],
                        "ledger_head": {"seq": seq, "hash": h}})


def write(doc: dict, dest: Path | None = None) -> Path:
    d = dest or verify.CERT_DIR
    d.mkdir(parents=True, exist_ok=True)
    p = d / f"alta_{doc['body']['run_id']}.json"
    p.write_text(json.dumps(doc, indent=1, sort_keys=True), encoding="utf-8")
    return p


__all__ = ["audit", "certificate", "report", "write"]
