"""Open mandate (per-employer limits, HMAC-signed) and closed batch approval (bound to the exact batch).

The approval binds run_id + tenant + round + every line incl. its stored request_id, so approving
batch A can never authorise batch B, next week's identical batch, or a re-pay round.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any

from .config import get_key
from .money import canonical_json


def _sign(key_name: str, data: dict) -> str:
    return hmac.new(get_key(key_name), canonical_json(data).encode(), hashlib.sha256).hexdigest()


def _ok(key_name: str, data: dict, sig: str) -> bool:
    return hmac.compare_digest(_sign(key_name, data), sig or "")


def _dt(s: str | None) -> datetime | None:
    return datetime.fromisoformat(s) if s else None


@dataclass(frozen=True)
class Mandate:
    tenant: str
    currencies: tuple[str, ...]
    funding_currencies: tuple[str, ...]
    per_line_cap: dict[str, Decimal]
    per_run_cap: dict[str, Decimal]
    allowed_contractor_ids: tuple[str, ...]
    expires_at: datetime
    fx: str = "never"  # never | within_band
    rate_band_bps: int = 50
    auto_release: str = "never"  # never | if_no_diff
    approver_role: str = ""
    version: int = 1

    def to_dict(self) -> dict[str, Any]:
        return {
            "tenant": self.tenant, "currencies": list(self.currencies),
            "funding_currencies": list(self.funding_currencies),
            "per_line_cap": {k: str(v) for k, v in self.per_line_cap.items()},
            "per_run_cap": {k: str(v) for k, v in self.per_run_cap.items()},
            "allowed_contractor_ids": list(self.allowed_contractor_ids),
            "expires_at": self.expires_at.isoformat(), "fx": self.fx,
            "rate_band_bps": self.rate_band_bps, "auto_release": self.auto_release,
            "approver_role": self.approver_role, "version": self.version,
        }

    @classmethod
    def from_dict(cls, d: dict) -> Mandate:
        return cls(
            d["tenant"], tuple(d["currencies"]), tuple(d["funding_currencies"]),
            {k: Decimal(v) for k, v in d["per_line_cap"].items()},
            {k: Decimal(v) for k, v in d["per_run_cap"].items()},
            tuple(d["allowed_contractor_ids"]), datetime.fromisoformat(d["expires_at"]),
            d["fx"], d["rate_band_bps"], d["auto_release"], d["approver_role"], d["version"])


@dataclass(frozen=True)
class SignedMandate:
    mandate: Mandate
    signature: str

    def to_dict(self) -> dict:
        return {"mandate": self.mandate.to_dict(), "signature": self.signature}

    @classmethod
    def from_dict(cls, d: dict) -> SignedMandate:
        return cls(Mandate.from_dict(d["mandate"]), d["signature"])


def sign_mandate(m: Mandate) -> SignedMandate:
    return SignedMandate(m, _sign("RF_MANDATE_KEY", m.to_dict()))


def mandate_sig_valid(sm: SignedMandate) -> bool:
    return _ok("RF_MANDATE_KEY", sm.mandate.to_dict(), sm.signature)


@dataclass(frozen=True)
class LineSpec:
    """One line of a batch, exactly what is hashed."""
    contractor_id: str
    beneficiary_id: str
    amount: Decimal
    currency: str
    method: str
    source_currency: str
    attempt: int
    request_id: str

    def to_dict(self) -> dict:
        return {"contractor_id": self.contractor_id, "beneficiary_id": self.beneficiary_id,
                "amount": str(self.amount), "currency": self.currency, "method": self.method,
                "source_currency": self.source_currency, "attempt": self.attempt,
                "request_id": self.request_id}


def batch_hash(run_id: str, tenant: str, round: int, lines: list[LineSpec]) -> str:
    ordered = [ln.to_dict() for ln in sorted(lines, key=lambda x: x.contractor_id)]
    return hashlib.sha256(canonical_json(
        {"run_id": run_id, "tenant": tenant, "round": round, "lines": ordered}).encode()).hexdigest()


def make_request_id(run_id: str, tenant: str, contractor_id: str, attempt: int) -> str:
    """Deterministic, 50 chars, no amount in it (re-pricing can never mint a new id).
    Compute once, store on the line, and always reuse the stored value."""
    digest = hashlib.sha256(f"{run_id}|{tenant}|{contractor_id}|{attempt}".encode()).digest()
    return ("rf-" + base64.b32encode(digest).decode().rstrip("=").lower())[:50]


@dataclass(frozen=True)
class Approval:
    run_id: str
    tenant: str
    round: int
    batch_hash: str
    approver_id: str
    approver_role: str
    approved_at: datetime
    expires_at: datetime  # +2h, real UTC
    fx_quote_rate: Decimal | None = None
    rate_band_bps: int = 50
    signature: str = field(default="", compare=False)

    def body(self) -> dict:
        return {
            "run_id": self.run_id, "tenant": self.tenant, "round": self.round,
            "batch_hash": self.batch_hash, "approver_id": self.approver_id,
            "approver_role": self.approver_role, "approved_at": self.approved_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "fx_quote_rate": None if self.fx_quote_rate is None else str(self.fx_quote_rate),
            "rate_band_bps": self.rate_band_bps,
        }

    def to_dict(self) -> dict:
        return {**self.body(), "signature": self.signature}

    @classmethod
    def from_dict(cls, d: dict) -> Approval:
        return cls(d["run_id"], d["tenant"], d["round"], d["batch_hash"], d["approver_id"],
                   d["approver_role"], _dt(d["approved_at"]), _dt(d["expires_at"]),
                   None if d["fx_quote_rate"] is None else Decimal(d["fx_quote_rate"]),
                   d["rate_band_bps"], d["signature"])


def sign_approval(a: Approval) -> Approval:
    return Approval(**{**a.__dict__, "signature": _sign("RF_APPROVAL_KEY", a.body())})


def approval_sig_valid(a: Approval) -> bool:
    return _ok("RF_APPROVAL_KEY", a.body(), a.signature)
