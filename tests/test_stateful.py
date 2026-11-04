"""Hostile sequences: Hypothesis picks the order of events, the money invariants must hold after every step.
CI runs 25 sequences; scripts/gauntlet.py runs 500 and records the step count."""
import itertools
import os
import shutil
import tempfile
from pathlib import Path

from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule, run_state_machine_as_test
from invariants import assert_invariants

from ringfence import store
from ringfence.agent import loop
from ringfence.awx import Awx
from ringfence.config import tenants
from ringfence.fake_awx import FakeAirwallex
from ringfence.ledger import Ledger
from ringfence.orchestrator import Orchestrator, Refused
from ringfence.scenarios import Simulator
from ringfence.setup_demo import setup

STEPS = {"n": 0}  # every rule that ran, for the Gauntlet's record
TENANT = st.sampled_from(["northwind", "kestrel", "harbour"])
_ids = itertools.count()


class Sequences(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self._old = os.environ.get("RF_VAR")
        base = Path(self._old or tempfile.mkdtemp())
        self._var = base / f"seq{next(_ids)}"
        self._var.mkdir(parents=True, exist_ok=True)
        os.environ["RF_VAR"] = str(self._var)
        os.environ.setdefault("RF_MANDATE_KEY", "test-mandate-key")
        os.environ.setdefault("RF_APPROVAL_KEY", "test-approval-key")
        ts = tenants(fake=True)
        self.fake = FakeAirwallex({k: t.account_id for k, t in ts.items()})
        awx = Awx(transport=self.fake.transport, tenant_map=ts, sleep=lambda s: None)
        self.L = Ledger()
        setup(awx)
        self.o = Orchestrator(awx, self.L, cert_dir=self._var / "certs")  # a reset must never move the repo's own certificates
        self.o.ex._sleep = lambda s: None
        self.sim = Simulator(self.o, lambda: self.o.run_id(loop.pay_date()), lambda t: loop.run_tick(self.o, t, mode="scripted"))

    def teardown(self):
        if self._old is None:
            os.environ.pop("RF_VAR", None)
        else:
            os.environ["RF_VAR"] = self._old
        shutil.rmtree(self._var, ignore_errors=True)

    def _rid(self):
        return self.o.run_id(loop.pay_date())

    @invariant()
    def money_invariants_hold(self):
        assert_invariants(self.L, self.fake)

    @rule(t=TENANT)
    def advance(self, t):
        STEPS["n"] += 1
        if store.get_run(self.L, self._rid(), t) is None:
            loop.run_tick(self.o, t, mode="scripted")
        else:
            self.o.advance(self._rid(), t)

    @rule(t=TENANT)
    def approve(self, t):
        STEPS["n"] += 1
        try:
            self.o.approve(self._rid(), t, "gauntlet", store.latest_mandate(self.L, t).mandate.approver_role)
        except (Refused, AttributeError):
            pass

    @rule()
    def top_up(self):
        STEPS["n"] += 1
        self.sim.run("harbour_topup", "harbour")

    @rule()
    def late_return(self):
        STEPS["n"] += 1
        self.sim.run("late_return")

    @rule(t=st.sampled_from(["northwind", "kestrel", "harbour"]))
    def bank_change_email(self, t):
        STEPS["n"] += 1
        self.sim.run("bank_change_email", t)

    @rule()
    def double_click(self):
        STEPS["n"] += 1
        self.sim.run("double_click", "northwind")

    @rule()
    def rate_move(self):
        STEPS["n"] += 1
        self.sim.run("rate_move")

    @rule()
    def tamper_and_restore(self):
        STEPS["n"] += 1
        if self.sim.run("tamper_ledger").get("ok"):
            self.sim.restore()  # a second press repairs; the invariants need an intact chain

    @rule()
    def reset(self):
        STEPS["n"] += 1
        self.o.reset("gauntlet")
        for a in self.fake.accounts.values():  # Airwallex keeps old payments; the fake's checks are per take
            a.transfers.clear()
        self.sim.reset()


def run_sequences(max_examples: int, step_count: int = 12) -> None:
    run_state_machine_as_test(Sequences, settings=settings(
        max_examples=max_examples, stateful_step_count=step_count, deadline=None, database=None,
        suppress_health_check=list(HealthCheck)))


def test_hostile_sequences_never_break_a_money_invariant():
    run_sequences(25)
