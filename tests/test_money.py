import json
from datetime import datetime
from decimal import Decimal as D

import pytest
from hypothesis import given
from hypothesis import strategies as st

from ringfence import config
from ringfence.money import (
    Contractor,
    MoneyError,
    dumps_money,
    loads_money,
    parse_amount,
    price_line,
    price_run,
    q,
)

amts = st.decimals(min_value=0, max_value=10_000_000, places=6, allow_nan=False)


@given(amts)
def test_q_idempotent(a):
    assert q(q(a, "GBP"), "GBP") == q(a, "GBP")


@given(st.lists(amts, max_size=20))
def test_sum_of_quantized_is_quantized(xs):
    total = sum((q(x, "USD") for x in xs), D(0))
    assert total == q(total, "USD")


@given(st.decimals(min_value=0, max_value=10_000_000, places=2, allow_nan=False))
def test_json_roundtrip(a):
    assert loads_money(dumps_money({"amount": a}))["amount"] == a


def test_dumps_bare_numbers():
    out = dumps_money({"a": D("1240.17"), "b": D("10000000.00"), "s": "x"})
    assert out == b'{"a": 1240.17, "b": 10000000.00, "s": "x"}'
    assert json.loads(dumps_money({"n": [D("1E+2")]})) == {"n": [100]}


def test_floats_rejected():
    for bad in (1.5, True):
        with pytest.raises(TypeError):
            parse_amount(bad)
    with pytest.raises(TypeError):
        dumps_money({"a": 1.5})


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "-1", "abc"])
def test_bad_amounts(bad):
    with pytest.raises(MoneyError):
        parse_amount(bad)


def test_half_up_and_unsupported():
    assert q(D("60.165"), "AUD") == D("60.17")
    assert q(D("0.005"), "GBP") == D("0.01")
    with pytest.raises(MoneyError) as e:
        q(D(1), "JPY")
    assert e.value.code == "CURRENCY_UNSUPPORTED"


def test_harbour_headline_shortfall():
    cs = [Contractor(f"h{i}", "harbour", "x", "AUD", "LOCAL", r)
          for i, r in enumerate((D("35.00"), D("38.40"), D("40.11")))]
    lines = [price_line(c, h) for c, h in zip(cs, (D(20), D("12.5"), D("1.5")))]
    assert [ln.amount for ln in lines] == [D("700.00"), D("480.00"), D("60.17")]
    p = price_run(lines, {"AUD": D(0), "GBP": D(10000000)})
    assert p.shortfall["AUD"] == D("1240.17") and p.shortfall["GBP"] == 0
    assert p.platform_fee == D("4.50")


def test_loads_money_decimal():
    assert isinstance(loads_money('{"a": 1.10}')["a"], D)


def test_clock_rf_now_only_shifts_business_time():
    config.clock.set_business(datetime.fromisoformat("2026-11-13T00:00:00+00:00"))
    assert config.clock.business_now().year == 2026
    assert config.clock.utc_now().year >= 2026 and config.clock.utc_now().tzinfo
    config.clock.set_business(None)
