import logging
from decimal import Decimal as D

import pytest

from ringfence.awx import Awx, AwxError, AwxTimeout, build_backend
from ringfence.config import tenants

T = tenants(fake=True)


def test_binding_is_fixed_and_cached(awx):
    c = awx.for_tenant("kestrel")
    assert c is awx.for_tenant("kestrel")
    assert c.account_id == T["kestrel"].account_id and c.tenant_key == "kestrel"
    with pytest.raises(AttributeError):
        c.account_id = T["harbour"].account_id
    with pytest.raises(AttributeError):
        c.on_behalf_of = "x"  # no obo knob exists
    assert c.get("/account")["id"] == T["kestrel"].account_id
    assert awx.for_tenant("harbour").get("/account")["id"] == T["harbour"].account_id


def test_one_relogin_on_expired_token(awx, fake):
    c = awx.for_tenant("northwind")
    c.get("/account")
    old = c._token
    fake.inject("token_expired_once")
    assert c.get("/account")["id"] == T["northwind"].account_id
    assert c._token != old and old not in fake.tokens


def test_credentials_invalid_is_not_retried(awx, fake):
    awx.for_tenant("northwind").get("/account")
    n = len(fake.tokens)
    assert awx.probe_cross_tenant("northwind", "kestrel") == (401, "credentials_invalid")
    assert len(fake.tokens) == n  # no re-login on a cross-tenant refusal


def test_forgotten_token_relogs_once(awx, fake):
    c = awx.for_tenant("northwind")
    c.get("/account")
    fake.tokens.clear()  # live: an unknown bearer is 401 unauthorized -> one fresh login, then success
    assert c.get("/account")["id"] == T["northwind"].account_id and len(fake.tokens) == 1


def test_get_retries_then_gives_up(awx, fake):
    c = awx.for_tenant("northwind")
    fake.inject("error_before_commit", status=503, n=2, path="balances", method="GET")
    assert "GBP" in c.balances()  # 2 failures, 3rd attempt works
    fake.inject("error_before_commit", status=503, n=10, path="balances", method="GET")
    with pytest.raises(AwxError) as e:
        c.balances()
    assert e.value.status == 503
    assert sum(1 for m, p, _ in fake.log if p == "balances/current") == 3 + 4


def test_post_money_never_retries(awx, fake):
    c = awx.for_tenant("northwind")
    fake.inject("error_before_commit", status=500, n=5)
    with pytest.raises(AwxError):
        c.post_money("/transfers/create", {"request_id": "rf-req-0000000009"})
    assert sum(1 for m, p, _ in fake.log if p == "transfers/create") == 1


def test_post_money_timeout_surfaces_as_awxtimeout(awx, fake):
    fake.inject("timeout_after_commit")
    with pytest.raises(AwxTimeout):
        awx.for_tenant("northwind").post_money("/transfers/create", {"request_id": "rf-req-0000000009"})


def test_post_retries_only_with_request_id(awx, fake):
    c = awx.for_tenant("northwind")
    fake.inject("error_before_commit", status=500, n=1, path="global_accounts/create")
    ga = c.post("/global_accounts/create", {"request_id": "ga-req-0001", "country_code": "AU",
                                            "nick_name": "x", "required_features": [{"currency": "AUD", "transfer_method": "LOCAL"}]})
    assert ga["status"] == "ACTIVE"
    fake.inject("error_before_commit", status=500, n=1, path="global_accounts/create")
    with pytest.raises(AwxError):
        c.post("/global_accounts/create", {"country_code": "AU", "nick_name": "x"})


def test_no_secret_in_logs_or_reprs(awx, fake, caplog):
    caplog.set_level(logging.DEBUG)
    c = awx.for_tenant("northwind")
    c.balances()
    awx.probe_cross_tenant("northwind", "kestrel")
    secrets = set(fake.tokens) | {"fake"}
    text = caplog.text + repr(c) + repr(awx)
    assert all(s not in text for s in fake.tokens)
    assert "Bearer" not in text and secrets  # tokens were issued, none leaked


def test_money_parsed_as_decimal(awx):
    assert all(isinstance(v, D) for v in awx.for_tenant("northwind").balances().values())


def test_build_backend_fake():
    a, f = build_backend("fake")
    assert isinstance(a, Awx) and f is not None
    assert a.for_tenant("harbour").get("/account")["id"] == "acct_FAKE_harbour"
