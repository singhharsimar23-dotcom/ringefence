"""FX on the tenant's OWN account only. Live facts (PROBES.md P5): quotes are MULTI_USE, a quote accepts
sell_amount (exact drain), the conversion response id is `conversion_id`."""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from .awx import TenantClient
from .money import q


@dataclass(frozen=True)
class Quote:
    quote_id: str
    sell_currency: str
    buy_currency: str
    sell_amount: Decimal
    buy_amount: Decimal
    rate: Decimal  # client_rate


def get_quote(c: TenantClient, sell: str, buy: str, *, buy_amount: Decimal | None = None,
              sell_amount: Decimal | None = None) -> Quote:
    if (buy_amount is None) == (sell_amount is None):
        raise ValueError("exactly one of buy_amount / sell_amount")
    body = {"sell_currency": sell, "buy_currency": buy, "validity": "MIN_1"}
    body["buy_amount" if buy_amount is not None else "sell_amount"] = buy_amount if buy_amount is not None else sell_amount
    r = c.post("/fx/quotes/create", body)
    return Quote(r["quote_id"], sell, buy, Decimal(r["sell_amount"]), Decimal(r["buy_amount"]), Decimal(r["client_rate"]))


def convert(c: TenantClient, request_id: str, qt: Quote, *, by: str) -> dict:
    """by='buy' fixes the buy amount (payroll top-up); by='sell' fixes the sell amount (drain)."""
    amt = ("buy_amount", qt.buy_amount) if by == "buy" else ("sell_amount", qt.sell_amount)
    return c.post("/fx/conversions/create", {"request_id": request_id, "quote_id": qt.quote_id,
                                             "sell_currency": qt.sell_currency, "buy_currency": qt.buy_currency,
                                             amt[0]: amt[1]})


@dataclass(frozen=True)
class Leg:
    sell: str
    buy: str
    quote: Quote


def plan(c: TenantClient, mandate, need: dict[str, Decimal], avail: dict[str, Decimal]) -> list[Leg]:
    """Cover ONLY this tenant's shortfall per currency by selling the first mandate funding currency that has
    spare balance. Quotes only; nothing moves. An empty list for a real shortfall makes the gate deny it."""
    legs: list[Leg] = []
    sold: dict[str, Decimal] = {}
    zero = Decimal(0)
    if mandate.fx == "never":
        return legs
    for cur, n in sorted(need.items()):
        short = n - avail.get(cur, zero)
        if short <= 0:
            continue
        for f in mandate.funding_currencies:
            if f == cur:
                continue
            qt = get_quote(c, f, cur, buy_amount=q(short, cur))
            if avail.get(f, zero) - need.get(f, zero) - sold.get(f, zero) >= qt.sell_amount:
                legs.append(Leg(f, cur, qt))
                sold[f] = sold.get(f, zero) + qt.sell_amount
                break
    return legs


def leg_request_id(run_id: str, tenant: str, leg: Leg, round: int) -> str:
    """One conversion per (run, tenant, currency, round); a duplicate means it already happened."""
    return f"fx-{run_id}-{tenant}-{leg.buy}-r{round}"


def drain(c: TenantClient, ccy: str, into: str, request_id: str) -> Decimal:
    """Sell this tenant's whole `ccy` balance into `into`, in the same account. Returns the amount sold."""
    bal = q(c.balances().get(ccy, Decimal(0)), ccy)
    if bal <= 0:
        return Decimal(0)
    convert(c, request_id, get_quote(c, ccy, into, sell_amount=bal), by="sell")
    return bal
