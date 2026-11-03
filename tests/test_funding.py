import re
from datetime import date
from decimal import Decimal as D

from helpers import RUN, acct, new_run

from ringfence import funding
from ringfence.setup_demo import setup

PAY = date(2026, 11, 14)


def harbour_ga(fake):
    return next(g for g in fake.accounts[acct("harbour")].gas.values() if g["required_features"][0]["currency"] == "AUD")


def test_act_by_is_cutoff_minus_buffer_in_the_tenants_timezone():
    t = funding.act_by("AUD", PAY, "Australia/Sydney")
    assert (t.hour, t.minute, t.tzname()) == (9, 0, "AEDT")  # 11:00 cut-off - 2h
    assert funding.act_by("GBP", PAY, "Europe/London").hour == 10


def test_reference_is_short_and_bank_safe():
    refs = {funding.new_reference("harbour", RUN) for _ in range(20)}
    assert len(refs) > 1 and all(re.fullmatch(r"[A-Z0-9-]{1,18}", r) for r in refs)


def test_request_then_match_only_this_tenants_exact_deposit(awx, fake, L):
    setup(awx)
    new_run(awx, L, "harbour")
    req = funding.request_funding(awx, L, RUN, "harbour", "AUD", D("1240.17"), PAY)
    assert req["routing_type"] == "bsb" and req["amount"] == "1240.17"
    assert funding.request_funding(awx, L, RUN, "harbour", "AUD", D("1240.17"), PAY) == req  # idempotent
    ga = harbour_ga(fake)["id"]
    # wrong reference, wrong status, and the same reference arriving in ANOTHER tenant: none of them match
    fake.deposit(acct("harbour"), ga, D("1240.17"), "RF-HAR-WRONG", "SETTLED")
    fake.deposit(acct("harbour"), ga, D("1240.17"), req["reference"], "REJECTED")
    kes_ga = next(iter(fake.accounts[acct("kestrel")].gas))
    fake.deposit(acct("kestrel"), kes_ga, D("1240.17"), req["reference"], "SETTLED")
    assert funding.match_deposits(awx, L, RUN, "harbour") == []
    assert L.entries(kind="FUNDING_MATCHED") == []
    fake.deposit(acct("harbour"), ga, D("1240.17"), req["reference"], "SETTLED")
    got = funding.match_deposits(awx, L, RUN, "harbour")
    assert [d["reference"] for d in got] == [req["reference"]]
    assert funding.match_deposits(awx, L, RUN, "harbour") == []  # a deposit matches once
    assert len(L.entries(kind="FUNDING_MATCHED")) == 1 and len(L.entries(kind="FUNDING_REQUESTED")) == 1
    assert L.verify().ok
