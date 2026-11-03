"""The invariant checker must fail when the thing it guards is broken."""
from decimal import Decimal

import pytest
from helpers import RUN, new_run
from invariants import assert_invariants

from ringfence import beneficiaries as ben
from ringfence import store
from ringfence.config import tenants
from ringfence.executor import Executor


@pytest.fixture
def paid(awx, fake, L):
    new_run(awx, L, "kestrel")
    L.append("APPROVED", {"auto_release": True, "rule": "mandate auto_release if_no_diff, no changes"}, RUN, "kestrel")  # as the orchestrator writes it
    ex = Executor(awx, L, sleep=lambda s: None)
    ex.release(RUN, "kestrel")
    assert_invariants(L, fake)  # a clean run passes
    return L


def _any_beneficiary(tenant):
    return next(iter(ben.load_registry()["tenants"][tenant]["beneficiaries"].values()))


def test_i3_a_transfer_with_no_intent_is_caught(awx, fake, paid):
    awx.for_tenant("kestrel").post_money("/transfers/create", {
        "request_id": "rogue-transfer-0000001", "beneficiary_id": _any_beneficiary("kestrel"), "transfer_amount": Decimal("1.00"),
        "transfer_currency": "USD", "source_currency": "USD", "transfer_method": "LOCAL", "reason": "x", "reference": "x"})
    with pytest.raises(AssertionError, match="I1|I3"):
        assert_invariants(paid, fake)


def test_i7_an_intent_without_an_approval_is_caught(awx, fake, L):
    new_run(awx, L, "northwind", state="AWAITING_APPROVAL")
    L.append("INTENT", {"contractor_id": "ada", "request_id": "x" * 20, "amount": "450.00", "currency": "GBP", "attempt": 1},
             RUN, "northwind")
    with pytest.raises(AssertionError, match="I7"):
        assert_invariants(L, fake)


def test_i8_a_token_in_the_ledger_is_caught(awx, fake, paid):
    token = next(t for t in fake.tokens if t)
    paid.append("ALERT", {"kind": "oops", "detail": f"leaked {token}"}, RUN, "kestrel")
    with pytest.raises(AssertionError, match="I8"):
        assert_invariants(paid, fake)


def test_i9_a_double_fee_is_caught(awx, fake, paid):
    paid.append("FEE_CHARGED", {"amount": "100.00", "currency": "GBP", "transfer_id": "t", "request_id": "r", "round": 1}, RUN, "kestrel")
    with pytest.raises(AssertionError, match="I9"):
        assert_invariants(paid, fake)


def test_i5_an_amount_that_differs_from_the_intent_is_caught(awx, fake, paid):
    t = next(iter(fake.accounts[tenants(fake=True)["kestrel"].account_id].transfers.values()))
    t["transfer_amount"] = t["transfer_amount"] + 1
    with pytest.raises(AssertionError, match="I5"):
        assert_invariants(paid, fake)
    assert store.get_lines(paid, RUN, "kestrel")  # the run itself is untouched
