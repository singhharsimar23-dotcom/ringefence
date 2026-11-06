from copy import deepcopy
from datetime import date
from decimal import Decimal as D

import pytest
from helpers import acct, sim

from ringfence import beneficiaries as ben
from ringfence import shadow, store, verify
from ringfence.ledger import Ledger
from ringfence.orchestrator import Orchestrator, Refused
from ringfence.setup_demo import setup

PAY = date(2026, 11, 14)
NEW_BANK = {"country": "GB", "bank_name": "Barclays", "routing_type": "sort_code", "routing_value": "200000",
            "account_number": "99999901"}


@pytest.fixture
def orch(awx, L, tmp_path, monkeypatch):
    monkeypatch.setattr("ringfence.orchestrator.ROOT", tmp_path)  # reset() moves artifacts/certs under ROOT
    setup(awx)
    o = Orchestrator(awx, L)
    o.ex._sleep = lambda s: None
    return o


def role(L, t):
    return store.latest_mandate(L, t).mandate.approver_role


def test_bank_change_is_quarantined_and_does_not_touch_the_run(orch, L):
    rid = orch.create_run("northwind", PAY)
    old = store.get_line(L, rid, "northwind", "ada")["beneficiary_id"]
    q = orch.propose_bank_change(rid, "northwind", "ada", NEW_BANK, "email-1", "maya")
    assert q["valid"]
    assert store.get_line(L, rid, "northwind", "ada")["beneficiary_id"] == old
    assert store.get_run(L, rid, "northwind")["beneficiary_editors"] == ["maya"]
    assert orch.diff(rid, "northwind")["bank_changes"][0]["last4"] == "9901"
    assert orch.propose_bank_change(rid, "northwind", "ada", NEW_BANK, "email-1", "maya")["id"] == q["id"]  # idempotent


def test_callback_needs_a_different_person_and_a_reference_then_voids_the_old_approval(orch, fake, L):
    rid = orch.create_run("northwind", PAY)
    orch.submit(rid, "northwind")
    r = role(L, "northwind")
    orch.approve(rid, "northwind", "priya", r)
    q = orch.propose_bank_change(rid, "northwind", "ada", NEW_BANK, "email-1", "maya")
    with pytest.raises(PermissionError):
        orch.confirm_bank_change("northwind", q["id"], "maya", r, "call-4411")  # the requester cannot confirm
    with pytest.raises(PermissionError):
        orch.confirm_bank_change("northwind", q["id"], "priya", "viewer", "call-4411")  # wrong role
    with pytest.raises(ValueError):
        orch.confirm_bank_change("northwind", q["id"], "priya", r, "x")  # no callback reference
    new_id = orch.confirm_bank_change("northwind", q["id"], "priya", r, "call-4411")
    assert store.get_line(L, rid, "northwind", "ada")["beneficiary_id"] == new_id
    run = store.get_run(L, rid, "northwind")
    assert run["state"] == "AWAITING_APPROVAL"  # approval was over the old batch hash
    assert {ln["state"] for ln in store.get_lines(L, rid, "northwind")} == {"PLANNED"}
    assert orch.advance(rid, "northwind") == "AWAITING_APPROVAL"
    assert fake.accounts[acct("northwind")].transfers == {}
    orch.approve(rid, "northwind", "priya", r)
    assert orch.advance(rid, "northwind") == "RELEASED"
    t = [x for x in fake.accounts[acct("northwind")].transfers.values()
         if x["beneficiary"]["bank_details"].get("account_number") == NEW_BANK["account_number"]]  # sent inline: no id on it
    assert len(t) == 1


def test_account_in_someone_elses_name_cannot_be_confirmed_even_after_a_callback(orch, fake, L):
    rid = orch.create_run("northwind", PAY)
    old = store.get_line(L, rid, "northwind", "ada")["beneficiary_id"]
    assert orch.propose_bank_change(rid, "northwind", "ada", NEW_BANK, "email-0", "maya")["name_match"] == "FULL_MATCH"
    fake.holders["99999901"] = "Mallory Mule"  # the bank's record: this account belongs to someone else
    q = orch.propose_bank_change(rid, "northwind", "ada", NEW_BANK, "email-1", "maya")
    assert q["name_match"] == "NOT_MATCHED"
    with pytest.raises(ValueError, match="not in the contractor's name"):
        orch.confirm_bank_change("northwind", q["id"], "priya", role(L, "northwind"), "call-4411")
    assert store.get_line(L, rid, "northwind", "ada")["beneficiary_id"] == old  # the old details stay in force


