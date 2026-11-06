"""DISPLAY ONLY. The crossed-out "naive total" strip: what a careless system would think it can spend.

Nothing that decides or moves money may import this module (tests/test_architecture.py enforces it).
"""
from __future__ import annotations

from decimal import Decimal

from .awx import Awx, AwxError
from .config import EMPLOYERS
from .fx import get_quote
from .money import q


def naive_total(awx: Awx, target: str) -> tuple[Decimal, bool]:
    """Every employer's balances pooled and converted into `target` at a live quote. (total, complete)."""
    total, complete = Decimal(0), True
    rates: dict[str, Decimal] = {target: Decimal(1)}
    for t in EMPLOYERS:
        c = awx.for_tenant(t)
        for ccy, amt in c.balances().items():
            if not amt:  # adds nothing, and Airwallex rejects a 1-unit quote in many of these (amount_below_limit)
                continue
            if ccy not in rates:
                try:
                    rates[ccy] = get_quote(c, ccy, target, sell_amount=Decimal(1)).buy_amount
                except (AwxError, KeyError):
                    rates[ccy] = Decimal(0)
                    complete = False
            total += amt * rates[ccy]
    return q(total, target), complete
