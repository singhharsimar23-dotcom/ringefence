"""Alta settlement adapter: the SAME executor, a different client underneath.

A payout to a wallet becomes one `mandate pull --payment-id <request_id>` under a credential the approver's device bound
for exactly that line (payee, amount, one pull, expiry). Everything else (fees, GBP, any bank payee) goes to the inner
Airwallex client untouched. The executor, gate, ledger and approval code are not changed: this file only has to look like
a TenantClient. It never mints or binds a credential (the owner key is not on this server) and never pulls from a read.

Money states map to what the executor already understands: paid -> PAID, pending -> IN_APPROVAL (in flight, counted as
undebited, never re-sent while it can land), held -> SENT plus an ALERT, a spent mandate -> duplicate_request_id (adopt it
only if it is exactly this line), a CLI failure -> AwxTimeout (reconcile, then one re-pull with the SAME payment id, which
the chain pays at most once)."""
from __future__ import annotations

import json
import os
import re
import threading
import time
from decimal import Decimal
from pathlib import Path

from . import ledger, metal
from .awx import AwxError, AwxTimeout
from .config import ROOT, var_dir

ledger.KINDS.update({"ALTA_PULL", "ALTA_REFUSED", "ALTA_HELD", "ALTA_BOUND", "ALTA_REVOKED", "ALTA_ATTACK"})
# 1 USDZ stands for USD 10: the faucet gives about 100 USDZ per account, so a demo batch is scaled down (a labelled limit).
USD_PER_USDZ = Decimal(os.environ.get("RF_ALTA_USD_PER_USDZ", "10"))
WALLET = re.compile(r"^0x[0-9a-fA-F]{40}$")
RID = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
TID = "alta-"
_lock = threading.Lock()  # one CLI call at a time: a 1 GB VM, one RPC secret


def enabled() -> bool:
    return os.environ.get("RF_ALTA_SETTLE") == "1"


def creds_dir() -> Path:
    return Path(os.environ.get("RF_ALTA_CREDS") or var_dir() / "alta_creds")


def is_wallet(bank_details: dict | None) -> bool:
    return bool(WALLET.match(str((bank_details or {}).get("account_number") or "")))


def usd_to_usdz(usd: Decimal) -> Decimal:
    """Whole USDZ cents or a refusal: rounding a payment would make the chain pay something nobody approved."""
    z = Decimal(usd) / USD_PER_USDZ
    if z != z.quantize(Decimal("0.01")) or z <= 0:
        raise AwxError(400, "ALTA_AMOUNT_NOT_EXACT",
                       f"USD {usd} is not a whole number of USDZ cents at 1 USDZ = USD {USD_PER_USDZ}")
    return z.quantize(Decimal("0.01"))


def _num(s: str | None) -> Decimal:
    m = re.match(r"\s*([0-9.]+)", s or "")
    return Decimal(m.group(1)) if m else Decimal(0)


class Chain:
    """The Alta CLI behind the metal.run_cli signature (tests inject a runner that speaks the same text)."""

    def __init__(self, runner=None, creds: Path | None = None):
        self.runner, self.creds = runner or metal.run_cli, creds or creds_dir()

    def dir(self, rid: str) -> Path:
        if not RID.match(rid or ""):
            raise AwxError(400, "ALTA_BAD_REQUEST_ID", "request_id is not a safe credential name")
        return self.creds / rid

    def has(self, rid: str) -> bool:
        return (self.dir(rid) / "m.json").exists()

    def run(self, args: list[str], rid: str) -> tuple[int, dict, str]:
        try:
            with _lock:
                rc, out = self.runner([*args, *metal.NET], self.dir(rid))
        except metal.MetalError as e:
            raise AwxTimeout(str(e)) from None
        return rc, metal.parse(out), out

    def status(self, rid: str) -> dict | None:
        """The credential's own state from the chain. None = no credential here. A CLI failure is a timeout, not a verdict."""
        if not self.has(rid):
            return None
        rc, f, out = self.run(["mandate", "status", "--credential", "m.json"], rid)
        if rc != 0 or "mandate" not in f:
            raise AwxTimeout(f"mandate status failed: {out[:120]}")
        return {"mandate": f["mandate"], "payee": f.get("payee", ""), "principal": f.get("principal", ""),
                "cap": _num(f.get("per-payment-cap")), "budget": _num(f.get("budget")),
                "spent": _num(f.get("spent")), "occurrences": int(f.get("max-occurrences", "0") or 0),
                "payments": int(f.get("payments", "0") or 0), "bound": f.get("bound") == "yes",
                "revoked": f.get("revoked") == "yes", "expiry": int(_num(f.get("expiry"))),
                "description": f.get("description", "")}

    def pull(self, rid: str, to: str, usdz: Decimal, pid: str) -> tuple[int, dict, str]:
        return self.run(["mandate", "pull", "--credential", "m.json", "--to", to, "--amount", str(usdz),
                         "--payment-id", pid], rid)  # no --key: on a pull it names a funded key for refusal records, not the pull key

    def pending(self, rid: str) -> int:
        """can-land-until (epoch) of a pending pull, 0 if none. Written by us, because Alta prints it only once."""
        try:
            return int(json.loads((self.dir(rid) / "pending.json").read_text())["until"])
        except (OSError, ValueError, KeyError):
            return 0

    def set_pending(self, rid: str, until: int) -> None:
        (self.dir(rid) / "pending.json").write_text(json.dumps({"until": until}))

    def budget_usdz(self) -> Decimal:
        """Unspent budget across the credentials this server holds that are bound, live and unexpired."""
        total, now = Decimal(0), time.time()
        for d in sorted(self.creds.glob("*/m.json")):
            try:
                s = self.status(d.parent.name)
            except (AwxError, AwxTimeout):
                continue
            if s and s["bound"] and not s["revoked"] and s["payments"] == 0 and s["expiry"] > now:
                total += s["budget"]
        return total


