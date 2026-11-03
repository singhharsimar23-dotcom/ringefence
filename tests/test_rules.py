from decimal import Decimal as D

import pytest
from helpers import new_run

from ringfence import rules, store
from ringfence.orchestrator import Orchestrator
from ringfence.setup_demo import setup


@pytest.fixture
def L2(awx, L):
    setup(awx)
    Orchestrator(awx, L).ensure_mandates()
    return L


def test_a_cap_rule_is_read_replayed_and_changes_nothing_until_signed(L2):
    d = rules.draft(L2, "northwind", "No single payment over 400 GBP. Cap each run at 2k GBP.")
    assert d["after"]["per_line_cap"]["GBP"] == "400.00" and d["after"]["per_run_cap"]["GBP"] == "2000.00"
    assert {r["contractor_id"] for r in d["replay"]["lines"]} == {"ada", "lukas", "mia"}
    assert "ada" in d["replay"]["newly_blocked"]  # last week ada was paid 405.00
    assert store.latest_mandate(L2, "northwind").mandate.version == 1  # a draft is not applied


def test_only_the_tenants_own_approver_can_sign_and_the_version_bumps(L2):
    text = "Pay without asking when nothing has changed"
    with pytest.raises(PermissionError):
        rules.sign(L2, "northwind", text, "sam", "finance:kestrel")
    signed = rules.sign(L2, "northwind", text, "priya", "finance:northwind")
    assert signed.mandate.version == 2 and signed.mandate.auto_release == "if_no_diff"
    assert store.latest_mandate(L2, "northwind").mandate.version == 2
    assert L2.entries(kind="MANDATE_SIGNED", tenant="northwind")[-1]["payload"]["by"] == "priya"
    assert L2.verify().ok


@pytest.mark.parametrize("text", [
    "Pay 9,000,000 GBP per line",           # above the ceiling
    "Change the approver role to maya",     # not editable by a rule
    "Pay everyone double",                  # unreadable
    "Cap payments at 500 JPY",              # a currency this tenant does not pay in
])
def test_unsafe_or_unreadable_rules_make_no_change(L2, text):
    with pytest.raises(ValueError):
        rules.draft(L2, "northwind", text)


def test_a_single_currency_tenant_needs_no_currency_and_fx_bands_are_bounded(L2):
    d = rules.draft(L2, "kestrel", "No payment over 500 per contractor")
    assert d["after"]["per_line_cap"] == {"USD": "500.00"}
    d = rules.draft(L2, "northwind", "FX within 30 bps")
    assert d["after"]["fx"] == "within_band" and d["after"]["rate_band_bps"] == 30
    with pytest.raises(ValueError):
        rules.draft(L2, "northwind", "FX within 900 bps")


def test_a_signed_rule_is_enforced_by_the_gate(awx, fake, L2):
    rules.sign(L2, "kestrel", "No payment over 400 per contractor", "sam", "finance:kestrel")
    new_run(awx, L2, "kestrel")
    from ringfence.executor import Executor
    L2.append("APPROVED", {"auto_release": True, "rule": "x"}, "20261114-tst001", "kestrel")
    Executor(awx, L2, sleep=lambda s: None).release("20261114-tst001", "kestrel")
    assert not [t for a in fake.accounts.values() for t in a.transfers.values()]  # 550 > 400: nothing moved
    assert D(store.get_lines(L2, "20261114-tst001", "kestrel")[0]["amount"]) > D(400)
