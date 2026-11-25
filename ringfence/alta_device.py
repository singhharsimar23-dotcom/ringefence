"""The approver's device. Runs where the employer's OWNER key lives, never on the Ringfence server.

It turns one approved batch into one on-chain mandate per line, and it does not trust the server for anything that matters:
  - it recomputes the batch hash from the lines it is about to sign and refuses if that is not the approved hash;
  - the wallet for each contractor comes from the device's own payee book, never from the export; an export that names a
    wallet which differs from the book is refused;
  - amounts are whole USDZ cents or refused; the credential expires no later than the approval;
  - every earlier attempt of a reopened line is revoked first (an unspent old credential is still payable by whoever holds
    its pull key, which is a double pay), and a line whose earlier attempt already paid is never signed again;
  - each credential is read back from the file it just wrote and compared to the line before it is bound.
What the server receives is m.json and m.key.json: a pull key bound by the chain to this line, once."""
from __future__ import annotations

import json
import shutil
import time
from collections.abc import Callable
from datetime import datetime
from decimal import Decimal
from pathlib import Path

from . import metal
from .alta import usd_to_usdz
from .awx import AwxError
from .mandate import LineSpec, batch_hash, make_request_id

MIN_LIFE = 120  # seconds an approval must still have left, or signing is pointless
SLACK = 30  # a credential is made to expire this long before the approval does: the CLI's own latency must not push it past


class DeviceRefused(Exception):
    """The device will not sign this. The message is shown to the approver as is."""


def _spec(d: dict) -> LineSpec:
    return LineSpec(d["contractor_id"], d["beneficiary_id"], Decimal(d["amount"]), d["currency"], d["method"],
                    d["source_currency"], d["attempt"], d["request_id"])