class AltaTenantClient:
    """A TenantClient for one employer. Wallet payees go to the chain, everything else to the inner client."""

    def __init__(self, inner, chain: Chain, L=None):
        self._i, self._chain, self._L = inner, chain, L

    def __getattr__(self, name):  # tenant_key, account_id, repr: whatever the inner client has
        return getattr(self._i, name)

    # -- reads -------------------------------------------------------------------------------------
    def _payee(self, bid: str) -> dict | None:
        from . import beneficiaries as ben
        p = ben.load_registry().get("tenants", {}).get(self._i.tenant_key, {}).get("payees", {}).get(bid)
        return p if p and is_wallet(p.get("bank_details")) else None

    def get(self, path: str, params: dict | None = None):
        if (m := re.fullmatch(r"/beneficiaries/([^/]+)", path)) and (p := self._payee(m.group(1))) is not None:
            return {"id": m.group(1), "beneficiary": p}
        if m := re.fullmatch(rf"/transfers/{TID}([a-z0-9-]+)", path):
            t = self._transfer(m.group(1), exact=True)
            if t is None:
                raise AwxError(404, "resource_not_found", "no such Alta payment")
            return t
        return self._i.get(path, params)

    def transfer_by_request(self, request_id: str) -> dict | None:
        if self._chain.has(request_id):
            return self._transfer(request_id, exact=False)
        return self._i.transfer_by_request(request_id)

    def balances(self) -> dict[str, Decimal]:
        b = dict(self._i.balances())
        b["USD"] = self._chain.budget_usdz() * USD_PER_USDZ  # shortcut: the chain's own refusal is the real funds check, no balance command exists
        return b

    def _transfer(self, rid: str, exact: bool) -> dict | None:
        """A payment in transfer shape, from mandate status (read-only, never a pull). exact=False: None means 'not paid yet'."""
        s = self._chain.status(rid)
        if s is None:
            return None
        usd = s["spent"] * USD_PER_USDZ if s["payments"] else s["cap"] * USD_PER_USDZ
        t = {"id": TID + rid, "request_id": rid, "transfer_amount": usd, "transfer_currency": "USD",
             "beneficiary": {"bank_details": {"account_number": s["payee"], "account_currency": "USD", "bank_country_code": "ZZ"}},
             "mandate": s["mandate"]}
        if s["payments"] >= 1:
            return {**t, "status": "PAID"}
        now = time.time()
        landing = self._chain.pending(rid) > now
        dead = s["revoked"] or (s["expiry"] <= now and not landing)
        if dead:
            return {**t, "status": "CANCELLED", "failure_type": "mandate_revoked" if s["revoked"] else "mandate_expired",
                    "failure_reason": "the credential can no longer pay"}
        if landing or exact:
            return {**t, "status": "IN_APPROVAL"}  # in flight: counted as undebited, never re-sent while it can land
        return None

    # -- writes ------------------------------------------------------------------------------------
    def post_money(self, path: str, body: dict):
        bd = (body.get("beneficiary") or {}).get("bank_details")
        bid = body.get("beneficiary_id")
        if path != "/transfers/create" or not (is_wallet(bd) or (bid and self._payee(bid))):
            return self._i.post_money(path, body)
        return self._pay(body, bd or self._payee(bid)["bank_details"])

    def post(self, path: str, body: dict):
        return self._i.post(path, body)

    def _log(self, kind: str, rid: str, **f) -> None:
        if self._L is not None:
            self._L.append(kind, {"request_id": rid, **f}, None, self._i.tenant_key)

    def _pay(self, body: dict, bd: dict) -> dict:
        rid, to = body["request_id"], bd["account_number"]
        if body.get("transfer_currency") != "USD":
            raise AwxError(400, "ALTA_CURRENCY", "Alta settlement pays USD only")
        usd = Decimal(body["transfer_amount"])
        usdz = usd_to_usdz(usd)
        s = self._chain.status(rid)
        if s is None:
            raise AwxError(400, "alta_no_credential", "no mandate was signed for this line, so nothing is pulled")
        why = self._terms(s, to, usdz)
        if why:
            raise AwxError(400, why, "the credential does not match this line, so nothing is pulled")
        rc, f, _ = self._chain.pull(rid, to, usdz, rid)
        outcome, reason = f.get("outcome", ""), f.get("reason", "")
        base = {"id": TID + rid, "request_id": rid, "transfer_amount": usd, "transfer_currency": "USD",
                "beneficiary": {"bank_details": bd}, "tx": f.get("transaction"), "explorer": f.get("explorer")}
        if rc == 0 and outcome.startswith("paid"):
            self._log("ALTA_PULL", rid, tx=f.get("transaction"), usdz=str(usdz), to=to, mandate=s["mandate"])
            return {**base, "status": "PAID"}
        if rc == 3 or outcome.startswith("pending"):
            until = int(_num(f.get("can-land-until"))) or int(time.time()) + 3600
            self._chain.set_pending(rid, until)
            self._log("ALTA_HELD", rid, outcome="pending", until=until)
            return {**base, "status": "IN_APPROVAL"}
        if rc == 4 or outcome.startswith("held"):
            self._log("ALTA_HELD", rid, outcome="held", to=to)
            if self._L is not None:
                self._L.append("ALERT", {"what": "alta_held", "request_id": rid}, None, self._i.tenant_key)
            return {**base, "status": "SENT"}  # a held payout still counts against the budget: never pay it again
        if reason in ("mandate_budget_spent", "mandate_occurrences_used"):
            raise AwxError(400, "duplicate_request_id", "the mandate is already spent", {"id": TID + rid})
        if rc == 1 and not reason:
            self._log("ALTA_REFUSED", rid, reason="reverted", text=f.get("error", "")[:160])
            raise AwxError(400, "insufficient_funds", "the chain rejected the pull without a reason; the usual cause is an unfunded principal")
        if rc == 1:
            self._log("ALTA_REFUSED", rid, reason=reason, tx=f.get("transaction"))
            raise AwxError(400, reason, f"Alta refused the pull: {reason}")
        raise AwxTimeout(f"Alta pull did not finish (exit {rc})")

    @staticmethod
    def _terms(s: dict, to: str, usdz: Decimal) -> str | None:
        """The credential must be exactly this line before we ask the chain to pull: the chain would refuse a mismatch anyway,
        and this turns it into a plain reason instead of a spent recorded refusal."""
        if s["revoked"]:
            return "mandate_revoked"
        if not s["bound"]:
            return "mandate_not_bound"
        if s["expiry"] <= time.time():
            return "mandate_expired"
        if s["payee"].lower() != to.lower():
            return "alta_payee_mismatch"
        if not (s["cap"] == s["budget"] == usdz and s["occurrences"] == 1):
            return "alta_terms_mismatch"
        return None


class AltaAwx:
    """Wraps an Awx (or FakeAirwallex-backed Awx): for_tenant() returns a client that pays wallets on chain."""

    def __init__(self, inner, chain: Chain | None = None, L=None):
        self._i, self.chain, self._L = inner, chain or Chain(), L

    def __getattr__(self, name):
        return getattr(self._i, name)

    def for_tenant(self, key: str):
        return AltaTenantClient(self._i.for_tenant(key), self.chain, self._L)


def seed_dir() -> Path:
    return Path(os.environ.get("RF_ALTA_DEMO") or ROOT / "var" / "alta" / "demo")