def repoint(awx, tenant, bid):
    """What an employer's phished web login (or anyone with beneficiary:write) can do: same id, a mule's account."""
    c = awx.for_tenant(tenant)
    b = deepcopy(c.get(f"/beneficiaries/{bid}")["beneficiary"])
    bd = b["bank_details"]
    bd.update(iban="DE89370400440532013000") if "iban" in bd else bd.update(account_number="99999901")
    c.post(f"/beneficiaries/{bid}/update", {"transfer_methods": ["LOCAL"], "beneficiary": b})


def test_payee_repointed_in_place_on_airwallex_holds_the_run(orch, fake, L):
    rid = orch.create_run("kestrel", PAY)
    assert orch.submit(rid, "kestrel") == "READY"
    ln = store.get_lines(L, rid, "kestrel")[0]
    repoint(orch.awx, "kestrel", ln["beneficiary_id"])  # the id still matches the registry: the gate alone would pay it
    assert orch.advance(rid, "kestrel") == "HELD"
    assert fake.accounts[acct("kestrel")].transfers == {}
    assert any(e["payload"]["lines"][0]["contractor_id"] == ln["contractor_id"] for e in L.entries(kind="ALERT"))
    assert orch.resume(rid, "kestrel") == "READY" and orch.advance(rid, "kestrel") == "HELD"  # resuming does not wash it


def test_a_repoint_after_the_release_check_cannot_redirect_a_transfer_sent_with_inline_details(orch, fake, L, monkeypatch):
    rid = orch.create_run("kestrel", PAY)
    orch.submit(rid, "kestrel")
    monkeypatch.setattr(ben, "drifted", lambda *a: [])  # the edit lands between the release check and the create
    ln = store.get_lines(L, rid, "kestrel")[0]
    repoint(orch.awx, "kestrel", ln["beneficiary_id"])
    assert orch.advance(rid, "kestrel") == "RELEASED"
    pin = ben.load_registry()["tenants"]["kestrel"]["pins"][ln["beneficiary_id"]]
    t = next(x for x in fake.accounts[acct("kestrel")].transfers.values() if x["request_id"] == ln["request_id"])
    assert t["beneficiary"]["bank_details"].get("account_number") != "99999901"
    assert ben.dest_fp(t["beneficiary"]) == pin and t["status"] != "CANCELLED"  # it went to the pinned account
    assert not [e for e in L.entries(kind="ALERT") if e["payload"].get("what") == "PAID_TO_UNAPPROVED_ACCOUNT"]
    assert verify.report(orch.awx, L)["tenants"]["kestrel"]["ok"]


def test_a_repoint_that_wins_the_race_still_fails_the_proof_on_a_registry_without_inline_payees(orch, L, monkeypatch):
    reg = ben.load_registry()
    reg["tenants"]["kestrel"].pop("payees")  # a registry from before inline sends: the id is sent, the recall is the backstop
    ben.save_registry(reg)
    rid = orch.create_run("kestrel", PAY)
    orch.submit(rid, "kestrel")
    monkeypatch.setattr(ben, "drifted", lambda *a: [])  # the edit lands between the release check and the create
    repoint(orch.awx, "kestrel", store.get_lines(L, rid, "kestrel")[0]["beneficiary_id"])
    assert orch.advance(rid, "kestrel") == "RELEASED"
    a = L.entries(kind="ALERT")[-1]["payload"]  # the transfer's own snapshot shows the repoint: recalled before it is SENT
    assert a["what"] == "PAID_TO_UNAPPROVED_ACCOUNT" and a["cancelled"]
    assert orch.awx.for_tenant("kestrel").get(f"/transfers/{a['transfer_id']}")["status"] == "CANCELLED"
    rep = verify.report(orch.awx, L)
    chk = next(c for c in rep["tenants"]["kestrel"]["checks"] if "human approved" in c["name"])
    assert not chk["ok"] and not rep["tenants"]["kestrel"]["ok"] and rep["tenants"]["northwind"]["ok"]


def test_a_lost_database_does_not_pay_payroll_twice(orch, awx, fake, tmp_path):
    rid = orch.create_run("kestrel", PAY)
    orch.submit(rid, "kestrel")
    assert orch.advance(rid, "kestrel") == "RELEASED"
    paid = len(fake.accounts[acct("kestrel")].transfers)
    o2 = Orchestrator(awx, Ledger(tmp_path / "fresh-disk.db"))  # the VM died; a new one starts with an empty ledger
    rid2 = o2.create_run("kestrel", PAY)
    assert rid2 == rid  # same obligation, same id, same request_ids
    o2.submit(rid2, "kestrel")
    assert o2.advance(rid2, "kestrel") == "HELD"
    assert len(fake.accounts[acct("kestrel")].transfers) == paid
    assert o2.L.entries(kind="ALERT")[-1]["payload"]["what"] == "ALREADY_PAID_ON_AIRWALLEX"


