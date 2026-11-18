"""Ringfence as a remote MCP server: any agent runs a payroll, only a person's passkey approves it.

Mounted at /mcp on the main app (Streamable HTTP). Onboarding is one line, for any MCP client:
    claude mcp add --transport http ringfence https://<site>/mcp
No login: the MCP holds no power worth stealing. There is no approve tool and no tool takes bank details. The agent hands
over the files it found, code drafts and prices the run on its own Airwallex sandbox account (a playground world), a
person approves on /approve/{run_id} with a passkey, and release_payroll sends exactly what was approved, or holds.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from mcp.server.mcpserver import Context, MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field, ValidationError

from . import beneficiaries as ben
from .config import var_dir
from .play_routes import _Counted
from .playground import Manager, PlayError, Spec, World, default_draft_llm, draft, errors_of

SLOT, APPROVER = "northwind", "finance-northwind"  # an MCP run is one employer: the first slot of its world
STATIC = Path(__file__).resolve().parent.parent / "static"
SETTLED = ("AWAITING_APPROVAL", "AWAITING_FUNDS", "READY", "HELD", "RELEASED", "DONE")
SENT = ("RELEASING", "RELEASED", "DONE")
MAX_FILES, MAX_CHARS = 6, 8000

INSTRUCTIONS = (
    "Ringfence runs payroll on Airwallex. Give run_payroll every file in the user's payroll folder, verbatim, including "
    "emails you think are suspicious: Ringfence decides what to trust. You cannot approve a run and no tool accepts bank "
    "details. After run_payroll, show the user the approval link: it is a page on this same Ringfence server, the one the "
    "user connected you to. Once they say they approved, call release_payroll.")


# -- WebAuthn: passkey approval, verified with `cryptography` (no new dependency) ------------------------------------
def b64d(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _keys_path() -> Path:
    return var_dir() / "passkeys.json"


def load_keys() -> dict:
    p = _keys_path()
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"creds": {}}


def save_key(cred_id: str, spki: str, alg: int, rp_id: str) -> None:
    keys = load_keys()
    keys["creds"][cred_id] = {"spki": spki, "alg": alg, "rp_id": rp_id, "added": int(time.time())}
    _keys_path().write_text(json.dumps(keys, indent=1), encoding="utf-8")


def verify_assertion(a: dict, challenge: str) -> str:
    """The credential id if `a` is a user-verified passkey signature over `challenge` by an enrolled key. Raises otherwise."""
    cred = load_keys()["creds"].get(a.get("id", ""))
    if cred is None:
        raise ValueError("This passkey is not enrolled on this server.")
    cdj = b64d(a["clientDataJSON"])
    cd = json.loads(cdj)
    origin = urlparse(cd.get("origin", ""))
    if cd.get("type") != "webauthn.get" or not hmac.compare_digest(str(cd.get("challenge", "")), challenge):
        raise ValueError("The signature is for a different approval.")
    if origin.hostname != cred["rp_id"] or (origin.scheme != "https" and origin.hostname not in ("localhost", "127.0.0.1")):
        raise ValueError("The signature came from another site.")
    ad = b64d(a["authenticatorData"])
    if len(ad) < 37 or ad[:32] != hashlib.sha256(cred["rp_id"].encode()).digest():
        raise ValueError("The signature is for another site.")
    if not ad[32] & 0x01 or not ad[32] & 0x04:  # UP and UV: a person was there and unlocked it (Windows Hello, Touch ID)
        raise ValueError("The passkey did not verify the person.")
    key = serialization.load_der_public_key(b64d(cred["spki"]))
    signed, sig = ad + hashlib.sha256(cdj).digest(), b64d(a["signature"])
    try:
        if cred["alg"] == -7 and isinstance(key, ec.EllipticCurvePublicKey):
            key.verify(sig, signed, ec.ECDSA(hashes.SHA256()))
        elif cred["alg"] == -257 and hasattr(key, "key_size"):
            key.verify(sig, signed, padding.PKCS1v15(), hashes.SHA256())
        else:
            raise ValueError("Unsupported passkey type.")
    except InvalidSignature:
        raise ValueError("The passkey signature is not valid.") from None
    return a["id"]


# -- talking to a world, over localhost (never through the public proxy) ---------------------------------------------
def settled(lane: dict) -> bool:
    """Settled, and the cached diff (totals, FX, bank changes) has caught up with the state: it refreshes a tick later."""
    return lane.get("state") in SETTLED and (lane.get("diff") or {}).get("state") == lane["state"]


class Stop(Exception):
    pass


def call(w: World, method: str, path: str, body: dict | None = None, timeout: float = 90.0):
    try:
        r = httpx.request(method, f"http://127.0.0.1:{w.port}/api/{path}", json=body, timeout=timeout)
    except httpx.HTTPError:
        raise Stop("The run's bank connection is not answering. Try again in a moment.") from None
    data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code >= 400:
        raise Stop(str(data.get("detail") or f"Refused ({r.status_code})."))
    return data


def approved_last4(w: World) -> dict[str, str]:
    """contractor id -> last 4 of the account Ringfence pinned and sends inline: what the approver is shown."""
    try:
        reg = json.loads((w.dir / "var" / "registry.json").read_text(encoding="utf-8"))["tenants"][SLOT]
    except (OSError, KeyError, ValueError, TypeError):
        return {}
    return {cid: ben.bank_key(reg["payees"].get(bid, {}).get("bank_details", {}))[-4:]
            for cid, bid in reg.get("beneficiaries", {}).items()}


def summary(w: World, base: str, since: int | None = None) -> dict:
    st = call(w, "GET", "state")
    lane = st["lanes"][SLOT]
    d = lane.get("diff") or {}
    tl = call(w, "GET", "timeline")
    tids = {r["detail"]["request_id"]: r["detail"]["transfer_id"] for r in tl
            if r["detail"].get("request_id") and r["detail"].get("transfer_id")}
    banks = approved_last4(w)
    names = {ln["contractor_id"]: ln["name"] for ln in lane["lines"]}
    flagged = [{"what": r["proposed"], "decision": r["decided"], "why": r["why"]}
               for r in call(w, "GET", "decisions") if r["tone"] in ("flag", "refused", "held") and r["kind"] != "BENEFICIARY_QUARANTINED"]
    out = {
        "run_id": w.wid,
        "bank": (f"Airwallex sandbox, account ending {st['world']['account_suffix']}" if w.backend == "live"
                 else "[SIMULATED] bank" + (" (the live Airwallex sandbox was busy)" if w.fell_back else "")),
        "employer": lane["name"], "state": lane["state"], "status": lane["text"]["status"],
        "payments": [{"name": ln["name"], "amount": ln["amount"], "currency": ln["currency"],
                      "to_account_ending": banks.get(ln["contractor_id"]), "state": ln["state"],
                      **({"airwallex_transfer_id": tids[ln["request_id"]]} if ln["request_id"] in tids else {})}
                     for ln in lane["lines"]],
        "totals": d.get("totals"),
        "fx": [{"sell": g["sell"], "buy": g["buy"], "rate": g["rate"]} for g in d.get("fx", [])],
        "refused_or_flagged": flagged,
        "bank_change_requests": [{"id": b["id"], "name": b["name"], "new_account_ending": b["last4"],
                                  "status": {"ACTIVE": "quarantined: not used", "REJECTED": "rejected: not used"}.get(b["status"], b["status"].lower())}
                                 for b in d.get("bank_changes", [])],
    }
    asked = {f"New bank details for {b['name']}" for b in out["bank_change_requests"]}
    out["refused_or_flagged"] = [f for f in flagged if f["what"].split(" ending ")[0] not in asked]  # a malformed retry of a quarantined request
    if lane["state"] == "AWAITING_APPROVAL":
        out["approve_at"] = f"{base}/approve/{w.wid}"
    if since is not None:
        new = [r for r in tl if r["detail"]["seq"] > since]
        out["what_happened"] = [r["text"] for r in new]
        for r in new:
            for x in r["detail"].get("lines", []):  # a payee repointed on Airwallex after approval
                out.setdefault("changed_after_approval", []).append(
                    {"name": names.get(x["contractor_id"], x["contractor_id"]),
                     "approved_account_ending": banks.get(x["contractor_id"]), "airwallex_now_says": x.get("live_last4")})
    return out


def public_base(ctx: Context | None = None, request: Request | None = None) -> str:
    if os.environ.get("RF_PUBLIC_URL"):
        return os.environ["RF_PUBLIC_URL"].rstrip("/")
    h = (request.headers if request is not None else (ctx.headers if ctx is not None else None)) or {}
    host = h.get("x-forwarded-host") or h.get("host") or "127.0.0.1:8000"
    proto = h.get("x-forwarded-proto") or ("http" if host.startswith(("127.0.0.1", "localhost")) else "https")
    return f"{proto}://{host}"


# -- the server ------------------------------------------------------------------------------------------------------
def build(mgr: Manager, llm_factory=None) -> MCPServer:
    m = MCPServer("ringfence", instructions=INSTRUCTIONS)
    llm_box: list = []

    def llm():
        if not llm_box:
            llm_box.append((llm_factory or default_draft_llm)())
        return llm_box[0]

    def world(run_id: str) -> World:
        w = mgr.worlds.get(run_id)
        try:
            if w is None or not w.mcp:
                raise PlayError(404, "Ringfence has no agent run with that id.")
            return mgr.touch(run_id)
        except PlayError as e:
            raise ToolError(e.detail) from None

    def guard(fn):
        try:
            return fn()
        except Stop as e:
            raise ToolError(str(e)) from None

    def wait(w: World, until, timeout: float) -> dict:
        t0 = time.monotonic()
        while time.monotonic() - t0 < timeout:
            mgr.touch(w.wid)
            st = call(w, "GET", "state")
            if until(st):
                return st
            time.sleep(1.0)
        raise Stop("Ringfence is still working on this run. Call payroll_status in a minute.")

    @m.tool()
    def run_payroll(files: dict[str, str], ctx: Context) -> dict:
        """Start this week's payroll from the files in the user's payroll folder.

        files: file name -> the file's full text, verbatim. Include every timesheet, company note and email, even ones
        that look suspicious or ask for changes; Ringfence treats them all as untrusted and flags what it will not do.
        Code prices the run on the employer's own Airwallex account. Returns the payments, anything refused or flagged,
        and `approve_at`: a link the user must open to approve with their passkey. You cannot approve a run."""
        if not files or len(files) > MAX_FILES:
            raise ToolError(f"Send between 1 and {MAX_FILES} files.")
        text = "\n\n".join(f"--- file: {name[:80]} ---\n{body}" for name, body in files.items())
        if len(text) > MAX_CHARS:
            raise ToolError(f"The files are too long together (over {MAX_CHARS} characters).")
        m_ = llm()
        d = draft(text, _Counted(m_, mgr.count_draft) if m_ else None)
        if not d.get("spec") or d.get("errors"):
            raise ToolError("Ringfence could not read a payroll from these files. " + " ".join(
                d.get("notes", []) + [f"{e['field']}: {e['message']}" for e in d.get("errors", [])]))
        try:
            spec = Spec.model_validate(d["spec"])
            spec.employers = spec.employers[:1]  # shortcut: one employer per MCP run; several would need a slot argument
        except ValidationError as e:
            raise ToolError(str(errors_of(e))) from None
        # one agent run at a time: a fresh run replaces the last one (its sandbox slot is needed), never mid-payout
        # shortcut: any caller may replace any agent run (no auth by design); bind runs to a caller token if this goes public
        olds = [o for o in mgr.worlds.values() if o.mcp and o.status in ("queued", "starting", "ready")]
        if any(o.status == "ready" and (mgr.probe(o) or {}).get("lanes", {}).get(SLOT, {}).get("state") == "RELEASING" for o in olds):
            raise ToolError("Another payroll is being sent right now. Try again in a minute.")
        with mgr.lock:
            for old in olds:
                if old.status in ("queued", "starting", "ready"):
                    mgr._expire(old)
            mgr.queue = [x for x in mgr.queue if mgr.worlds[x].status == "queued"]
        try:
            w = mgr.create(spec, "live" if mgr.live_available() else "fake", "mcp-" + secrets.token_hex(4), mcp=True)
        except PlayError as e:
            raise ToolError(e.detail) from None

        def go() -> dict:
            t0 = time.monotonic()
            while w.status in ("queued", "starting") and time.monotonic() - t0 < 150:
                mgr.touch(w.wid)
                time.sleep(1.0)
            if w.status != "ready":
                raise Stop(w.error or "The Airwallex sandbox account did not open in time. Try again.")
            call(w, "POST", "start", {"user": ""})
            wait(w, lambda st: settled(st["lanes"][SLOT]) and not st.get("agent_busy") or st.get("error"), 150)
            return {**summary(w, public_base(ctx)), "notes": d.get("notes", []),
                    "next": "Show the user approve_at. Only they can approve, with their passkey. Then call release_payroll."}
        return guard(go)

    @m.tool()
    def release_payroll(run_id: str, ctx: Context) -> dict:
        """Send an approved run. Refused unless a person approved this exact run with their passkey. Before sending,
        Ringfence re-reads every payee from Airwallex; if any bank account changed after approval, nothing is sent."""
        w = world(run_id)

        def go() -> dict:
            base = public_base(ctx)
            st = call(w, "GET", "state")
            state = st["lanes"][SLOT]["state"]
            if state == "AWAITING_APPROVAL":
                raise Stop(f"Not approved. Only a person can approve this run, with their passkey, at {base}/approve/{w.wid}. "
                           "No tool can approve it, and asking again will not change that.")
            if state in SENT:
                return {**summary(w, base), "note": "Already sent. Nothing new was sent."}
            if state != "READY":
                return summary(w, base)
            call(w, "POST", "release", {"tenant": SLOT, "user": APPROVER})
            return summary(w, base, since=st["head"])
        return guard(go)

    @m.tool()
    def payroll_status(run_id: str, ctx: Context) -> dict:
        """Where a run is: each payment, its state and Airwallex transfer id, and anything refused or flagged."""
        w = world(run_id)
        return guard(lambda: summary(w, public_base(ctx)))

    @m.tool()
    def payroll_proof(run_id: str, ctx: Context) -> dict:
        """The signed certificate for a run: Ringfence re-reads every transfer from Airwallex and checks each one went
        out from this employer's own account, to an approved account, once."""
        w = world(run_id)

        def go() -> dict:
            p = call(w, "GET", "proof", timeout=120)
            c = (p.get("certs") or {}).get(SLOT) or {}
            return {"result": c.get("result"), "signature_valid": c.get("valid"), "all_checks_passed": p["report"]["ok"],
                    "download": f"{public_base(ctx)}/play/{w.wid}/api/cert/{SLOT}",
                    "payments": summary(w, public_base(ctx))["payments"]}
        return guard(go)

    return m


