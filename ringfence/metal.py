"""Metal testnet treasury top-up under an on-chain mandate (spec 9.1). Shells out to the pinned @metalntwx/metal-agent CLI.
Harbour signs a mandate (cap = budget = the shortfall in USDZ, one pull, payee = the platform's settlement address),
the agent pulls the shortfall on Metal, and Airwallex gets the usual [SIMULATED] deposit so the existing matcher closes
the funding request. No money-core file changes. Secrets (METAL_RPC_URL, METAL_RPC_SECRET) travel only in the
environment and are scrubbed from everything this module returns, logs or writes to the ledger."""
from __future__ import annotations

import json
import logging
import os
import re
import shutil
import subprocess
import threading
import time
from decimal import ROUND_UP, Decimal
from pathlib import Path

from . import fx, ledger
from .config import ROOT

log = logging.getLogger("ringfence.metal")
PIN = "0.3.3"
# The faucet tops an account up to about 100 USDZ and no further, so the demo shortfall is scaled: 1 USDZ stands for USD 10.
USD_PER_USDZ = Decimal(os.environ.get("RF_METAL_USD_PER_USDZ", "10"))
EXPLORER = "https://testnet.metalntwx.com/tx/"
NET = ["--network", "testnet"]
SECRETS = ("METAL_RPC_URL", "METAL_RPC_SECRET")
# Event kinds this module writes. Added here so ledger.py (the verified core) stays untouched; the chain hash does not look at KINDS.
ledger.KINDS.update({"METAL_PULL", "METAL_REFUSED"})
_lock = threading.Lock()  # one CLI call at a time: a 1 GB VM and one faucet


class MetalError(Exception):
    """Metal did not do it (CLI missing, timeout, RPC error, not set up). The caller falls back to the simulated top-up."""


def enabled() -> bool:
    return os.environ.get("RF_METAL") == "1" and not os.environ.get("RF_WORLD")


def base_dir() -> Path:
    return Path(os.environ.get("RF_METAL_DIR") or ROOT / "var" / "metal") / "harbour"


def scrub(text: str) -> str:
    for n in SECRETS:
        if os.environ.get(n):
            text = text.replace(os.environ[n], f"<{n}>")
    return re.sub(r"https://rpc[\w.-]*/v1/\S+", "<rpc-url>", text)


def _cli_cmd() -> list[str]:
    if p := os.environ.get("RF_METAL_CLI"):  # path to a locally installed dist/index.js
        return ["node", p]
    return [shutil.which("npx") or "npx", "-y", f"@metalntwx/metal-agent@{PIN}"]


def run_cli(args: list[str], cwd: Path, timeout: int = 60) -> tuple[int, str]:
    """The real runner. Tests inject their own with the same signature."""
    cwd.mkdir(parents=True, exist_ok=True)
    try:
        p = subprocess.run([*_cli_cmd(), *args], check=False, cwd=cwd, capture_output=True, text=True, timeout=timeout, encoding="utf-8")
    except (subprocess.TimeoutExpired, OSError) as e:
        raise MetalError(f"Metal CLI did not finish: {type(e).__name__}") from None
    return p.returncode, scrub(p.stdout + p.stderr)


def parse(out: str) -> dict[str, str]:
    """`name value` lines. A refusal prints `reason mandate_cap_exceeded (explanation)`: keep the code, drop the prose."""
    f = {}
    for ln in out.splitlines():
        k, _, v = ln.strip().partition(" ")
        k = k.rstrip(":")
        if k and v and k not in f:
            f[k] = v.strip()
    if "reason" in f:
        f["reason"] = f["reason"].split(" ")[0]
    return f


