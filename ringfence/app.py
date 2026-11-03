"""The demo server: FastAPI + ONE money worker thread (BUILD_SPEC 4.11).

Handlers only read the ledger and a cache, or enqueue a job. Every call that can touch Airwallex runs on the worker,
one at a time. SSE carries no data, only "something changed": the page then re-reads /api/state and /api/timeline.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import logging
import os
import queue
import tempfile
import threading
import time
from concurrent.futures import Future
from concurrent.futures import TimeoutError as JobTimeout
from decimal import Decimal
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

from . import copy, inbox, rules, seed, setup_demo, store, track, verify, webhooks
from .agent import loop
from .agent.tools import funding_state
from .awx import Awx, AwxError, build_backend
from .config import EMPLOYERS, clock, env, tenants, var_dir
from .executor import INFLIGHT
from .ledger import Ledger
from .orchestrator import Orchestrator, Refused
from .scenarios import SCENARIOS, Simulator, settle_step
from .shadow import naive_total

log = logging.getLogger("ringfence")
STATIC = Path(__file__).resolve().parent.parent / "static"
OPEN = ("DRAFT", "AWAITING_FUNDS", "AWAITING_APPROVAL")
Tenant = Literal["northwind", "kestrel", "harbour"]


class Engine:
    """Owns the orchestrator. `call(fn)` runs fn on the worker thread and returns its result."""

    def __init__(self, awx: Awx, L: Ledger, backend: str, mode: str | None = None, idle: float = 2.0,
                 release_delay: float = 3.0, cache_every: float = 20.0):
        self.awx, self.L, self.backend = awx, L, backend
        self.idle, self.release_delay, self.cache_every = idle, release_delay, cache_every
        self.llm = None if mode == "scripted" else loop.default_llm()
        self.cert_dir = verify.CERT_DIR if backend == "live" else var_dir() / "certs"  # a fake world never touches the real certs
        self.o = Orchestrator(awx, L, cert_dir=self.cert_dir)
        self.sim = Simulator(self.o, self.rid, self.tick)
        self.q: queue.Queue = queue.Queue()
        self.cache: dict = {"diff": {}, "balances": {}, "naive": None, "naive_at": 0.0}
        self.results: dict[str, dict] = {}
        self.certs: dict[str, dict] = {}
        self.autosettle, self.error, self.ver = True, "", 0
        self._ready_since: dict[str, float] = {}
        self._docs_seen: dict[str, set[str]] = {}
        self.agent_busy: str | None = None
        self.notes: dict[str, dict] = {}
        self.llm_day, self.llm_ticks = "", 0  # shortcut: in memory, resets on restart; upgrade to a ledger count if abused
        threading.Thread(target=self._work, name="money-worker", daemon=True).start()

    # -- plumbing ----------------------------------------------------------------------------------------
    def rid(self) -> str:
        return self.o.run_id(loop.pay_date())

    def _capped(self) -> bool:
        """True once today's Claude ticks pass RF_LLM_DAILY_CAP; then the rules engine takes the rest of the day."""
        if not self.llm:
            return False
        day = dt.datetime.now(dt.UTC).date().isoformat()
        if day != self.llm_day:
            self.llm_day, self.llm_ticks = day, 0
        return self.llm_ticks >= int(env("RF_LLM_DAILY_CAP", "300"))

    def tick(self, tenant: str):
        capped = self._capped()
        use_llm = self.llm and not capped
        if use_llm:
            self.llm_ticks += 1
        self.agent_busy = tenant
        self.ver += 1
        try:
            r = loop.run_tick(self.o, tenant, llm=self.llm if use_llm else None, mode=None if use_llm else "scripted")
        finally:
            self.agent_busy = None
            self.ver += 1
        self.notes[tenant] = {"headline": copy.agent_line(r.headline) or f"{tenant.title()}: review finished",
                              "explanation": copy.agent_line(r.explanation) or "", "mode": r.mode,
                              "at": dt.datetime.now(dt.UTC).isoformat()}
        return r

    @property
    def agent_mode(self) -> str:
        return "claude" if self.llm else "offline agent"

    def call(self, fn, timeout: float = 90.0):
        f: Future = Future()
        self.q.put((fn, f))
        try:
            return f.result(timeout)
        except JobTimeout:
            raise HTTPException(504, "Ringfence is still working on that. The timeline shows where it got to.") from None

    def _work(self) -> None:
        while True:
            try:
                fn, f = self.q.get(timeout=self.idle)
            except queue.Empty:
                self._guard(self._autopilot)
                continue
            try:
                f.set_result(fn())
            except BaseException as e:  # noqa: BLE001
                f.set_exception(e)
            self._guard(self._refresh)

    def _guard(self, fn) -> None:
        try:
            fn()
            if self.error != copy.START_FAILED:  # a failed start stays visible until the next start
                self.error = ""
        except (AwxError, OSError) as e:
            log.warning("worker step failed: %s", type(e).__name__)
            self.error = "Airwallex didn't answer. Ringfence is checking whether any payment went through; nothing will be paid twice."
        except Exception:  # keep the worker alive whatever happens
            log.exception("worker step crashed")
            self.error = "Something went wrong inside Ringfence. Nothing was sent; see the timeline."
        self.ver += 1

    # -- the autopilot: what Ringfence does by itself while nobody clicks ---------------------------------
    def _autopilot(self) -> None:
        rid, now = self.rid(), time.monotonic()
        for t in EMPLOYERS:
            run = store.get_run(self.L, rid, t)
            if run is None:
                continue
            ids = {d.id for d in inbox.all_docs(t)}
            if run["state"] in OPEN and ids != self._docs_seen.get(t, ids - {"-"}) and ids - inbox.seen_ids(self.L, t):
                self._docs_seen[t] = ids
                self.tick(t)  # a new email arrived
            st = run["state"]
            if st == "AWAITING_FUNDS" or (st == "READY" and now - self._ready_since.setdefault(t, now) >= self.release_delay):
                self.o.advance(rid, t)
            if st != "READY":
                self._ready_since.pop(t, None)
            if self.autosettle and store.get_lines(self.L, rid, t, states=INFLIGHT):
                settle_step(self.awx, self.L, rid, t)
        self.o.poll()
        self._refresh(naive=now - self.cache["naive_at"] >= self.cache_every)

    def _refresh(self, naive: bool = False) -> None:
        rid = self.rid()
        for t in EMPLOYERS:
            if store.get_run(self.L, rid, t):
                try:
                    self.cache["diff"][t] = self.o.diff(rid, t)
                except AwxError:
                    pass  # keep the last diff; the error banner says what happened
            self.cache["balances"][t] = {k: str(v) for k, v in self.awx.for_tenant(t).balances().items()}
        if naive:
            self.cache["naive"], self.cache["naive_at"] = naive_total(self.awx, "AUD"), time.monotonic()

    # -- read side (no Airwallex) -------------------------------------------------------------------------
    def state(self) -> dict:
        rid, now = self.rid(), clock.business_now()
        users = seed.load()["users"]
        kill = self.L.query("SELECT on_, by, ts FROM kill_switch WHERE id=1")[0]
        lanes = {t: self._lane(rid, t, now) for t in EMPLOYERS}
        harbour_req = lanes["harbour"]["funding"]
        naive = self.cache["naive"]
        return {
            "run_id": rid, "pay_date": seed.load()["pay_date"], "now": now.isoformat(), "backend": self.backend,
            "agent": self.agent_mode, "agent_busy": self.agent_busy, "agent_capped": self._capped(),
            "model": getattr(self.llm, "model", None), "error": self.error, "autosettle": self.autosettle, "head": self.L.head()[0],
            "kill": {"on": bool(kill["on_"]), "by": kill["by"], "ts": kill["ts"]},
            "users": [{"id": k, **v, "label": _user_label(k, v)} for k, v in users.items()],
            "naive": None if naive is None else {
                "amount": str(naive[0]), "currency": "AUD", "complete": naive[1],
                "covers": bool(harbour_req and naive[0] >= Decimal(harbour_req["amount"]))},
            "lanes": lanes,
            "scenarios": [{"id": k, "title": v[0], "line": v[1], "last": self.results.get(k)} for k, v in SCENARIOS.items()],
        }

    def _lane(self, rid: str, t: str, now) -> dict:
        name = tenants(fake=True)[t].name
        run = store.get_run(self.L, rid, t)
        d = self.cache["diff"].get(t)
        lines = []
        if run:
            names = {k: c.name for k, c in seed.contractors(t).items()}
            lines = [{"contractor_id": ln["contractor_id"], "name": names[ln["contractor_id"]], "amount": ln["amount"],
                      "currency": ln["currency"], "state": ln["state"], "pill": copy.pill(ln["state"], run["state"]),
                      "request_id": ln["request_id"], "track": f"/track/{track.token(t, rid, ln['contractor_id'])}"} for ln in store.get_lines(self.L, rid, t, round=run["round"])]
            run = {**run, "lines": lines}
        req = funding_state(self.o, rid, t) if run and run["state"] == "AWAITING_FUNDS" else None
        ccys = sorted({ln["currency"] for ln in lines} | ({req["currency"]} if req else set()))
        bal = self.cache["balances"].get(t, {})
        text = copy.lane_text(name, run, d, req, now, "")
        return {
            "tenant": t, "name": name, "tz": tenants(fake=True)[t].display_tz, "state": run["state"] if run else None,
            "text": text, "lines": lines, "diff": d, "funding": req, "wallet": {c: bal[c] for c in ccys if c in bal},
            "approve_label": f"Approve {copy.totals(d['totals'])} (bound to this exact batch)" if d else "",
            "agent_note": self.notes.get(t),
            "path": {"ccys": ccys, "fx": [{"sell": g["sell"], "buy": g["buy"]} for g in (d or {}).get("fx", [])]},
        }

    def timeline(self, after: int = 0, limit: int = 300) -> list[dict]:
        out = []
        for e in self.L.entries(after_seq=after):
            row = copy.timeline_row(e)
            if row:
                p = e["payload"]
                out.append({**row, "detail": {"seq": e["seq"], "kind": e["kind"], "hash": e["hash"][:16],
                                              **{k: p[k] for k in ("request_id", "code", "reference", "transfer_id") if k in p}}})
        return out[-limit:]


