"""An offline Alta chain: a runner with the metal.run_cli signature that prints the REAL CLI text (formats captured live
25 Nov 2026) and keeps the per-credential state a chain would. Faults are injected per pull, like FakeAirwallex.inject.

Models only what the live spike proved: a bound credential pays at most max-occurrences, a refusal keeps the occurrence,
a repeated payment id on the same HOME says paid again, a new id or a fresh HOME is refused once spent, revoke is owner-only."""
from __future__ import annotations

import json
import time
from decimal import Decimal
from pathlib import Path

from ringfence import metal


class FakeChain:
    def __init__(self, creds: Path, principal: str = "0x" + "a" * 40, funds: Decimal = Decimal(100)):
        self.creds, self.principal, self.funds = creds, principal, funds
        self.state: dict[str, dict] = {}    # rid -> the LATEST mandate for that request id, the chain's truth
        self.objs: dict[str, dict] = {}     # unique key -> every mandate ever minted (a re-signed line is a second mandate)
        self.seen: dict[str, int] = {}
        self.home: dict[str, set] = {}      # rid -> payment ids this HOME has paid (Alta's local dedup)
        self.faults: list[tuple[str, dict]] = []
        self.pulls: list[dict] = []         # every pull attempt that reached the CLI
        self.refusals: list[dict] = []
        self.cmds: list[tuple] = []         # (subcommand, subsubcommand) of every CLI call, to prove what a role never calls

    # -- setup the tests use (what the approver's device does) ---------------------------------------
    def mint(self, rid: str, payee: str, usdz, *, occ: int = 1, ttl: int = 3600, bound: bool = True, desc: str = "", files: bool = True) -> str:
        self.seen[rid] = self.seen.get(rid, 0) + 1
        key = f"{rid}~{self.seen[rid]}"  # a line signed again is a second mandate; the first stays on the chain
        if files:  # a test minting straight into the server dir; the device writes its own files
            d = self.creds / rid
            d.mkdir(parents=True, exist_ok=True)
            (d / "m.json").write_text(json.dumps({"key": key}))
            (d / "m.key.json").write_text("{}")
        z = Decimal(str(usdz))
        self.state[rid] = self.objs[key] = {
            "key": key, "mandate": "0x" + format(abs(hash(key)) % 16**64, "064x"), "payee": payee, "cap": z, "budget": z,
            "spent": Decimal(0), "occ": occ, "payments": 0, "bound": bound, "revoked": False,
            "expiry": int(time.time()) + ttl, "desc": desc, "tx": []}
        self.home.setdefault(key, set())
        return self.state[rid]["mandate"]

    def revoke(self, rid: str) -> None:  # owner key only: the adapter has no code path that calls this
        self.state[rid]["revoked"] = True

    def inject(self, kind: str, **kw) -> None:
        self.faults.append((kind, kw))

    def lost_home(self) -> None:
        """The pull ran on another machine / a wiped HOME: Alta's local 'already paid' memory is gone."""
        self.home = {k: set() for k in self.home}

    def land(self, rid: str) -> None:
        """A pending pull settles."""
        s = self.state[rid]
        if s.get("pending"):
            self._commit(rid, s.pop("pending"))

    def paid(self) -> list[dict]:
        return [{"rid": r, "payee": s["payee"], "usdz": s["spent"], "tx": s["tx"]} for r, s in self.state.items() if s["payments"]]

    # -- the CLI --------------------------------------------------------------------------------------
    def __call__(self, args: list[str], cwd: Path, timeout: int = 60) -> tuple[int, str]:
        a = [x for x in args if x not in ("--network", "testnet")]
        rid = Path(cwd).name
        mj = Path(cwd) / "m.json"
        if mj.exists() and a[:3] != ["mandate", "credential", "create"]:
            rid = json.loads(mj.read_text()).get("key", rid)  # the credential file names its mandate, not the directory
        self.cmds.append(tuple(a[:3]) if a[:2] == ["mandate", "credential"] else tuple(a[:2]))
        if a[:3] == ["mandate", "credential", "create"]:
            return self._create(rid, a, Path(cwd))
        if a[:2] in (["mandate", "bind"], ["mandate", "revoke"]):
            return self._owner(rid, a)
        if a[:2] == ["mandate", "status"]:
            return self._status(rid)
        if a[:2] == ["mandate", "pull"]:
            return self._pull(rid, a)
        return 1, f"error: unsupported {a[:2]}\n"

    def _create(self, rid: str, a: list[str], cwd: Path) -> tuple[int, str]:
        f = {k: a[i + 1] for i, k in enumerate(a) if k.startswith("--") and i + 1 < len(a)}
        # any key can write a credential for any principal; only the principal's owner key can BIND it (as on the chain)
        self.mint(rid, f.get("--payee"), f["--cap"], occ=int(f.get("--max-occurrences", 10**9)), ttl=int(f.get("--expires-in", 3600)),
                  bound=False, desc=f.get("--description", ""), files=False)
        self.state[rid]["budget"] = Decimal(f["--budget"])
        self.state[rid]["forged"] = Path(f.get("--key", "")).name != "owner.json"
        (cwd / "m.json").write_text(json.dumps({"key": self.state[rid]["key"]}))
        (cwd / "m.key.json").write_text("{}")
        return 0, f"credential {cwd / 'm.json'}\n"

    def _owner(self, rid: str, a: list[str]) -> tuple[int, str]:
        f = {k: a[i + 1] for i, k in enumerate(a) if k.startswith("--") and i + 1 < len(a)}
        s = self.objs.get(rid) or self.state.get(rid)
        if s is not None and s.get("forged"):
            return 1, "error: Mandate Binding rejects the call: the key is not the principal's owner\n"
        if s is None or Path(f.get("--key", "")).name != "owner.json":
            return 1, "error: m.key.json does not hold a 32-byte private key\n"  # the pull key cannot bind or revoke
        s["bound" if a[1] == "bind" else "revoked"] = True
        return 0, f"{'bound' if a[1] == 'bind' else 'revoked'} {s['mandate']}\ntransaction 0x{abs(hash(rid)) % 16**64:064x}\n"

    def _status(self, rid: str) -> tuple[int, str]:
        s = self.objs.get(rid) or self.state.get(rid)
        if s is None:
            return 1, "error: cannot read credential\n"
        return 0, (f"mandate {s['mandate']}\ndescription {s['desc']}\nprincipal {self.principal}\n"
                   f"token 0x000000000000000000000000000000000000B5d5\nper-payment-cap {s['cap']} *USDZ\n"
                   f"budget {s['budget']} *USDZ until expiry\nexpiry {s['expiry']} (2026-11-25T06:14:15.000Z)\n"
                   f"max-occurrences {s['occ']}\npayee {s['payee'] or 'any'}\naccount-type MetalAccount\n"
                   f"bound {'yes' if s['bound'] else 'no'}\nrevoked {'yes' if s['revoked'] else 'no'}\n"
                   f"spent {s['spent']} *USDZ of {s['budget']} *USDZ\npayments {s['payments']}\n")

    def _refuse(self, rid: str, reason: str, why: str = "") -> tuple[int, str]:
        self.refusals.append({"rid": rid.split("~")[0], "reason": reason})
        return 1, f"outcome refused, not sent\nreason {reason} ({why})\nrecorded yes\ntransaction 0x{len(self.refusals):064x}\n"

    def _commit(self, rid: str, amt: Decimal) -> str:
        s = self.objs.get(rid) or self.state[rid]
        s["spent"] += amt
        s["payments"] += 1
        self.funds -= amt
        tx = "0x" + format(abs(hash((rid, s["payments"]))) % 16**64, "064x")
        s["tx"].append(tx)
        return tx

    def _pull(self, rid: str, a: list[str]) -> tuple[int, str]:
        flag = {k: a[i + 1] for i, k in enumerate(a) if k.startswith("--") and i + 1 < len(a)}
        to, amt, pid = flag["--to"], Decimal(flag["--amount"]), flag["--payment-id"]
        if Path(flag.get("--key", "x")).name == "m.key.json":  # the real CLI: --key on a pull is the refusal recorder, not the pull key
            return 1, "error: m.key.json does not hold a 32-byte private key\n"
        s = self.objs.get(rid) or self.state.get(rid)
        self.pulls.append({"rid": rid.split("~")[0], "to": to, "amount": amt, "pid": pid})
        if s is None:
            return 1, "error: cannot read credential\n"
        kind, kw = self.faults.pop(0) if self.faults else (None, {})
        if kind == "race":  # another machine pulls this line between our status read and our pull
            self._commit(rid, s["cap"])
        if kind == "error_before_commit":
            raise metal.MetalError("Metal CLI did not finish: TimeoutExpired")
        if s["revoked"]:
            return self._refuse(rid, "mandate_revoked", "the mandate was revoked")
        if not s["bound"]:
            return self._refuse(rid, "mandate_not_bound", "not bound")
        if s["payee"] is not None and to.lower() != s["payee"].lower():
            return self._refuse(rid, "mandate_payee_not_listed", "the payee is not one the mandate allows")
        if amt > s["cap"]:
            return self._refuse(rid, "mandate_cap_exceeded", "over the cap")
        if pid in self.home[rid]:
            return 0, f"outcome paid (already paid)\nspent {s['spent']} *USDZ of {s['budget']} *USDZ\npayee {to}\n"
        if s["payments"] >= s["occ"] or s["spent"] + amt > s["budget"]:
            return self._refuse(rid, "mandate_occurrences_used" if s["payments"] >= s["occ"] else "mandate_budget_spent", "spent")
        if self.funds < amt:
            return 1, "error: Mandate Binding rejects the pull and records nothing: Execution reverted for an unknown reason.\n"
        if kind == "pending":
            s["pending"] = amt
            self.home[rid].add(pid)
            return 3, f"outcome pending\ncan-land-until {int(time.time()) + kw.get('window', 600)}\npayee {to}\n"
        tx = self._commit(rid, amt)
        self.home[rid].add(pid)
        if kind == "timeout_after_commit":
            raise metal.MetalError("Metal CLI did not finish: TimeoutExpired")
        if kind == "held":
            return 4, f"transaction {tx}\noutcome held\npayee {to}\n"
        return 0, f"transaction {tx}\noutcome paid\nspent {s['spent']} *USDZ of {s['budget']} *USDZ\npayee {to}\namount {amt} *USDZ\nexplorer https://testnet.metalntwx.com/tx/{tx}\n"


class _Acct:
    def __init__(self, inner, extra):
        self._inner, self._extra = inner, extra

    @property
    def transfers(self):
        return {**self._inner.transfers, **self._extra()}

    def __getattr__(self, n):
        return getattr(self._inner, n)


class ChainView:
    """The fake Airwallex plus every chain payment as a transfer, so tests/invariants.py (I1 to I9) run unchanged."""

    def __init__(self, fake, chain: FakeChain, tenant_acct: dict[str, str], tenant: str = "kestrel"):
        self._f, self.chain, self.tokens = fake, chain, fake.tokens
        self.accounts = dict(fake.accounts)
        a = tenant_acct[tenant]
        self.accounts[a] = _Acct(fake.accounts[a], self._chain_transfers)

    def _chain_transfers(self) -> dict:
        out = {}
        for r, s in self.chain.state.items():
            if s["payments"]:
                out["alta-" + r] = {"id": "alta-" + r, "request_id": r, "status": "PAID", "beneficiary_id": None,
                                    "transfer_amount": s["spent"] * 10, "transfer_currency": "USD",
                                    "beneficiary": {"bank_details": {"account_number": s["payee"]}}}
        return out

    def __getattr__(self, n):
        return getattr(self._f, n)