# -- the human side: approval page and passkey enrolment --------------------------------------------------------------
class Assertion(BaseModel):
    challenge: str = Field(max_length=100)
    id: str = Field(max_length=400)
    clientDataJSON: str = Field(max_length=4000)
    authenticatorData: str = Field(max_length=4000)
    signature: str = Field(max_length=2000)


class Reject(BaseModel):
    qid: int


class Enrol(BaseModel):
    key: str = Field(max_length=200)
    id: str = Field(max_length=400)
    spki: str = Field(max_length=2000)
    alg: int


def batch_fp(view: dict) -> str:
    """What the person saw: each payee, amount, currency and the account it goes to. A change voids the signature."""
    rows = sorted((p["name"], p["amount"], p["currency"], p["to_account_ending"]) for p in view["payments"])
    return hashlib.sha256(json.dumps([view["run_id"], rows]).encode()).hexdigest()


def register(app: FastAPI, mgr: Manager, llm_factory=None) -> MCPServer:
    m = build(mgr, llm_factory)
    sub = m.streamable_http_app(stateless_http=True, json_response=True,
                                transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False))
    app.router.routes.extend(sub.routes)  # POST /mcp
    app.router.lifespan_context = lambda _app: m.session_manager.run()
    challenges: dict[str, tuple[str, str, float]] = {}  # challenge -> (wid, batch fingerprint, expiry)
    lock = threading.Lock()

    def mcp_world(wid: str) -> World:
        w = mgr.worlds.get(wid)
        if w is None or not w.mcp or w.status != "ready":
            raise HTTPException(410, "This run has ended. Ask the agent to start a new one.")
        return mgr.touch(wid)

    def http(fn):
        try:
            return fn()
        except Stop as e:
            raise HTTPException(409, str(e)) from None

    @app.get("/approve/latest")
    def latest(request: Request):
        """The newest agent run, for the operator's own screen-recording script. Same key as passkey enrolment."""
        want = os.environ.get("RF_ENROLL_KEY", "")
        if not want or not hmac.compare_digest(request.headers.get("x-enroll-key", ""), want):
            raise HTTPException(403, "Wrong enrolment key.")
        runs = sorted((w for w in mgr.worlds.values() if w.mcp), key=lambda w: w.created)
        if not runs:
            raise HTTPException(404, "No agent run yet.")
        return {"run_id": runs[-1].wid, "status": runs[-1].status}

    @app.get("/approve/{wid}")
    def approve_page(wid: str):
        return FileResponse(STATIC / "approve.html")

    @app.get("/approve/{wid}/view")
    def approve_view(wid: str, request: Request):
        w = mcp_world(wid)
        v = http(lambda: summary(w, public_base(request=request)))
        v.pop("approve_at", None)
        if v["state"] == "AWAITING_APPROVAL":
            c = secrets.token_urlsafe(32)
            with lock:
                now = time.time()
                for k in [k for k, x in challenges.items() if x[2] < now]:
                    del challenges[k]
                challenges[c] = (wid, batch_fp(v), now + 300)
            host = request.url.hostname
            v["passkey"] = {"challenge": c, "rp_id": host,
                            "allow": [k for k, x in load_keys()["creds"].items() if x["rp_id"] == host]}
        return v

    @app.post("/approve/{wid}")
    def approve(wid: str, a: Assertion, request: Request):
        w = mcp_world(wid)
        with lock:
            got = challenges.pop(a.challenge, None)  # one use, whatever happens next
        if got is None or got[0] != wid or got[2] < time.time():
            raise HTTPException(409, "This approval expired. Reload the page and approve again.")
        try:
            who = verify_assertion(a.model_dump(), a.challenge)
        except (ValueError, KeyError, TypeError) as e:
            raise HTTPException(403, str(e) or "The passkey signature is not valid.") from None
        now = http(lambda: summary(w, public_base(request=request)))
        if batch_fp(now) != got[1]:
            raise HTTPException(409, "The payroll changed after you opened it. Reload and check it again.")
        if any(x["status"].startswith("quarantined") for x in now["bank_change_requests"]):
            raise HTTPException(409, "Decide on the bank change first: reject it, or have a second person confirm it by phone.")
        r = http(lambda: call(w, "POST", "approve", {"tenant": SLOT, "user": APPROVER}))
        return {"ok": True, "state": r.get("state"), "passkey": who[:12]}

    @app.post("/approve/{wid}/reject")
    def reject(wid: str, b: Reject):
        """The person says a bank-change request is not real. Moves no money: the verified account stays."""
        w = mcp_world(wid)
        return http(lambda: call(w, "POST", "reject_bank", {"tenant": SLOT, "user": "", "qid": b.qid}))

    @app.post("/approve/{wid}/resume")
    def resume(wid: str):
        """A held run goes back for a fresh look and a fresh approval. Moves no money."""
        w = mcp_world(wid)
        return http(lambda: call(w, "POST", "resume", {"tenant": SLOT, "user": ""}))

    @app.get("/passkey")
    def enrol_page():
        return FileResponse(STATIC / "passkey.html")

    @app.post("/passkey")
    def enrol(b: Enrol, request: Request):
        want = os.environ.get("RF_ENROLL_KEY", "")
        if not want or not hmac.compare_digest(b.key, want):
            raise HTTPException(403, "Wrong enrolment key.")
        if b.alg not in (-7, -257):
            raise HTTPException(422, "Use a passkey with ES256 or RS256.")
        try:
            serialization.load_der_public_key(b64d(b.spki))
        except ValueError:
            raise HTTPException(422, "That is not a public key.") from None
        save_key(b.id, b.spki, b.alg, request.url.hostname)
        return {"ok": True, "rp_id": request.url.hostname}

    return m
