from decimal import Decimal as D

from helpers import acct

from ringfence import beneficiaries as ben
from ringfence import seed
from ringfence.config import tenants
from ringfence.mandate import mandate_sig_valid
from ringfence.money import price_line, price_run
from ringfence.setup_demo import setup

T = tenants(fake=True)


def test_setup_is_idempotent_and_isolated(awx, fake):
    r1 = setup(awx)
    n_before = {t: len(a.beneficiaries) for t, a in fake.accounts.items()}
    r2 = setup(awx)
    assert r1["tenants"].keys() == {"northwind", "kestrel", "harbour"}
    for t in r1["tenants"]:
        assert r1["tenants"][t]["beneficiaries"] == r2["tenants"][t]["beneficiaries"]
        assert r1["tenants"][t]["fee_beneficiary"] == r2["tenants"][t]["fee_beneficiary"]
    assert n_before == {t: len(a.beneficiaries) for t, a in fake.accounts.items()}  # nothing duplicated
    ids = [i for t in r1["tenants"].values() for i in (*t["beneficiaries"].values(), t["fee_beneficiary"])]
    assert len(ids) == len(set(ids)) == 3 + 2 + 3 + 3  # contractors + one fee beneficiary per tenant
    assert ben.resolve(ben.load_registry(), "harbour", "ivy") == r1["tenants"]["harbour"]["beneficiaries"]["ivy"]
    assert ben.resolve(ben.load_registry(), "harbour", "noah") is None  # another tenant's contractor


def test_ga_created_and_every_tenants_own_accounts_are_known(awx):
    reg = setup(awx)
    assert any(g["currency"] == "USD" and g["routing_type"] for g in reg["tenants"]["kestrel"]["gas"])
    keys = ben.all_ga_keys(reg)
    harbour_aud = next(g for g in reg["tenants"]["harbour"]["gas"] if g["currency"] == "AUD")
    assert harbour_aud["account_number"] in keys and harbour_aud["routing_type"] == "bsb"
    assert "07371376" not in keys  # the platform fee account is not an employer account


def test_drain_zeroes_aud_inside_own_account(awx, fake):
    c = awx.for_tenant("harbour")
    assert c.balances()["AUD"] == D("3000.00")
    kestrel_before = awx.for_tenant("kestrel").balances()
    reg = setup(awx)
    assert c.balances().get("AUD", D(0)) == 0 and reg["tenants"]["harbour"]["drained_aud"] == "3000.00"
    assert awx.for_tenant("kestrel").balances() == kestrel_before  # other tenants untouched
    assert setup(awx)["tenants"]["harbour"]["drained_aud"] == "0"  # re-run is a no-op


def test_harbour_headline_shortfall():
    cs = seed.contractors("harbour")
    hours = {"ivy": D(20), "omar": D("12.5"), "ruth": D("1.5")}
    lines = [price_line(cs[k], h) for k, h in hours.items()]
    assert [ln.amount for ln in lines] == [D("700.00"), D("480.00"), D("60.17")]
    p = price_run(lines, {"AUD": D(0), "GBP": D(10000000)})
    assert p.shortfall["AUD"] == D("1240.17")


def test_default_mandates_signed_and_scoped():
    ms = seed.default_mandates()
    assert all(mandate_sig_valid(m) for m in ms.values())
    h = ms["harbour"].mandate
    assert h.currencies == ("AUD",) and h.funding_currencies == ("AUD",) and h.fx == "never"
    assert h.allowed_contractor_ids == ("ivy", "omar", "ruth")
    assert ms["kestrel"].mandate.auto_release == "if_no_diff" and ms["northwind"].mandate.fx == "within_band"


def test_two_resets_in_the_same_second_do_not_reuse_a_conversion_id(awx, fake, monkeypatch):
    monkeypatch.setattr("time.time", lambda: 1_700_000_000.0)  # the clock stands still
    c = awx.for_tenant("harbour")
    setup(awx)
    fake.accounts[acct("harbour")].balances["AUD"] = D("500.00")  # a top-up lands between two resets
    assert setup(awx)["tenants"]["harbour"]["drained_aud"] == "500.00" and c.balances().get("AUD", D(0)) == 0