class Device:
    def __init__(self, runner, owner_key: Path, out: Path, book: dict[str, str], principal: str,
                 now: Callable[[], float] = time.time):
        self.runner, self.key, self.out, self.book, self.principal, self.now = runner, str(owner_key), out, book, principal, now
        self.out.mkdir(parents=True, exist_ok=True)

    # -- chain ------------------------------------------------------------------------------------
    def cli(self, args: list[str], cwd: Path) -> dict:
        cwd.mkdir(parents=True, exist_ok=True)
        try:
            rc, text = self.runner([*args, *metal.NET], cwd)
        except metal.MetalError as e:
            raise DeviceRefused(f"the chain did not answer: {e}") from None
        f = metal.parse(text)
        if rc != 0:
            raise DeviceRefused(f.get("error") or f.get("reason") or f"alta exit {rc}")
        return f

    def status(self, rid: str) -> dict | None:
        d = self.out / rid
        return self.cli(["mandate", "status", "--credential", "m.json"], d) if (d / "m.json").exists() else None

    # -- the one thing the approver does ----------------------------------------------------------
    def sign(self, export: dict, hand_to: Path, confirm: Callable[[list[dict]], bool] = lambda terms: True) -> list[dict]:
        run, tenant, rnd = export["run_id"], export["tenant"], export["round"]
        specs = [_spec(x) for x in export["lines"]]
        if batch_hash(run, tenant, rnd, specs) != export["batch_hash"]:
            raise DeviceRefused("the lines do not hash to the approved batch: nothing signed")
        left = int(datetime.fromisoformat(export["approval_expires_at"]).timestamp() - self.now())
        if left < MIN_LIFE:
            raise DeviceRefused("the approval has expired or is about to: approve again")
        deadline = datetime.fromisoformat(export["approval_expires_at"]).timestamp()
        terms = [{**self._terms(x, left, export["batch_hash"]), "deadline": deadline} for x in export["lines"]]
        for t in terms:  # all checks first: a refusal on line 3 must not leave lines 1 and 2 signed
            self._check_earlier(run, tenant, t)
        if not confirm(terms):
            raise DeviceRefused("not confirmed: nothing signed")
        done = []
        for t in terms:
            self._revoke_earlier(run, tenant, t)
            done.append(self._mint(t, hand_to))
        idx = self.out / "index.json"
        known = json.loads(idx.read_text()) if idx.exists() else {}
        known[run] = sorted({*known.get(run, []), *(t["request_id"] for t in terms)})
        idx.write_text(json.dumps(known, indent=1))
        return done

    def _terms(self, line: dict, left: int, bhash: str) -> dict:
        cid = line["contractor_id"]
        wallet = self.book.get(cid)
        if not wallet:
            raise DeviceRefused(f"{cid} is not in this device's payee book: add the wallet here, not on the server")
        if line.get("wallet") and line["wallet"].lower() != wallet.lower():
            raise DeviceRefused(f"the export names a different wallet for {cid} than this device's book: refused")
        if line["currency"] != "USD":
            raise DeviceRefused(f"{cid}: Alta settlement pays USD only")
        try:
            usdz = usd_to_usdz(Decimal(line["amount"]))
        except AwxError as e:
            raise DeviceRefused(f"{cid}: {e.message}") from None
        return {"contractor_id": cid, "request_id": line["request_id"], "attempt": line["attempt"], "payee": wallet,
                "usdz": usdz, "usd": Decimal(line["amount"]), "expires_in": left, "description": f"rf:{bhash}:{line['request_id']}"}

    def _earlier(self, run: str, tenant: str, t: dict):
        for k in range(1, t["attempt"]):
            rid = make_request_id(run, tenant, t["contractor_id"], k)
            if (st := self.status(rid)) is not None:
                yield rid, st

    def _check_earlier(self, run: str, tenant: str, t: dict) -> None:
        for rid, st in self._earlier(run, tenant, t):
            if int(st.get("payments", "0")) > 0:
                raise DeviceRefused(f"{t['contractor_id']}: attempt {rid[:12]} already paid on chain, a new attempt would pay twice")

    def _revoke_earlier(self, run: str, tenant: str, t: dict) -> None:
        for rid, st in self._earlier(run, tenant, t):
            if st.get("revoked") != "yes":
                self.cli(["mandate", "revoke", "--credential", "m.json", "--key", self.key], self.out / rid)

    def _mint(self, t: dict, hand_to: Path) -> dict:
        rid, d = t["request_id"], self.out / t["request_id"]
        if (d / "m.json").exists() and self._matches(self.status(rid), t):
            pass  # signed on an earlier run of this command: hand it over again, never mint a second credential for one line
        else:
            if (d / "m.json").exists():
                # FINDING: a renewed approval (a new batch hash) leaves this line's old credential describing the old batch.
                # It is unspent and still payable by the server, so revoke it, set it aside, and sign the line again.
                self._retire(rid, t)
            # FINDING (live payroll, 25 Nov): each create and bind takes about a minute, so a lifetime worked out once at the
            # start made every later credential outlive the approval. Work it out again for each credential, just before it is made.
            life = int(t["deadline"] - self.now()) - SLACK
            if life <= 0:
                raise DeviceRefused(f"{t['contractor_id']}: the approval expired while signing: approve again")
            self.cli(["mandate", "credential", "create", "--principal", self.principal, "--payee", t["payee"],
                      "--cap", str(t["usdz"]), "--budget", str(t["usdz"]), "--max-occurrences", "1",
                      "--expires-in", str(life), "--key", self.key, "--out", "m.json",
                      "--description", t["description"]], d)
            st = self.status(rid)  # read back from the file we wrote, not from what we asked for
            if not self._matches(st, t):
                raise DeviceRefused(f"{t['contractor_id']}: the credential does not say what was asked: not binding it")
        if (st := self.status(rid)) and st.get("bound") != "yes":
            self.cli(["mandate", "bind", "--credential", "m.json", "--key", self.key], d)
        dest = hand_to / rid
        dest.mkdir(parents=True, exist_ok=True)
        for f in ("m.json", "m.key.json"):  # never the owner key
            shutil.copy2(d / f, dest / f)
        return {**t, "dir": str(dest)}

    def _retire(self, rid: str, t: dict) -> None:
        st = self.status(rid)
        if st and int(st.get("payments", "0")) > 0:
            raise DeviceRefused(f"{t['contractor_id']}: this line already paid on chain, it is not signed again")
        if st and st.get("revoked") != "yes":
            self.cli(["mandate", "revoke", "--credential", "m.json", "--key", self.key], self.out / rid)
        k = 1
        while (self.out / f"{rid}.old{k}").exists():
            k += 1
        (self.out / rid).rename(self.out / f"{rid}.old{k}")

    @staticmethod
    def _matches(st: dict | None, t: dict) -> bool:
        if st is None or st.get("revoked") == "yes" or int(st.get("payments", "0")) > 0:
            return False
        num = lambda k: Decimal(st.get(k, "0").split()[0])
        return (st.get("payee", "").lower() == t["payee"].lower() and num("per-payment-cap") == t["usdz"]
                and num("budget") == t["usdz"] and st.get("max-occurrences") == "1" and st.get("description") == t["description"])

    # -- the kill switch --------------------------------------------------------------------------
    def revoke_all(self, run: str) -> list[str]:
        """Revoke every credential this device signed for the run that has not paid. Returns what it revoked."""
        idx = self.out / "index.json"
        gone = []
        for rid in (json.loads(idx.read_text()).get(run, []) if idx.exists() else []):
            st = self.status(rid)
            if st and st.get("revoked") != "yes" and int(st.get("payments", "0")) == 0:
                self.cli(["mandate", "revoke", "--credential", "m.json", "--key", self.key], self.out / rid)
                gone.append(rid)
        return gone
