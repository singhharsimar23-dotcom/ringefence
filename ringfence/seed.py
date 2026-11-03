"""Trusted seed registry (demo/employers.json): contractors, rates, users, default mandates.
Rates and bank corridors come ONLY from here (or var/registry.json), never from the model or an email."""
from __future__ import annotations

import json
from datetime import timedelta
from decimal import Decimal
from functools import lru_cache

from .config import ROOT, clock
from .mandate import Mandate, SignedMandate, sign_mandate
from .money import Contractor

SEED_PATH = ROOT / "demo" / "employers.json"


@lru_cache(maxsize=1)
def load() -> dict:
    return json.loads(SEED_PATH.read_text(encoding="utf-8"))


def contractor_seeds(tenant: str | None = None) -> list[dict]:
    return [c for c in load()["contractors"] if tenant in (None, c["tenant"])]


def contractors(tenant: str | None = None) -> dict[str, Contractor]:
    return {c["id"]: Contractor(c["id"], c["tenant"], c["name"], c["currency"], c["method"], Decimal(c["rate"]))
            for c in contractor_seeds(tenant)}


def default_mandates() -> dict[str, SignedMandate]:
    exp = clock.utc_now() + timedelta(days=90)
    out = {}
    for t, m in load()["mandates"].items():
        out[t] = sign_mandate(Mandate(
            tenant=t, currencies=tuple(m["currencies"]), funding_currencies=tuple(m["funding_currencies"]),
            per_line_cap={k: Decimal(v) for k, v in m["per_line_cap"].items()},
            per_run_cap={k: Decimal(v) for k, v in m["per_run_cap"].items()},
            allowed_contractor_ids=tuple(contractors(t)), expires_at=exp, fx=m["fx"],
            rate_band_bps=m["rate_band_bps"], auto_release=m["auto_release"], approver_role=m["approver_role"]))
    return out
