from decimal import Decimal as D

import httpx
import pytest

from ringfence.awx import AwxError
from ringfence.config import tenants

T = tenants(fake=True)
GB_BEN = {"nickname": "Ada", "transfer_methods": ["LOCAL"], "beneficiary": {
    "entity_type": "PERSONAL", "first_name": "Ada", "last_name": "Okoye",
    "bank_details": {"bank_country_code": "GB", "account_currency": "GBP", "account_name": "Ada Okoye",
                     "bank_name": "Barclays", "account_routing_type1": "sort_code",
                     "account_routing_value1": "040004", "account_number": "12345678"}}}


def ben(c, body=None):
    return c.post("/beneficiaries/create", body or GB_BEN)["id"]


def pay(c, bid, rid="rf-req-0000000001", amt=D("10.00"), ccy="GBP", **kw):
    return c.post_money("/transfers/create", {
        "request_id": rid, "beneficiary_id": bid, "transfer_amount": amt, "transfer_currency": ccy,
        "source_currency": ccy, "transfer_method": "LOCAL", "reason": "professional_business_services",
        "reference": "RF TEST", **kw})


def test_login_rules(fake):
    h = {"x-client-id": "c", "x-api-key": "k"}
    with httpx.Client(transport=fake.transport, base_url="https://x/api/v1") as c:
        assert c.post("/authentication/login", headers={**h, "x-login-as": "northwind"}, content=b"").status_code == 400
        assert c.post("/authentication/login", headers={**h, "x-login-as": T["kestrel"].account_id}, content=b"x").status_code == 400
        tok = c.post("/authentication/login", headers=h, content=b"").json()["token"]  # no account
        r = c.get("/account", headers={"Authorization": f"Bearer {tok}"})
        assert r.status_code == 401 and "Insufficient" in r.json()["message"]
        r = c.get("/account", headers={"Authorization": "Bearer junk"})  # P9: garbage bearer -> 401 unauthorized
        assert r.status_code == 401 and r.json()["code"] == "unauthorized"
        assert c.get("/account").status_code == 403  # P9: no auth header -> 403 html


def test_tenant_token_scoped_and_cross_tenant_401(awx):
    a = awx.for_tenant("northwind")
    assert a.get("/account")["id"] == T["northwind"].account_id
    assert awx.probe_cross_tenant("northwind", "kestrel") == (401, "credentials_invalid")
    assert awx.probe_cross_tenant("northwind", "platform") == (401, "credentials_invalid")


def test_prefunded_balances_and_own_beneficiaries(awx):
    a, b = awx.for_tenant("northwind"), awx.for_tenant("kestrel")
    bal = a.balances()
    assert bal["GBP"] == D("10000000.00") and bal.get("AUD", 0) == 0
    la, lb = a.get("/beneficiaries")["items"], b.get("/beneficiaries")["items"]
    assert len(la) == 9 and not {x["id"] for x in la} & {x["id"] for x in lb}


def test_transfer_create_duplicate_and_lookup(awx, fake):
    c = awx.for_tenant("northwind")
    bid = ben(c)
    t = pay(c, bid)
    assert t["status"] == "SCHEDULED"
    with pytest.raises(AwxError) as e:  # a different amount still hits the duplicate guard
        pay(c, bid, amt=D("99.00"))
    assert e.value.status == 400 and e.value.code == "duplicate_request_id" and e.value.details["id"] == t["id"]
    found = c.get("/transfers", {"request_id": "rf-req-0000000001"})["items"]
    assert [x["id"] for x in found] == [t["id"]]
    assert len(fake.all_transfers(T["northwind"].account_id)) == 1


def test_request_id_length(awx):
    c = awx.for_tenant("northwind")
    with pytest.raises(AwxError):
        pay(c, ben(c), rid="short")


def test_cannot_pay_another_tenants_beneficiary(awx):
    a, b = awx.for_tenant("northwind"), awx.for_tenant("kestrel")
    bid = ben(a)
    with pytest.raises(AwxError):
        pay(b, bid)


def test_debit_and_state_machine(awx):
    c = awx.for_tenant("northwind")
    t = pay(c, ben(c))
    assert c.balances()["GBP"] == D("9999990.00")
    tid = t["id"]
    for nxt in ("SENT", "PAID"):
        assert c.post(f"/simulation/transfers/{tid}/transition", {"next_status": nxt})["status"] == nxt
    r = c.post(f"/simulation/transfers/{tid}/transition",
               {"next_status": "FAILED", "failure_type": "BENEFICIARY_BANK_RETURNED"})
    assert r["failure_type"] == "INCORRECT_ROUTING" and "90802" in r["failure_reason"]
    assert c.balances()["GBP"] == D("10000000.00")  # returned money is credited back


def test_forced_overdue_500_and_bad_transition(awx):
    c = awx.for_tenant("northwind")
    tid = pay(c, ben(c))["id"]
    with pytest.raises(AwxError) as e:
        c.post(f"/simulation/transfers/{tid}/transition", {"next_status": "OVERDUE"})
    assert e.value.status == 500
    with pytest.raises(AwxError) as e:
        c.post(f"/simulation/transfers/{tid}/transition", {"next_status": "PAID"})
    assert e.value.status == 400


@pytest.mark.parametrize("mod,code", [
    (lambda b: b["beneficiary"]["bank_details"].update(account_routing_type1="SORT_CODE"), "011"),
    (lambda b: b["beneficiary"]["bank_details"].update(account_routing_value1="601613"), "010"),
])
def test_gb_validation_codes(awx, mod, code):
    import copy
    body = copy.deepcopy(GB_BEN)
    mod(body)
    with pytest.raises(AwxError) as e:
        awx.for_tenant("northwind").post("/beneficiaries/validate", body)
    assert e.value.status == 400 and f"code {code}" in e.value.message


