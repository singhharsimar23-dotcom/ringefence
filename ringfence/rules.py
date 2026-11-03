"""Plain-English rule -> mandate draft -> replay over last week's payments -> a person signs.

The text is parsed by code into a closed set of changes (caps, auto-release, FX band). Anything it cannot read is
reported back, never guessed. A rule can only edit caps, auto_release and fx; currencies, contractors and the
approver role are not editable here. Nothing takes effect until the tenant's own finance approver signs.
"""
from __future__ import annotations

import dataclasses
import re
from decimal import Decimal, InvalidOperation

from . import inbox, store
from .ledger import Ledger
from .mandate import Mandate, SignedMandate, sign_mandate

CEILING = Decimal(50000)  # no rule may set a cap above this, whatever the text says
AMT = r"(?:[$£€]\s?)?(\d[\d,]*(?:\.\d{1,2})?)\s*(k\b)?"
CCY = r"\b(GBP|EUR|AUD|USD)\b"


def _money(num: str, k: str | None) -> Decimal:
    try:
        v = Decimal(num.replace(",", "")) * (1000 if k else 1)
    except InvalidOperation as e:
        raise ValueError(f"not an amount: {num}") from e
    if not 0 < v <= CEILING:
        raise ValueError(f"{v} is outside 0 to {CEILING}, which no rule may exceed")
    return v.quantize(Decimal("0.01"))


def _currency(text: str, m: Mandate) -> str:
    found = re.search(CCY, text, re.IGNORECASE)
    if found:
        ccy = found.group(1).upper()
    elif len(m.currencies) == 1:
        ccy = m.currencies[0]
    else:
        raise ValueError(f"which currency? {m.tenant} pays in {', '.join(m.currencies)}")
    if ccy not in m.currencies:
        raise ValueError(f"{m.tenant} does not pay in {ccy}")
    return ccy


def parse(text: str, current: Mandate) -> tuple[Mandate, list[dict], list[str]]:
    """Returns (draft, changes, ignored). Each sentence is read on its own; unreadable ones land in `ignored`."""
    draft, changes, ignored = current, [], []
    for raw in re.split(r"[.;\n]+", text):
        s = raw.strip()
        if not s:
            continue
        low = s.lower()
        try:
            if re.search(r"\b(role|approver|beneficiar\w*|bank|iban|currenc(y|ies))\b", low):
                raise ValueError("a rule cannot change who approves, who is paid or where")
            if re.search(r"\b(per|each|every|a|the)\s+(run|batch|payroll)\b|run cap|total", low) and (a := re.search(AMT, s, re.IGNORECASE)):
                ccy = _currency(s, draft)
                draft = dataclasses.replace(draft, per_run_cap={**draft.per_run_cap, ccy: _money(*a.groups())})
                changes.append({"field": f"per_run_cap.{ccy}", "text": s})
            elif re.search(r"per\s+(line|payment|contractor|person|transfer)|any one|single|cap", low) and (a := re.search(AMT, s, re.IGNORECASE)):
                ccy = _currency(s, draft)
                draft = dataclasses.replace(draft, per_line_cap={**draft.per_line_cap, ccy: _money(*a.groups())})
                changes.append({"field": f"per_line_cap.{ccy}", "text": s})
            elif re.search(r"auto|without asking|nothing (has )?changed|no changes", low):
                on = not re.search(r"\b(never|don'?t|do not|no auto|stop)\b", low)
                draft = dataclasses.replace(draft, auto_release="if_no_diff" if on else "never")
                changes.append({"field": "auto_release", "text": s})
            elif re.search(r"\bfx\b|convert|exchange", low):
                off = re.search(r"\b(no|never|don'?t|do not|stop|disable)\b", low)
                band = re.search(r"(\d{1,3})\s*(?:bps|basis points)", low)
                if off:
                    draft = dataclasses.replace(draft, fx="never")
                elif band and 1 <= int(band.group(1)) <= 200:
                    draft = dataclasses.replace(draft, fx="within_band", rate_band_bps=int(band.group(1)))
                else:
                    raise ValueError("say 'no FX' or 'FX within 30 bps' (1 to 200)")
                changes.append({"field": "fx", "text": s})
            else:
                ignored.append(s)
        except ValueError as e:
            ignored.append(f"{s} ({e})")
    return draft, changes, ignored


def replay(tenant: str, old: Mandate, new: Mandate) -> dict:
    """Last run's payments (demo/history) against both mandates: which would be blocked, and what changes."""
    from .seed import contractors
    cs = contractors(tenant)
    rows, totals = [], {}
    for cid, amt in inbox.history(tenant).items():
        c = cs.get(cid)
        if c is None:
            continue
        ccy = c.currency
        totals[ccy] = totals.get(ccy, Decimal(0)) + amt
        rows.append({"contractor_id": cid, "name": c.name, "amount": str(amt), "currency": ccy,
                     "was": _line_ok(old, ccy, amt), "now": _line_ok(new, ccy, amt)})
    runs = [{"currency": k, "amount": str(v), "was": v <= old.per_run_cap.get(k, Decimal(0)),
             "now": v <= new.per_run_cap.get(k, Decimal(0))} for k, v in sorted(totals.items())]
    return {"lines": rows, "runs": runs,
            "newly_blocked": [r["contractor_id"] for r in rows if r["was"] and not r["now"]],
            "newly_allowed": [r["contractor_id"] for r in rows if not r["was"] and r["now"]]}


def _line_ok(m: Mandate, ccy: str, amt: Decimal) -> bool:
    return amt <= m.per_line_cap.get(ccy, Decimal(0))


def draft(L: Ledger, tenant: str, text: str) -> dict:
    sm = store.latest_mandate(L, tenant)
    if sm is None:
        raise LookupError(f"{tenant} has no mandate to change")
    new, changes, ignored = parse(text, sm.mandate)
    if not changes:
        raise ValueError("Nothing in that could be turned into a rule. " + (" ".join(ignored) if ignored else ""))
    return {"tenant": tenant, "base_version": sm.mandate.version, "before": sm.mandate.to_dict(), "after": new.to_dict(),
            "changes": changes, "ignored": ignored, "replay": replay(tenant, sm.mandate, new)}


def sign(L: Ledger, tenant: str, text: str, by: str, role: str) -> SignedMandate:
    """Re-derives the draft from the text (never trusts a client-supplied mandate) and signs it as version+1."""
    sm = store.latest_mandate(L, tenant)
    if sm is None or role != sm.mandate.approver_role:
        raise PermissionError(f"{by} ({role}) may not sign rules for {tenant}")
    new, changes, _ = parse(text, sm.mandate)
    if not changes:
        raise ValueError("nothing to sign")
    signed = sign_mandate(dataclasses.replace(new, version=sm.mandate.version + 1))
    with L.tx() as tx:
        store.save_mandate(tx, signed)
        tx.append("MANDATE_SIGNED", {"tenant": tenant, "version": signed.mandate.version, "by": by, "role": role,
                                     "rule": text.strip()[:500], "changes": changes}, None, tenant)
    return signed
