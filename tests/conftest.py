import pytest

from ringfence.awx import Awx
from ringfence.config import tenants
from ringfence.fake_awx import FakeAirwallex


@pytest.fixture(autouse=True)
def _isolated_var(tmp_path, monkeypatch):
    """Keys/db never touch the real var/ dir; fixed signing keys keep tests deterministic."""
    monkeypatch.setenv("RF_VAR", str(tmp_path / "var"))
    monkeypatch.setenv("RF_MANDATE_KEY", "test-mandate-key")
    monkeypatch.setenv("RF_APPROVAL_KEY", "test-approval-key")


@pytest.fixture
def fake():
    return FakeAirwallex({k: t.account_id for k, t in tenants(fake=True).items()})


@pytest.fixture
def awx(fake):
    return Awx(transport=fake.transport, tenant_map=tenants(fake=True), sleep=lambda s: None)


@pytest.fixture
def L():
    from ringfence.ledger import Ledger
    return Ledger()


@pytest.fixture
def ex(awx, L):
    from ringfence.executor import Executor
    return Executor(awx, L, sleep=lambda s: None)
