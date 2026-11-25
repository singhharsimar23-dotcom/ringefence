"""Each attack against a broad mandate and against Ringfence, on the fake chain. The expected cells are the claim."""
from decimal import Decimal as D

import pytest
from fake_chain import FakeChain

from ringfence.alta_attacks import AFTER, BEFORE, NAIVE, SAFE, Lab, verdict

NOAH, ZOE, MULE = "0x" + "1" * 40, "0x" + "2" * 40, "0x" + "e" * 40
PRINCIPAL = "0x" + "a" * 40


@pytest.fixture
def lab(tmp_path):
    chain = FakeChain(tmp_path / "unused", PRINCIPAL, funds=D(10000))
    return Lab(chain, tmp_path / "owner.json", PRINCIPAL, tmp_path / "lab", wallets={"noah": NOAH, "zoe": ZOE}, mule=MULE)


def test_every_attack_pays_against_the_broad_mandate_and_is_refused_by_ringfence(lab):
    v = verdict(lab.all())
    for n in (1, 2, 3, 4, 5):
        assert v[n] == {NAIVE: "paid", SAFE: "refused"}, n


def test_the_two_bugs_we_found_in_our_first_design_paid_twice_and_are_fixed(lab):
    v = verdict(lab.all())
    assert v[6] == {BEFORE: "paid", AFTER: "refused"}
    assert v[7] == {BEFORE: "paid", AFTER: "refused"}


def test_refusals_name_the_chain_rule_that_stopped_them(lab):
    reasons = {(r["attack"], r["side"]): r["reason"] for r in lab.all() if r["outcome"] == "refused"}
    assert reasons[(1, SAFE)] == "mandate_payee_not_listed" and reasons[(2, SAFE)] == "mandate_payee_not_listed"
    assert reasons[(3, SAFE)] == "mandate_cap_exceeded"
    assert reasons[(4, SAFE)] in ("mandate_occurrences_used", "mandate_budget_spent")
    assert reasons[(6, AFTER)] == "mandate_revoked" and reasons[(7, AFTER)] == "mandate_revoked"


def test_money_lost_is_counted_only_for_paid_cells(lab):
    rows = lab.all()
    assert all(D(r["usd_lost"]) == 0 for r in rows if r["outcome"] == "refused")
    assert D(next(r for r in rows if r["attack"] == 1 and r["side"] == NAIVE)["usd_lost"]) == D(55)