def _user_label(uid: str, u: dict) -> str:
    who = uid.title()
    if u["role"] == "operator":
        return f"Operator {who}"
    return f"{u['tenant'].title()} Finance {who}"


# -- request bodies ----------------------------------------------------------------------------------------
class Who(BaseModel):
    user: str = "maya"


class TenantUser(Who):
    tenant: Tenant


class Confirm(TenantUser):
    qid: int
    ref: str = "phone callback"


class Rule(TenantUser):
    text: str = Field(max_length=600)


class Kill(Who):
    on: bool


PUBLIC_GAP_S = 1.0
PATH_GAP_S = {"/api/reset": 20.0}  # one visitor must not keep wiping the shared demo


def create_app(E: Engine) -> FastAPI:
    app = FastAPI(title="Ringfence", docs_url=None, redoc_url=None)
    app.mount("/static", StaticFiles(directory=STATIC), name="static")
    public, last_post, last_path = os.environ.get("RF_PUBLIC") == "1", [0.0], {}

    @app.middleware("http")
    async def shared_demo_throttle(request: Request, call_next):
        """RF_PUBLIC=1: one shared live demo, so operator buttons are spaced out globally."""
        if public and request.method == "POST" and request.url.path.startswith("/api/"):
            now, path = time.monotonic(), request.url.path
            if now - last_path.get(path, -1e9) < PATH_GAP_S.get(path, 0):
                return JSONResponse({"detail": copy.BUSY_RESET}, status_code=429)
            if now - last_post[0] < PUBLIC_GAP_S:
                return JSONResponse({"detail": copy.BUSY}, status_code=429)
            last_post[0], last_path[path] = now, now
        return await call_next(request)

    def user(uid: str) -> dict:
        u = seed.load()["users"].get(uid)
        if u is None:
            raise HTTPException(422, "Unknown user.")
        return u

    def act(fn):
        """Run an operator action on the worker and turn the failures a person can fix into plain 409s."""
        try:
            return {"ok": True, **(E.call(fn) or {})}
        except (Refused, PermissionError, LookupError, ValueError) as e:  # a person can fix these
            raise HTTPException(409, str(e)) from None
        except (AwxError, OSError):
            raise HTTPException(502, "Airwallex didn't answer. Nothing was changed; try again in a moment.") from None

    @app.get("/")
    def index():
        return FileResponse(STATIC / "index.html")

    @app.get("/api/state")
    def get_state():
        return {**E.state(), "public": public}

    @app.get("/api/timeline")
    def get_timeline(after: int = 0):
        return E.timeline(after)

    @app.get("/api/ledger")
    def get_ledger(seqs: str):
        wanted = {int(s) for s in seqs.split(",") if s.strip().isdigit()}
        return [{"seq": e["seq"], "ts": e["ts"], "kind": e["kind"], "tenant": e["tenant"], "hash": e["hash"],
                 "prev_hash": e["prev_hash"], "payload": e["payload"]}
                for e in E.L.entries() if e["seq"] in wanted][:50]

    @app.get("/events")
    async def events():
        async def gen():
            last = None
            while True:
                cur = (await asyncio.to_thread(E.L.head))[0], E.ver
                if cur != last:
                    last = cur
                    yield {"event": "tick", "data": json.dumps({"head": cur[0], "ver": cur[1]})}
                await asyncio.sleep(0.4)
        return EventSourceResponse(gen(), ping=15)

    @app.post("/api/start")
    def start(b: Who):
        user(b.user)

        def guarded_job():
            E.error = ""
            try:
                for t in EMPLOYERS:
                    E.tick(t)
            except Exception:
                log.exception("start failed")
                E.error = copy.START_FAILED
                E.L.append("ALERT", {"kind": "start_failed", "detail": copy.START_FAILED}, None, None)
        E.q.put((guarded_job, Future()))
        return {"ok": True, "queued": True}

    @app.post("/api/approve")
    def approve(b: TenantUser):
        u = user(b.user)

        def job():
            rid = E.rid()
            E.o.approve(rid, b.tenant, b.user, u["role"])
            return {"state": E.o.advance(rid, b.tenant)}
        return act(job)

    @app.post("/api/confirm_bank")
    def confirm_bank(b: Confirm):
        u = user(b.user)
        return act(lambda: {"beneficiary": E.o.confirm_bank_change(b.tenant, b.qid, b.user, u["role"], b.ref[:80])})

    @app.post("/api/hold")
    def hold(b: TenantUser):
        user(b.user)
        return act(lambda: E.o.hold(E.rid(), b.tenant, "OPERATOR_REQUEST", f"held by {b.user}"))

    @app.post("/api/resume")
    def resume(b: TenantUser):
        user(b.user)
        return act(lambda: {"state": E.o.resume(E.rid(), b.tenant)})

    @app.post("/api/kill")
    def kill(b: Kill):
        user(b.user)
        return act(lambda: E.o.set_kill_switch(b.on, b.user.title()))

    @app.post("/api/reset")
    def reset(b: Who):
        user(b.user)

        def job():
            E.o.reset(b.user)
            E.results.clear()
            E.certs.clear()
            E.sim._tamper = None
            E._ready_since.clear()
            E._docs_seen.clear()
            E.cache.update(diff={}, balances={}, naive=None, naive_at=0.0)
        return act(job)

    @app.post("/api/autosettle")
    def autosettle(b: Kill):
        E.autosettle = b.on
        return {"ok": True, "autosettle": b.on}

    @app.post("/api/scenario/{name}")
    def scenario(name: str, tenant: Tenant | None = None):
        if name not in SCENARIOS:
            raise HTTPException(404, "No such scenario.")

        def job():
            E.results[name] = r = E.sim.run(name, tenant)
            return {"result": r}
        return act(job)

    @app.post("/api/rules/draft")
    def rule_draft(b: Rule):
        user(b.user)
        def job():
            E.o.ensure_mandates()
            return {"draft": rules.draft(E.L, b.tenant, b.text)}
        return act(job)

    @app.post("/api/rules/sign")
    def rule_sign(b: Rule):
        u = user(b.user)
        def job():
            E.o.ensure_mandates()
            return {"version": rules.sign(E.L, b.tenant, b.text, b.user, u["role"]).mandate.version}
        return act(job)

    @app.get("/track/{tok}")
    def track_page(tok: str):
        return FileResponse(STATIC / "track.html")

    @app.get("/api/track/{tok}")
    def track_data(tok: str):
        found = track.lookup(E.L, tok)
        if found is None:
            raise HTTPException(404, "This link is not valid.")
        return found

    @app.post("/webhooks/airwallex")
    async def webhook(request: Request):
        secret = os.environ.get("AWX_WEBHOOK_SECRET", "")
        raw = await request.body()
        headers = {k: request.headers.get(k, "") for k in ("x-timestamp", "x-signature")}
        code, why = E.call(lambda: webhooks.handle(E.L, E.o.ex, secret, headers, raw))
        return PlainTextResponse(why, status_code=code)

    @app.get("/api/proof")
    def proof():
        def job():
            rep = verify.report(E.awx, E.L, E.cert_dir)
            run_id = verify.current_run_id(E.L)
            E.certs = verify.certificates(rep, run_id, E.backend)
            pub = verify.world_pub_path() if E.backend == "fake" else None  # live certs verify against the committed key
            if rep["ok"]:  # anchors for later chain checks; a failing report must not overwrite a good anchor
                verify.write_certs(E.certs, run_id, E.cert_dir)
            return {"report": rep, "certs": {t: {"valid": verify.check_cert(c, pub), "result": c["body"]["result"], "doc": c}
                                             for t, c in E.certs.items()},
                    "balances": E.cache["balances"]}
        return act(job)

    @app.get("/api/cert/{tenant}")
    def cert(tenant: Tenant):
        if tenant not in E.certs:
            raise HTTPException(404, "Open the proof page first so the certificate is issued.")
        return JSONResponse(E.certs[tenant], headers={
            "Content-Disposition": f'attachment; filename="ringfence_{tenant}_{E.certs[tenant]["body"]["run_id"]}.json"'})

    return app


def build_engine(backend: str | None, agent: str | None, **kw) -> Engine:
    if backend == "fake":  # a throwaway world: never touch the live ledger or registry
        os.environ["RF_VAR"] = tempfile.mkdtemp(prefix="rf-fake-")
    awx, _ = build_backend(backend)
    L = Ledger()
    if backend == "fake":
        setup_demo.setup(awx)
    return Engine(awx, L, backend or os.environ.get("RF_BACKEND", "live"), agent, **kw)


def main() -> int:
    import uvicorn
    ap = argparse.ArgumentParser(prog="ringfence.app")
    ap.add_argument("--backend", choices=["fake", "live"])
    ap.add_argument("--agent", choices=["scripted", "auto"], default="auto")
    ap.add_argument("--port", type=int, default=8000)
    a = ap.parse_args()
    app = create_app(build_engine(a.backend, a.agent))
    print(f"Ringfence on http://127.0.0.1:{a.port}/  (backend {a.backend or os.environ.get('RF_BACKEND', 'live')})")
    uvicorn.run(app, host="127.0.0.1", port=a.port, workers=1, reload=False, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