def test_the_pin_covers_every_routing_field_and_matches_what_airwallex_stores(orch, fake):
    bd = {"bank_country_code": "GB", "account_routing_type1": "sort_code", "account_routing_value1": "041907",
          "account_number": "07371376", "account_currency": "GBP"}
    for k, v in (("account_routing_value1", "200000"), ("account_routing_type1", "aba"), ("swift_code", "BARCGB22"),
                 ("account_currency", "EUR"), ("account_routing_value2", "x")):
        assert ben.fingerprint({**bd, k: v}) != ben.fingerprint(bd), k
    reg = ben.load_registry()["tenants"]["northwind"]  # Lukas: a LOCAL IBAN payee, whose swift_code Airwallex drops
    c = orch.awx.for_tenant("northwind")
    assert all(ben.fingerprint(c.get(f"/beneficiaries/{b}")["beneficiary"]["bank_details"]) == p for b, p in reg["pins"].items())


def test_the_fee_payee_moved_to_another_bank_under_the_same_account_number_is_not_paid(orch, fake, L):
    fbid = ben.load_registry()["tenants"]["kestrel"]["fee_beneficiary"]
    c = orch.awx.for_tenant("kestrel")
    b = deepcopy(c.get(f"/beneficiaries/{fbid}")["beneficiary"])
    b["bank_details"]["account_routing_value1"] = "200000"  # the platform's account number, someone else's bank
    c.post(f"/beneficiaries/{fbid}/update", {"transfer_methods": ["LOCAL"], "beneficiary": b})
    rid = orch.create_run("kestrel", PAY)
    orch.submit(rid, "kestrel")
    assert orch.advance(rid, "kestrel") == "RELEASED"  # payroll is not held: only the fee payee moved
    for t in list(fake.accounts[acct("kestrel")].transfers.values()):
        sim(orch.awx, "kestrel", t["id"], "SENT")
        sim(orch.awx, "kestrel", t["id"], "PAID")
    orch.poll()
    orch.poll()
    assert not L.entries(kind="FEE_CHARGED")
    assert L.entries(kind="GATE_DENY")[-1]["payload"]["code"] == "fee_beneficiary_changed"
    assert all(t.get("beneficiary_id") != fbid for t in fake.accounts[acct("kestrel")].transfers.values())


def test_rate_request_is_recorded_flagged_and_never_applied(orch, L):
    rid = orch.create_run("northwind", PAY)
    before = store.get_line(L, rid, "northwind", "ada")["amount"]
    req = orch.note_rate_request(rid, "northwind", "ada", D(300), "email-2", "pay me 3x")
    assert req["over_25pct"]
    assert store.get_line(L, rid, "northwind", "ada")["amount"] == before
    assert orch.diff(rid, "northwind")["rate_requests"][0]["new_rate"] == "300"


def test_hold_blocks_release_and_resume_goes_back_through_the_gate(orch, fake, L):
    rid = orch.create_run("kestrel", PAY)
    assert orch.submit(rid, "kestrel") == "READY"
    orch.hold(rid, "kestrel", "operator_hold", "checking")
    assert orch.advance(rid, "kestrel") == "HELD"
    assert fake.accounts[acct("kestrel")].transfers == {}
    assert orch.resume(rid, "kestrel") == "READY"
    assert orch.advance(rid, "kestrel") == "RELEASED"
    with pytest.raises(Refused):
        orch.hold(rid, "kestrel", "too_late")


def test_kill_switch_stops_release_and_clearing_it_allows_it(orch, fake, L):
    rid = orch.create_run("kestrel", PAY)
    orch.submit(rid, "kestrel")
    orch.set_kill_switch(True, "maya")
    assert orch.advance(rid, "kestrel") == "HELD"  # the gate holds the run; it does not silently retry
    assert fake.accounts[acct("kestrel")].transfers == {}
    orch.set_kill_switch(False, "maya")
    assert orch.resume(rid, "kestrel") == "READY"
    assert orch.advance(rid, "kestrel") == "RELEASED"


