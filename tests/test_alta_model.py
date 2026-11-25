"""The exhaustive model of a hostile server: Ringfence's mandates hold, a broad mandate and a reopen without revoke do not."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "formal"))
from alta_model import check


def test_ringfence_mandates_violate_nothing():
    assert check("ringfence")[1] == []


def test_a_broad_mandate_diverts_and_double_pays():
    assert "PaidOnlyApproved" in check("naive")[1]


def test_a_reopen_that_leaves_the_old_credential_payable_double_pays():
    assert check("no_revoke")[1] == ["NoDoublePay"]
