"""The attack lab. The attacker is the Ringfence server itself, fully compromised: it holds every pull key it was given and
can run any command, but it has no owner key. Each attack is run against the setup a team would normally build (one broad
mandate for the whole batch, "naive") and against Ringfence (one single-use mandate per approved line).

Attacks 6 and 7 are bugs we found in our OWN first design of per-line mandates. Their "before" side is that first design
(the device does not revoke earlier credentials), their "after" side is the shipped fix. Every cell is either a payment
the chain made or a refusal the chain recorded, with the transaction hash when the CLI printed one.

The lab takes a runner with the metal.run_cli signature, so the same code runs on the live testnet and on tests/fake_chain."""
from __future__ import annotations

import os
import shutil
import tempfile
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path

from . import metal
from .alta_device import Device
from .mandate import LineSpec, batch_hash, make_request_id

NAIVE, SAFE, BEFORE, AFTER = "broad mandate", "Ringfence", "before the fix", "after the fix"
ATTACKS = {
    1: ("approval swap", "pay line A's money to the attacker's wallet", "Bybit, Feb 2025: signers approved what they could not read"),
    2: ("address poisoning", "pay a wallet that looks like A's (same first 6 and last 4)", "address-poisoning losses, every year"),
    3: ("inflated amount", "pay A more than the approved line", "Lobstar Wilde, Feb 2026: an agent sent far more than meant"),
    4: ("double pull", "pull A's line a second time with a new payment id from a fresh machine", "Alta's own docs: dedup is local to one disk"),
    5: ("server binds its own mandate", "mint and bind a mandate for the employer's principal without the owner key", "AIXBT, Mar 2025: operator access abused"),
    6: ("stale attempt", "a line is reopened as attempt 2, then the server pays attempt 1 as well", "found by us, in our first design"),
    7: ("stale approval", "the batch is re-approved, then the server pays the line under the OLD approval", "found by us, in our first design"),
}


def _addr(n: int) -> str:
    return "0x" + format(n, "x").rjust(40, "0")