def test_diff_shows_changes_totals_and_shortfall(orch, L):
    rid = orch.create_run("harbour", PAY)
    orch.submit(rid, "harbour")
    d = orch.diff(rid, "harbour")
    assert d["totals"] == {"AUD": "1240.17"} and d["shortfall"] == {"AUD": "1240.17"}
    assert d["approver_role"] == role(L, "harbour")
    n = orch.diff(orch.create_run("northwind", PAY), "northwind")
    assert n["unchanged"]["count"] + len(n["changes"]) == 3


def test_reset_archives_starts_clean_and_keeps_the_archive_chain(orch, L, tmp_path):
    rid = orch.create_run("kestrel", PAY)
    orch.submit(rid, "kestrel")
    old_epoch = L.epoch()
    orch.reset("maya")
    assert L.epoch() != old_epoch or L.entries(kind="RESET")
    assert orch.runs() == []
    assert L.verify().ok
    assert list(L.entries(kind="RESET"))
    assert orch.create_run("kestrel", PAY)  # same pay date works again


def test_shadow_total_pools_every_tenant_for_display_only(awx):
    setup(awx)
    total, complete = shadow.naive_total(awx, "AUD")
    assert total > D(1000000) and complete


def test_shadow_total_never_quotes_an_empty_currency(awx, fake, monkeypatch):
    setup(awx)
    fake.accounts[acct("northwind")].balances["JPY"] = D("0.00")  # live accounts list ~40 currencies, most at zero
    asked = []
    real = shadow.get_quote
    monkeypatch.setattr(shadow, "get_quote", lambda c, sell, buy, **k: asked.append(sell) or real(c, sell, buy, **k))
    total, complete = shadow.naive_total(awx, "AUD")
    assert "JPY" not in asked and complete and total > D(1000000)


def test_a_payee_airwallex_answers_with_an_empty_200_holds_the_run_by_name(orch, fake, L):
    # live 6 Nov: GET /beneficiaries/{id} for a deleted (or another employer's) id is 200 with an empty body
    rid = orch.create_run("kestrel", PAY)
    assert orch.submit(rid, "kestrel") == "READY"
    del fake.accounts[acct("kestrel")].beneficiaries[store.get_lines(L, rid, "kestrel")[0]["beneficiary_id"]]
    assert orch.advance(rid, "kestrel") == "HELD"
    assert fake.accounts[acct("kestrel")].transfers == {}


def test_proof_sees_every_transfer_when_airwallex_ignores_page_num(awx, fake):
    a = fake.accounts[acct("kestrel")]
    for i in range(250):
        a.transfers[f"t{i}"] = {"id": f"t{i}", "request_id": f"r{i}", "created_at": "2026-11-06T00:00:00+00:00"}
    fake._view = lambda acc, t: dict(t)
    got = verify._transfers(awx.for_tenant("kestrel"), "2026-11-01T00:00:00+0000")
    assert len(got) == 250 == len({t["id"] for t in got})

def test_proof_fails_rather_than_certify_a_stalled_transfer_cursor():
    class Stalled:  # page 0 has one transfer; every later page repeats the cursor and adds nothing
        def get(self, path, params):
            return {"items": [{"id": "t0"}] if params["page"] == "0" else [], "page_after": "same"}
    with pytest.raises(RuntimeError, match="stalled"):
        verify._transfers(Stalled(), "2026-11-01T00:00:00Z")

def test_a_payee_that_became_a_wallet_holds_the_run_instead_of_skipping_the_check(orch, fake, L):
    # Airwallex Pay (DIGITAL_WALLET) records carry digital_wallet and no bank_details; that used to skip or crash the check
    rid = orch.create_run("kestrel", PAY)
    assert orch.submit(rid, "kestrel") == "READY"
    bid = store.get_lines(L, rid, "kestrel")[0]["beneficiary_id"]
    rec = fake.accounts[acct("kestrel")].beneficiaries[bid]["beneficiary"]
    rec.pop("bank_details")
    rec["digital_wallet"] = {"account_name": "Sandbox Business", "account_number": "12345678"}
    assert orch.advance(rid, "kestrel") == "HELD"
    assert fake.accounts[acct("kestrel")].transfers == {}


def test_a_wallet_or_bare_snapshot_never_matches_a_bank_pin():
    pin = ben.fingerprint({"account_number": "1"})
    assert ben.dest_fp({"bank_details": {"account_number": "1"}}) == pin
    assert ben.dest_fp({"digital_wallet": {"account_number": "1"}}) != pin
    assert ben.dest_fp({}) == "unknown" != pin