def test_validate_payment_methods_is_001_and_us_category(awx):
    c = awx.for_tenant("kestrel")
    with pytest.raises(AwxError) as e:
        c.post("/beneficiaries/validate", {"payment_methods": ["LOCAL"], "beneficiary": {}})
    assert "code 001" in e.value.message
    us = {"transfer_methods": ["LOCAL"], "beneficiary": {"bank_details": {
        "bank_country_code": "US", "bank_account_category": "checking"}}}
    with pytest.raises(AwxError):
        c.post("/beneficiaries/validate", us)
    us["beneficiary"]["bank_details"]["bank_account_category"] = "Checking"
    assert c.post("/beneficiaries/validate", us)["valid"] is True


def test_insufficient_funds_modes(awx, fake):
    c = awx.for_tenant("northwind")
    bid = ben(c)
    with pytest.raises(AwxError) as e:  # AUD starts at 0
        pay(c, bid, ccy="AUD")
    assert e.value.code == "balance_insufficient"  # P1
    assert not fake.accounts[T["northwind"].account_id].transfers
    with pytest.raises(AwxError) as e2:  # P1: a rejected create does NOT burn the request_id
        pay(c, bid, ccy="AUD")
    assert e2.value.code == "balance_insufficient"
    fake.insufficient_funds_mode = "overdue"
    assert pay(c, bid, ccy="AUD", rid="rf-req-0000000002")["status"] == "OVERDUE"


def test_ga_needs_transfer_method(awx):
    c = awx.for_tenant("kestrel")
    base = {"request_id": "ga-req-0002", "country_code": "US", "nick_name": "K"}
    for feats in ([{"currency": "USD"}], [{"currency": "USD", "transfer_method": "ACH"}]):
        with pytest.raises(AwxError):
            c.post("/global_accounts/create", {**base, "required_features": feats})
    ga = c.post("/global_accounts/create", {**base, "required_features": [{"currency": "USD", "transfer_method": "LOCAL"}]})
    assert ga["required_features"][0]["currency"] == "USD" and "currency" not in ga


def test_global_account_deposit_and_pagination_rules(awx, fake):
    h = awx.for_tenant("harbour")
    ga = next(iter(fake.accounts[T["harbour"].account_id].gas))
    before = h.balances()["AUD"]
    d = h.post("/simulation/deposit/create", {"global_account_id": ga, "amount": D("1240.17"),
                                              "payer_name": "Harbour Foods", "reference": "RF-HAR-1234-ABCD"})
    assert d["reference"] == "RF-HAR-1234-ABCD" and h.balances()["AUD"] == before + D("1240.17")
    with pytest.raises(AwxError):
        h.get("/deposits", {"page_size": 5, "page_num": 0})
    items = h.get("/deposits", {"page_size": 10, "page_num": 0})["items"]
    assert items[0]["reference"] == "RF-HAR-1234-ABCD"
    with pytest.raises(AwxError) as e:  # settle/reverse are 404 for global-account deposits
        h.post(f"/simulation/deposits/{d['id']}/settle", {})
    assert e.value.status == 404
    with pytest.raises(AwxError):  # a tenant can't deposit into someone else's GA
        awx.for_tenant("kestrel").post("/simulation/deposit/create", {"global_account_id": ga, "amount": D(1)})


def test_fx_quote_convert_and_duplicate(awx):
    c = awx.for_tenant("northwind")
    q = c.post("/fx/quotes/create", {"buy_currency": "AUD", "sell_currency": "GBP",
                                     "buy_amount": D("1000.00"), "validity": "MIN_1"})
    assert q["usage"] == "MULTI_USE"  # P5: live quotes are multi-use
    body = {"request_id": "fx-test-0001", "buy_currency": "AUD", "sell_currency": "GBP",
            "buy_amount": D("1000.00"), "quote_id": q["quote_id"]}
    conv = c.post("/fx/conversions/create", body)
    assert conv["status"] == "SETTLED" and "conversion_id" in conv and c.balances()["AUD"] == D("1000.00")
    with pytest.raises(AwxError) as e:  # same request_id never converts twice
        c.post("/fx/conversions/create", body)
    assert e.value.code == "duplicate_request_id"
    assert c.balances()["AUD"] == D("1000.00")


def test_timeout_after_commit_creates_exactly_one(awx, fake):
    from ringfence.awx import AwxTimeout
    c = awx.for_tenant("northwind")
    bid = ben(c)
    fake.inject("timeout_after_commit")
    with pytest.raises(AwxTimeout):
        pay(c, bid)
    assert len(fake.all_transfers(T["northwind"].account_id)) == 1


def test_error_before_commit_has_no_side_effect(awx, fake):
    c = awx.for_tenant("northwind")
    bid = ben(c)
    fake.inject("error_before_commit", status=503)
    with pytest.raises(AwxError) as e:
        pay(c, bid)
    assert e.value.status == 503 and not fake.all_transfers(T["northwind"].account_id)


def test_webhook_signing_and_duplicate(fake):
    seen = []
    fake.webhook({"id": "e1"}, lambda h, raw: seen.append((h, raw)), duplicate=True)
    assert len(seen) == 2
    h, raw = seen[0]
    assert h["x-signature"] == fake.sign_webhook(h["x-timestamp"], raw)
    bad = []
    fake.webhook({"id": "e1"}, lambda h, raw: bad.append(h), bad_signature=True)
    assert bad[0]["x-signature"] != fake.sign_webhook(bad[0]["x-timestamp"], raw)