class Metal:
    def __init__(self, runner=None, root: Path | None = None):
        self.runner, self.dir = runner or run_cli, root or base_dir()

    def cfg(self) -> dict:
        try:
            c = json.loads((self.dir / "state.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise MetalError("Metal treasury is not set up on this machine") from None
        if not {"principal", "settlement"} <= set(c):
            raise MetalError("Metal treasury setup is incomplete")
        return c

    def call(self, args: list[str], cwd: Path | None = None, ok=(0,)) -> dict:
        with _lock:
            rc, out = self.runner([*args, *NET], cwd or self.dir)
        f = parse(out)
        if rc not in ok:
            raise MetalError(f.get("error") or f.get("reason") or f"Metal CLI exit {rc}")
        return {**f, "rc": rc}

    def _mandate(self, rd: Path, usdz, ref: str, lifetime_s: int) -> dict:
        """Create and bind Harbour's one-pull mandate (cap = budget = usdz, payee = the settlement wallet) in run dir `rd`."""
        c, owner = self.cfg(), str(self.dir / "owner.json")
        self.call(["mandate", "credential", "create", "--principal", c["principal"], "--payee", c["settlement"], "--cap", str(usdz),
                   "--budget", str(usdz), "--max-occurrences", "1", "--expires-in", str(lifetime_s), "--key", owner,
                   "--out", "m.json", "--description", f"Ringfence payroll top-up {ref}"], rd)
        return self.call(["mandate", "bind", "--credential", "m.json", "--key", owner], rd)

    def pay_shortfall(self, L, run_id: str, tenant: str, req: dict, quote_c, lifetime_s: int = 3600) -> dict:
        """Mandate then pull. Returns the METAL_PULL payload (already in the ledger)."""
        c = self.cfg()
        usd = fx.get_quote(quote_c, "USD", req["currency"], buy_amount=Decimal(req["amount"])).sell_amount  # read only: a quote, no conversion
        usdz = (usd / USD_PER_USDZ).quantize(Decimal("0.01"), rounding=ROUND_UP)  # rounded up so the pull never undershoots
        ref = re.sub(r"[^A-Za-z0-9-]", "-", req["reference"])[:40]
        rd = self.dir / "runs" / ref
        bound = self._mandate(rd, usdz, ref, lifetime_s)
        pull = self.call(["mandate", "pull", "--credential", "m.json", "--to", c["settlement"], "--amount", str(usdz),
                          "--payment-id", ref], rd)
        if not pull.get("outcome", "").startswith("paid"):
            raise MetalError(f"Metal pull outcome {pull.get('outcome')}")
        pay = {"what": "Harbour's mandate paid the shortfall on Metal testnet", "usdz": str(usdz), "tx": pull["transaction"],
               "explorer_url": EXPLORER + pull["transaction"], "bind_tx": bound.get("transaction"), "mandate": bound.get("bound"),
               "run_dir": ref, "reference": req["reference"], "aud": req["amount"],
               "expires_at": int(time.time()) + lifetime_s}
        L.append("METAL_PULL", pay, run_id, tenant)
        return pay

    def treasury_key(self) -> str:
        """The platform's settlement account owner key (older setups used a plain settlement key)."""
        t = self.dir / "treasury" / "treasury_owner.json"
        return str(t if t.exists() else self.dir / "settlement.json")

    def recycle(self, pay: dict) -> None:
        """Send the pulled USDZ back to Harbour's account with a mandate the settlement account signs, so the testnet
        treasury never runs dry. Plumbing, not proof: it writes no ledger row (runs on a side thread)."""
        c, tk = self.cfg(), self.treasury_key()
        rd = self.dir / "runs" / (pay["run_dir"] + "-back")
        amt = pay["usdz"]
        self.call(["mandate", "credential", "create", "--principal", c["settlement"], "--payee", c["principal"], "--cap", amt,
                   "--budget", amt, "--max-occurrences", "1", "--expires-in", "3600", "--key", tk, "--out", "m.json"], rd)
        self.call(["mandate", "bind", "--credential", "m.json", "--key", tk], rd)
        self.call(["mandate", "pull", "--credential", "m.json", "--to", c["principal"], "--amount", amt,
                   "--payment-id", pay["run_dir"] + "-back"], rd)

    def recycle_later(self, pay: dict, alert=None) -> None:
        """Side thread. A failure is logged and, when `alert` is given, written to the ledger so the page can show it."""
        def go():
            try:
                self.recycle(pay)
            except MetalError as e:
                log.warning("metal recycle failed: %s", scrub(str(e)))
                if alert:
                    alert(scrub(str(e))[:200])
        threading.Thread(target=go, name="metal-recycle", daemon=True).start()

    def _refused(self, L, run_id: str, tenant: str, pay: dict, amount, to: str, ev: dict) -> dict:
        """Push a pull Metal must refuse, with the refusal recorded on chain. Returns the METAL_REFUSED payload."""
        if time.time() >= pay.get("expires_at", 0) - 60:  # the one-hour mandate ran out: sign it again so the refusal is for the right reason
            self._mandate(self.dir / "runs" / pay["run_dir"], pay["usdz"], pay["run_dir"], 3600)
        r = self.call(["mandate", "pull", "--credential", "m.json", "--to", to, "--amount", str(amount),
                       "--record-refusal", "--key", self.treasury_key()], self.dir / "runs" / pay["run_dir"], ok=(1,))
        if not r.get("outcome", "").startswith("refused"):
            raise MetalError("Metal did not refuse the pull")
        ev |= {"code": r.get("reason"), "usdz": str(amount), "tx": r.get("transaction"),
               "explorer_url": EXPLORER + r["transaction"] if r.get("transaction") else None, "mandate": pay.get("mandate")}
        L.append("METAL_REFUSED", ev, run_id, tenant)
        return ev

    def over_pull(self, L, run_id: str, tenant: str, pay: dict) -> dict:
        """Ask for 1.00 more than the mandate's cap."""
        return self._refused(L, run_id, tenant, pay, Decimal(pay["usdz"]) + 1, self.cfg()["settlement"],
                             {"what": "Metal refused a pull above the mandate"})

    def poisoned_pull(self, L, run_id: str, tenant: str, pay: dict, to: str) -> dict:
        """Address poisoning: send to a lookalike of the settlement wallet. Ringfence flags it in code first; the
        refusal on chain shows the mandate would stop it even if the agent were fooled."""
        real = self.cfg()["settlement"]
        if not looks_like(to, real):
            raise MetalError("not a lookalike address")
        return self._refused(L, run_id, tenant, pay, pay["usdz"], to,
                             {"what": "Metal refused a pull to a lookalike wallet", "flag": "address_poisoning", "to": to, "real": real})


def prewarm() -> None:
    """Fetch the pinned CLI into the npx cache now, so the first judge's click is not a 60 s download. Never raises."""
    def go():
        try:
            run_cli(["--help"], base_dir(), timeout=120)
        except MetalError:
            log.warning("metal pre-warm did not finish")
    threading.Thread(target=go, name="metal-prewarm", daemon=True).start()


def lookalike(addr: str) -> str:
    """The address a poisoner would mint: same first 6 and last 4 characters, different middle."""
    return addr[:6] + "".join("0123456789abcdef"[(int(ch, 16) + 7) % 16] for ch in addr[6:-4].lower()) + addr[-4:]


def looks_like(a: str, b: str) -> bool:
    """True for a different address that matches on what a person checks: the first 6 and last 4 characters."""
    a, b = a.lower(), b.lower()
    return a != b and len(a) == len(b) and a[:6] == b[:6] and a[-4:] == b[-4:]


def history(L) -> list[dict]:
    """Metal rows for the Proof tab, oldest first."""
    rows = [e for k in ("METAL_PULL", "METAL_REFUSED") for e in L.entries(kind=k)]
    return [{"seq": e["seq"], "kind": e["kind"], **e["payload"]} for e in sorted(rows, key=lambda e: e["seq"])]