class Lab:
    def __init__(self, runner: Callable, owner_key: Path, principal: str, work: Path, *, wallets: dict[str, str], mule: str,
                 recorder_key: Path | None = None, attacker_key: Path | None = None, amounts: dict[str, Decimal] | None = None, usd_per_usdz: Decimal = Decimal(10)):
        self.run, self.owner, self.principal, self.work = runner, str(owner_key), principal, work
        self.wallets, self.mule, self.recorder = wallets, mule, str(recorder_key or owner_key)
        self.usdz = amounts or {"noah": Decimal("5.50"), "zoe": Decimal("5.00")}
        self.k, self.rows, self.usd_per_usdz, self.attacker = 0, [], usd_per_usdz, attacker_key
        self.on_row: Callable | None = None

    # -- plumbing -----------------------------------------------------------------------------------
    def cli(self, args: list[str], cwd: Path) -> tuple[int, dict]:
        cwd.mkdir(parents=True, exist_ok=True)
        try:
            rc, text = self.run([*args, *metal.NET], cwd)
        except metal.MetalError as e:
            return -1, {"error": str(e)}
        return rc, metal.parse(text)

    def fresh(self, tag: str) -> Path:
        self.k += 1
        return self.work / f"{self.k:02d}-{tag}"

    def mint(self, tag: str, payee: str | None, cap: Decimal, budget: Decimal, occ: int | None, desc: str = "") -> Path:
        d = self.fresh(tag)
        a = ["mandate", "credential", "create", "--principal", self.principal, "--cap", str(cap), "--budget", str(budget),
             "--expires-in", "3600", "--key", self.owner, "--out", "m.json", "--description", desc or f"lab {tag}"]
        if payee:
            a += ["--payee", payee]
        if occ:
            a += ["--max-occurrences", str(occ)]
        rc, f = self.cli(a, d)
        if rc == 0:
            rc, f = self.cli(["mandate", "bind", "--credential", "m.json", "--key", self.owner], d)
        if rc != 0:
            raise RuntimeError(f"lab setup failed ({tag}): {f.get('error') or f.get('reason')}")
        return d

    def pull(self, d: Path, to: str, amount: Decimal, pid: str, fresh_home: bool = False) -> dict:
        a = ["mandate", "pull", "--credential", "m.json", "--to", to, "--amount", str(amount), "--payment-id", pid,
             "--record-refusal", "--key", self.recorder]
        with _home(fresh_home):
            rc, f = self.cli(a, d)
        paid = rc == 0 and str(f.get("outcome", "")).startswith("paid")
        return {"outcome": "paid" if paid else "refused", "reason": "" if paid else (f.get("reason") or f.get("error") or "")[:90],
                "tx": f.get("transaction", ""), "to": to, "usdz": str(amount) if paid else "0"}

    def cell(self, n: int, side: str, **r) -> dict:
        row = {"attack": n, "name": ATTACKS[n][0], "side": side, "usd_lost": str(Decimal(r.get("usdz", "0")) * self.usd_per_usdz), **r}
        self.rows.append(row)
        if self.on_row:
            self.on_row(row)
        return row

    # -- the lines every attack protects ------------------------------------------------------------
    def broad(self, tag: str) -> Path:
        """What a team builds first: any payee, budget = the whole batch, cap = the biggest line, no limit on pulls."""
        return self.mint(tag + "-broad", None, max(self.usdz.values()), sum(self.usdz.values()), None)

    def line(self, tag: str, cid: str = "noah") -> Path:
        z = self.usdz[cid]
        return self.mint(f"{tag}-{cid}", self.wallets[cid], z, z, 1)

    # -- attacks 1 to 5: Ringfence against a broad mandate ------------------------------------------
    def a1_swap(self):
        a = self.wallets["noah"]
        self.cell(1, NAIVE, **self.pull(self.broad("a1"), self.mule, self.usdz["noah"], "a1-n"), note="paid the attacker")
        self.cell(1, SAFE, **self.pull(self.line("a1"), self.mule, self.usdz["noah"], "a1-s"), note=f"line pays only {a[:8]}…")

    def a2_poison(self):
        fake = metal.lookalike(self.wallets["noah"])
        assert metal.looks_like(fake, self.wallets["noah"])
        self.cell(2, NAIVE, **self.pull(self.broad("a2"), fake, self.usdz["noah"], "a2-n"))
        self.cell(2, SAFE, **self.pull(self.line("a2"), fake, self.usdz["noah"], "a2-s"))

    def a3_inflate(self):
        big = self.usdz["zoe"] + Decimal("0.50")  # zoe's line is the smaller; the broad cap is noah's line
        z = self.wallets["zoe"]
        self.cell(3, NAIVE, **self.pull(self.broad("a3"), z, max(self.usdz.values()), "a3-n"), note=f"{self.usdz['zoe']} was approved")
        self.cell(3, SAFE, **self.pull(self.line("a3", "zoe"), z, big, "a3-s"), note=f"{self.usdz['zoe']} was approved")

    def a4_double(self):
        a, amt = self.wallets["noah"], self.usdz["noah"]
        for side, d in ((NAIVE, self.broad("a4")), (SAFE, self.line("a4"))):
            first = self.pull(d, a, amt, "a4-1")  # the legitimate payment
            left = sum(self.usdz.values()) - amt  # what a broad mandate still has to give
            second = self.pull(d, a, left if side == NAIVE else amt, "a4-2", fresh_home=True)
            self.cell(4, side, **second, note="first pull: " + first["outcome"])

    def a5_own_mandate(self):
        """The attacker writes a mandate for the employer's principal with a key of its own, then tries to bind it."""
        for side, owner in ((NAIVE, self.owner), (SAFE, None)):
            d = self.fresh("a5-" + ("naive" if owner else "safe"))
            with tempfile.TemporaryDirectory() as t:
                key = owner or str(self.attacker or Path(t) / "attacker.json")
                if owner is None and self.attacker is None:
                    self.cli(["account", "create", "--out", key], d)
                a = ["mandate", "credential", "create", "--principal", self.principal, "--payee", self.mule, "--cap", "1", "--budget", "1",
                     "--max-occurrences", "1", "--expires-in", "3600", "--key", key, "--out", "m.json"]
                rc, f = self.cli(a, d)
                if rc != 0:
                    self.cell(5, side, outcome="refused", reason=f.get("error", "create refused")[:90], tx="", to=self.mule, usdz="0")
                    continue
                rc, f = self.cli(["mandate", "bind", "--credential", "m.json", "--key", key], d)
                if rc != 0:
                    self.cell(5, side, outcome="refused", reason=(f.get("error") or f.get("reason") or "bind refused")[:90], tx="",
                              to=self.mule, usdz="0", note="the chain rejects a bind not signed by the principal's owner")
                    continue
                self.cell(5, side, **self.pull(d, self.mule, Decimal(1), "a5"), note="the server held the owner key")

    # -- attacks 6 and 7: the bugs in our first design ----------------------------------------------
    def _export(self, run: str, attempt: dict[str, int], bump: int = 0) -> dict:
        lines = [{"contractor_id": c, "beneficiary_id": f"b-{c}", "amount": str(self.usdz[c] * self.usd_per_usdz), "currency": "USD",
                  "method": "LOCAL", "source_currency": "USD", "attempt": attempt[c], "request_id": make_request_id(run, "lab", c, attempt[c])}
                 for c in self.usdz]
        specs = [LineSpec(x["contractor_id"], x["beneficiary_id"], Decimal(x["amount"]), "USD", "LOCAL", "USD", x["attempt"], x["request_id"])
                 for x in lines]
        exp = datetime.fromtimestamp(time.time() + 3600 + bump, UTC)
        return {"run_id": run, "tenant": "lab", "round": 1 + bump, "batch_hash": batch_hash(run, "lab", 1 + bump, specs),
                "approval_expires_at": exp.isoformat(), "lines": lines}

    def _device(self, tag: str, revoke: bool) -> Device:
        d = Device(self.run, Path(self.owner), self.fresh(tag), dict(self.wallets), self.principal)
        if not revoke:  # our first design: the device signs attempt 2 and leaves attempt 1 alone
            d._revoke_earlier = lambda *a, **k: None  # type: ignore[method-assign]
        return d

    def a6_stale_attempt(self):
        for side, revoke in ((BEFORE, False), (AFTER, True)):
            run = f"lab6{int(revoke)}{self.k}"
            dev, handed = self._device("a6", revoke), self.fresh("a6-server")
            dev.sign(self._export(run, {"noah": 1, "zoe": 1}), handed)
            dev.sign(self._export(run, {"noah": 2, "zoe": 1}, bump=1), handed)  # the line is reopened as attempt 2
            first = make_request_id(run, "lab", "noah", 1)
            second = make_request_id(run, "lab", "noah", 2)
            a = self.wallets["noah"]
            p2 = self.pull(handed / second, a, self.usdz["noah"], second)  # the honest retry
            p1 = self.pull(handed / first, a, self.usdz["noah"], first)  # the server pays attempt 1 as well
            self.cell(6, side, **p1, note=f"attempt 2 {p2['outcome']}, then attempt 1 is pulled for the same person")

    def a7_stale_approval(self):
        for side, retire in ((BEFORE, False), (AFTER, True)):
            run = f"lab7{int(retire)}{self.k}"
            dev, handed = self._device("a7", True), self.fresh("a7-server")
            dev.sign(self._export(run, {"noah": 1, "zoe": 1}), handed)
            zid = make_request_id(run, "lab", "zoe", 1)
            old = self.fresh("a7-copy") / zid  # the server kept a copy of the credential it was handed
            shutil.copytree(handed / zid, old)
            if retire:
                dev.sign(self._export(run, {"noah": 1, "zoe": 1}, bump=1), handed)  # re-approved: the device retires zoe's old credential
            self.cell(7, side, **self.pull(old, self.wallets["zoe"], self.usdz["zoe"], "a7-old"),
                      note="paid under an approval that was replaced" if not retire else "the old credential was revoked on re-approval")

    def all(self) -> list[dict]:
        for f in (self.a1_swap, self.a2_poison, self.a3_inflate, self.a4_double, self.a5_own_mandate, self.a6_stale_attempt,
                  self.a7_stale_approval):
            f()
        return self.rows


@contextmanager
def _home(fresh: bool) -> Iterator[None]:
    """Another machine: Alta keeps its 'already paid' memory under HOME, so a new HOME is a new machine."""
    if not fresh:
        yield
        return
    old = {k: os.environ.get(k) for k in ("HOME", "USERPROFILE")}
    h = tempfile.mkdtemp(prefix="alta-lab-home-")
    os.environ.update(HOME=h, USERPROFILE=h)
    try:
        yield
    finally:
        for k, v in old.items():
            os.environ.pop(k, None) if v is None else os.environ.__setitem__(k, v)


def verdict(rows: list[dict]) -> dict[int, dict[str, str]]:
    """{attack: {side: 'paid'|'refused'}} for the table and the tests."""
    out: dict[int, dict[str, str]] = {}
    for r in rows:
        out.setdefault(r["attack"], {})[r["side"]] = r["outcome"]
    return out


__all__ = ["AFTER", "ATTACKS", "BEFORE", "NAIVE", "SAFE", "Lab", "verdict"]
