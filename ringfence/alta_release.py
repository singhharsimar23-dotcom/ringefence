"""Before the executor runs, check that the chain holds exactly what the human approved. Read-only: this never signs, binds
or pulls. A run is released only when every READY line has its own credential whose terms equal the line, and no earlier
attempt of any line is still payable (the stale-credential double pay found while planning this build)."""
from __future__ import annotations

import time
from decimal import Decimal

from . import alta, store
from . import beneficiaries as ben
from .awx import AwxError, AwxTimeout
from .executor import line_specs
from .mandate import make_request_id


def problems(L, chain: alta.Chain, run_id: str, tenant: str, now: float | None = None) -> list[dict]:
    """[] = the chain matches the approval. Each problem names a line and a code."""
    now = time.time() if now is None else now
    run = store.get_run(L, run_id, tenant)
    ap = store.get_approval(L, run_id, tenant, run["round"])
    payees = ben.load_registry().get("tenants", {}).get(tenant, {}).get("payees", {})
    out: list[dict] = []

    def bad(ln, code, detail=""):
        out.append({"contractor_id": ln["contractor_id"], "code": code, "detail": detail})

    for ln in store.get_lines(L, run_id, tenant, round=run["round"], states=("READY", "PLANNED")):
        rid = ln["request_id"]
        try:
            s = chain.status(rid)
        except AwxTimeout as e:  # a credential the CLI cannot read is not a credential
            bad(ln, "credential_unreadable", str(e)[:80])
            continue
        try:
            want = alta.usd_to_usdz(Decimal(ln["amount"])) if ln["currency"] == "USD" else None
        except AwxError:
            want = None
        wallet = ((payees.get(ln["beneficiary_id"]) or {}).get("bank_details") or {}).get("account_number", "")
        if s is None:
            bad(ln, "no_credential")
        elif s["revoked"] or not s["bound"]:
            bad(ln, "not_payable", "revoked" if s["revoked"] else "not bound")
        elif s["payments"]:
            bad(ln, "already_paid")
        elif s["expiry"] <= now:
            bad(ln, "expired")
        elif ap is None:
            bad(ln, "no_approval")
        elif s["expiry"] > int(ap.expires_at.timestamp()):
            bad(ln, "outlives_approval")
        elif s["payee"].lower() != wallet.lower():
            bad(ln, "payee_not_the_pinned_wallet")
        elif want is None or not (s["cap"] == s["budget"] == want and s["occurrences"] == 1):
            bad(ln, "terms_differ")
        elif s["description"] != f"rf:{ap.batch_hash}:{rid}":
            bad(ln, "not_signed_for_this_batch", "the credential's description is not this approved batch and line")
        for k in range(1, ln["attempt"]):  # an older attempt that can still pay is a second payment waiting
            old = make_request_id(run_id, tenant, ln["contractor_id"], k)
            if chain.has(old):
                o = chain.status(old)
                if o["payments"]:
                    bad(ln, "earlier_attempt_paid", old[:12])
                elif o["bound"] and not o["revoked"] and o["expiry"] > now:
                    bad(ln, "earlier_attempt_still_payable", old[:12])
    return out


def release(orch, chain: alta.Chain, run_id: str, tenant: str) -> dict:
    """The only way an Alta run is released: preflight, then the orchestrator's own advance."""
    found = problems(orch.L, chain, run_id, tenant)
    if found:
        orch.L.append("ALTA_REFUSED", {"problems": found}, run_id, tenant)
        return {"released": False, "problems": found}
    return {"released": True, "state": orch.advance(run_id, tenant), "problems": []}


def export(L, run_id: str, tenant: str) -> dict:
    """What the approver's device receives: the approved batch, nothing the device has to take on trust beyond the hash it recomputes."""
    run = store.get_run(L, run_id, tenant)
    ap = store.get_approval(L, run_id, tenant, run["round"])
    lines = store.get_lines(L, run_id, tenant, round=run["round"])
    return {"run_id": run_id, "tenant": tenant, "round": run["round"], "batch_hash": ap.batch_hash if ap else None,
            "approval_expires_at": ap.expires_at.isoformat() if ap else None,
            "lines": [{**s.to_dict(), "usdz": str(alta.usd_to_usdz(s.amount))} for s in line_specs(lines)]}
