"""Test scaffolding: a ready-to-release run for one tenant, built the way the orchestrator will build it."""
from datetime import timedelta
from decimal import Decimal as D

from ringfence import beneficiaries as ben
from ringfence import seed, store
from ringfence.config import clock, tenants
from ringfence.executor import current_batch_hash
from ringfence.mandate import Approval, make_request_id, sign_approval
from ringfence.money import price_line
from ringfence.setup_demo import setup

RUN = "20261114-tst001"
HOURS = {
    "kestrel": {"noah": D(10), "zoe": D(8)},
    "northwind": {"ada": D(10), "lukas": D(8), "mia": D(5)},
    "harbour": {"ivy": D(20), "omar": D("12.5"), "ruth": D("1.5")},
}


def acct(tenant: str) -> str:
    return tenants(fake=True)[tenant].account_id


def new_run(awx, L, tenant, hours=None, *, approve=None, run_id=RUN, fx_rate=None, state="READY"):
    """Writes run + lines (+ a signed approval unless the tenant auto-releases). Kestrel auto-releases."""
    reg = ben.load_registry()
    if not reg["tenants"]:
        reg = setup(awx)
    with L.tx() as tx:
        for m in seed.default_mandates().values():
            if store.latest_mandate(tx, m.mandate.tenant) is None:
                store.save_mandate(tx, m)
    auto = tenant == "kestrel"
    cs = seed.contractors(tenant)
    with L.tx() as tx:
        store.put_run(tx, run_id, tenant, state, 1, diff_empty=auto, any_new_or_changed=not auto)
        for cid, h in (hours or HOURS[tenant]).items():
            ln = price_line(cs[cid], h)
            store.put_line(tx, run_id, tenant, cid, "READY" if state == "READY" else "PLANNED", 1, 1,
                           make_request_id(run_id, tenant, cid, 1),
                           beneficiary_id=reg["tenants"][tenant]["beneficiaries"][cid], amount=str(ln.amount),
                           currency=ln.currency, method=ln.method, hours=str(h))
    if approve is None:
        approve = not auto
    if approve:
        now = clock.utc_now()
        a = Approval(run_id, tenant, 1, current_batch_hash(L, run_id, tenant, 1), "approver",
                     store.latest_mandate(L, tenant).mandate.approver_role, now, now + timedelta(hours=2), fx_rate)
        with L.tx() as tx:
            store.save_approval(tx, sign_approval(a))
    return run_id


def sim(awx, tenant, tid, status, **kw):
    return awx.for_tenant(tenant).post(f"/simulation/transfers/{tid}/transition", {"next_status": status, **kw})


class FakeLLM:
    """Scripted tool_use turns. Each turn is a list of (tool, input); a turn may also be an Exception to raise,
    or a string stop_reason ("refusal", "max_tokens") with no content."""

    errors = (ConnectionError,)

    def __init__(self, turns):
        self.turns, self.seen = list(turns), []

    def create(self, system, tools, messages):
        from types import SimpleNamespace as NS
        self.seen.append(messages[-1])
        t = self.turns.pop(0) if self.turns else []
        if isinstance(t, Exception):
            raise t
        if isinstance(t, str):
            return NS(stop_reason=t, content=[])
        blocks = [NS(type="tool_use", id=f"tu{len(self.seen)}_{i}", name=n, input=a) for i, (n, a) in enumerate(t)]
        return NS(stop_reason="tool_use" if blocks else "end_turn", content=blocks)
