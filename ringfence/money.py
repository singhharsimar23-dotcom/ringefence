"""Money: Decimal only, never float. Airwallex amounts are major units (100 = one hundred)."""
from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

CURRENCIES = {"GBP": 2, "EUR": 2, "USD": 2, "AUD": 2}
FEE_PER_PAYOUT = Decimal("1.50")  # GBP, charged on landed payouts only (fees.py)
SWIFT_FEE = ("EUR", Decimal("12.85"))  # flat, added before conversion


class MoneyError(ValueError):
    def __init__(self, code: str, detail: str = ""):
        super().__init__(f"{code}: {detail}" if detail else code)
        self.code = code


def check_ccy(ccy: str) -> str:
    if ccy not in CURRENCIES:
        raise MoneyError("CURRENCY_UNSUPPORTED", str(ccy))
    return ccy


def q(amount: Decimal, ccy: str) -> Decimal:
    return amount.quantize(Decimal(1).scaleb(-CURRENCIES[check_ccy(ccy)]), rounding=ROUND_HALF_UP)


def parse_amount(x: Any, allow_negative: bool = False) -> Decimal:
    if isinstance(x, (bool, float)) or not isinstance(x, (str, int, Decimal)):
        raise TypeError(f"{type(x).__name__} is not allowed for money")
    try:
        d = Decimal(x)
    except Exception as e:
        raise MoneyError("INVALID_AMOUNT", repr(x)) from e
    if not d.is_finite():
        raise MoneyError("INVALID_AMOUNT", "not finite")
    if d < 0 and not allow_negative:
        raise MoneyError("INVALID_AMOUNT", "negative")
    return d


def canonical_json(obj: Any) -> str:
    """The one canonical serialisation for hashes and signatures; Decimals (and datetimes) become strings."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def loads_money(text: str | bytes) -> Any:
    """Every JSON number with a fraction comes back as Decimal."""
    return json.loads(text, parse_float=Decimal)


def dumps_money(body: Any) -> bytes:
    """Decimals become bare JSON numbers built from their exact decimal string; floats are rejected.
    Send with content=, never json=."""
    toks: list[str] = []
    marker = uuid.uuid4().hex

    def walk(o: Any) -> Any:
        if isinstance(o, float):
            raise TypeError("float in request body")
        if isinstance(o, Decimal):
            if not o.is_finite():
                raise MoneyError("INVALID_AMOUNT", "not finite")
            toks.append(format(o, "f"))
            return f"{marker}{len(toks) - 1}"
        if isinstance(o, dict):
            return {k: walk(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [walk(v) for v in o]
        return o

    s = json.dumps(walk(body))
    for i, t in enumerate(toks):
        s = s.replace(f'"{marker}{i}"', t)
    return s.encode()


@dataclass(frozen=True)
class Contractor:
    id: str
    tenant: str
    name: str
    currency: str
    method: str  # LOCAL | SWIFT
    rate: Decimal  # per hour, from the trusted registry only


@dataclass(frozen=True)
class Line:
    contractor_id: str
    tenant: str
    hours: Decimal
    rate: Decimal
    amount: Decimal
    currency: str
    method: str


def price_line(c: Contractor, hours: Decimal) -> Line:
    """Hours come from code-parsed timesheets, the rate from the registry; never from the model."""
    h = parse_amount(hours)
    return Line(c.id, c.tenant, h, c.rate, q(h * c.rate, c.currency), c.currency, c.method)


@dataclass
class RunPrice:
    net: dict[str, Decimal] = field(default_factory=dict)
    swift_fees: dict[str, Decimal] = field(default_factory=dict)
    platform_fee: Decimal = Decimal("0.00")  # GBP
    need: dict[str, Decimal] = field(default_factory=dict)
    own_available: dict[str, Decimal] = field(default_factory=dict)
    shortfall: dict[str, Decimal] = field(default_factory=dict)


def price_run(lines: list[Line], own_available: dict[str, Decimal],
              fee_per_payout: Decimal = FEE_PER_PAYOUT) -> RunPrice:
    """`own_available` must be this tenant's own /balances/current, never a sum across tenants."""
    if len({ln.tenant for ln in lines}) > 1:
        raise MoneyError("TENANT_MISMATCH", "lines span tenants")
    p = RunPrice()
    for ln in lines:
        p.net[ln.currency] = p.net.get(ln.currency, Decimal(0)) + ln.amount
        if ln.method == "SWIFT":
            c, fee = SWIFT_FEE
            p.swift_fees[c] = p.swift_fees.get(c, Decimal(0)) + fee
    p.platform_fee = q(fee_per_payout * len(lines), "GBP")
    need = dict(p.net)
    for c, v in p.swift_fees.items():
        need[c] = need.get(c, Decimal(0)) + v
    if lines:
        need["GBP"] = need.get("GBP", Decimal(0)) + p.platform_fee
    p.need = {c: q(v, c) for c, v in need.items()}
    for c, v in p.need.items():
        have = own_available.get(c, Decimal(0))
        p.own_available[c] = have
        p.shortfall[c] = max(Decimal(0), v - have)
    return p
