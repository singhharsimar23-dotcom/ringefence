"""HTTP side of the playground (main app only): /api/play/* and the whitelisted proxy to a world's own app.

The proxy is the only way a judge's browser reaches a world. It forwards a short list of paths, nothing else:
no reset, no kill switch, no rule signing, no webhooks, no autosettle.
"""
from __future__ import annotations

import re
from typing import Any, Literal

import httpx
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, ValidationError
from starlette.background import BackgroundTask

from . import copy, metal
from .playground import Manager, PlayError, Spec, World, default_draft_llm, draft, errors_of

_GET = [re.compile(p) for p in (r"state", r"timeline", r"ledger", r"proof", r"calls", r"cert/(northwind|kestrel|harbour)",
                                r"recheck/[A-Za-z0-9_-]{8,64}")]
_POST = [re.compile(p) for p in (r"start", r"approve", r"hold", r"resume",
                                 r"scenario/(topup|late_return|bank_change_email|injection|double_click|cross_tenant_call)")]
MAX_BODY, MAX_QUERY = 16 * 1024, 200
MAX_STREAMS, MAX_STREAMS_IP = 30, 4  # proxied /events streams: in total and per visitor


def allowed(method: str, path: str) -> bool | None:
    """True = forward. False = path exists but not for this method (405). None = not on the list (404)."""
    in_get, in_post = any(r.fullmatch(path) for r in _GET), any(r.fullmatch(path) for r in _POST)
    if method == "GET":
        return True if in_get else (False if in_post else None)
    if method == "POST":
        return True if in_post else (False if in_get else None)
    return False if (in_get or in_post) else None


class DraftBody(BaseModel):
    text: str = Field(max_length=4000)


class WorldBody(BaseModel):
    spec: dict[str, Any]
    backend: Literal["fake", "live"] = "fake"


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for", "")
    return (xff.split(",")[0].strip() or None) or (request.client.host if request.client else "?")


class _Capped(Exception):
    pass


class _Counted:
    """The model, counted against the daily draft budget only when draft() actually calls it."""

    def __init__(self, inner, count):
        self.inner, self.count = inner, count
        self.errors = (_Capped, *getattr(inner, "errors", ()))
        self.model = getattr(inner, "model", None)

    def create(self, *a):
        if not self.count():
            raise _Capped
        return self.inner.create(*a)


def register(app: FastAPI, mgr: Manager, llm_factory=None) -> None:
    def http(**kw) -> httpx.AsyncClient:  # one per request: localhost is cheap, and nothing is tied to one event loop
        return httpx.AsyncClient(timeout=httpx.Timeout(30.0, connect=2.0), **kw)

    llm_box: list = []  # built lazily: no key, no client

    def llm():
        if not llm_box:
            llm_box.append((llm_factory or default_draft_llm)())  # looked up per call so a test can swap it
        return llm_box[0]

    def world(wid: str) -> World:
        try:
            return mgr.get(wid)
        except PlayError as e:
            raise HTTPException(e.status, e.detail) from None

    def reachable(wid: str) -> World:
        w = world(wid)
        if w.status in ("queued", "failed"):
            raise HTTPException(409, w.error if w.status == "failed" else copy.WORLD_QUEUED)
        return w

    @app.get("/api/play/info")
    def info():
        return {**mgr.info(), "metal": metal.enabled()}

    @app.post("/api/play/draft")
    def make_draft(b: DraftBody):
        text = b.text.strip()
        if not text:
            return {"spec": None, "notes": [copy.DRAFT_NOTHING], "source": "none"}
        m = llm()
        return draft(text, _Counted(m, mgr.count_draft) if m else None)  # the cap only guards the model; a table is read by code

    @app.post("/api/play/worlds")
    def new_world(b: WorldBody, request: Request):
        try:
            spec = Spec.model_validate(b.spec)
            spec.for_backend(b.backend)
        except ValidationError as e:
            raise HTTPException(422, errors_of(e)) from None
        except ValueError as e:
            raise HTTPException(422, [{"field": "employers", "message": str(e)}]) from None
        if b.backend == "live" and not mgr.live_available():
            raise HTTPException(409, copy.LIVE_UNAVAILABLE)
        try:
            w = mgr.create(spec, b.backend, client_ip(request))
        except PlayError as e:
            raise HTTPException(e.status, e.detail) from None
        return mgr.view(w.wid)

    @app.get("/api/play/worlds/{wid}")
    async def world_view(wid: str):
        try:
            v = mgr.view(wid)
        except PlayError as e:
            raise HTTPException(e.status, e.detail) from None
        w = mgr.worlds.get(wid)
        if w is not None and w.status == "starting" and w.port:  # the setup steps, live, while the judge waits
            try:
                async with http() as h:
                    r = await h.get(f"http://127.0.0.1:{w.port}/api/calls", timeout=1.0)
                v["calls"] = r.json().get("calls", [])[-20:] if r.status_code == 200 else []
            except (httpx.HTTPError, ValueError):
                v["calls"] = []
        return v

    @app.api_route("/play/{wid}/api/{path:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
    async def proxy(wid: str, path: str, request: Request):
        ok = allowed(request.method, path)
        if ok is None:
            raise HTTPException(404, copy.NOT_FOUND)
        if ok is False:
            raise HTTPException(405, copy.NOT_FOUND)
        if len(request.url.query) > MAX_QUERY:
            raise HTTPException(414, copy.TOO_LARGE)
        body = await request.body()
        if len(body) > MAX_BODY:
            raise HTTPException(413, copy.TOO_LARGE)
        w = reachable(wid)
        if path != "calls":
            mgr.touch(wid)
        try:
            async with http() as h:
                r = await h.request(request.method, f"http://127.0.0.1:{w.port}/api/{path}",
                                    params=request.query_params, content=body or None,
                                    headers={"content-type": "application/json"} if body else None)
        except httpx.HTTPError:
            raise HTTPException(503, copy.WORLD_STARTING if w.status == "starting" else copy.WORLD_STOPPED) from None
        keep = {k: v for k, v in r.headers.items() if k.lower() in ("content-type", "content-disposition")}
        return Response(r.content, status_code=r.status_code, headers=keep)

    streams: dict = {"all": 0, "ip": {}}

    @app.get("/play/{wid}/events")
    async def proxy_events(wid: str, request: Request):
        w = reachable(wid)  # no touch: watching a stream is not activity
        ip = client_ip(request)
        if streams["all"] >= MAX_STREAMS or streams["ip"].get(ip, 0) >= MAX_STREAMS_IP:
            raise HTTPException(429, copy.PLAY_STREAMS)  # the page falls back to polling
        streams["all"] += 1
        streams["ip"][ip] = streams["ip"].get(ip, 0) + 1
        freed = []

        def release():
            if not freed:  # once, however the stream ends
                freed.append(1)
                streams["all"] -= 1
                streams["ip"][ip] -= 1
        h = http()
        req = h.build_request("GET", f"http://127.0.0.1:{w.port}/events", timeout=httpx.Timeout(None, connect=2.0))
        try:
            up = await h.send(req, stream=True)
        except httpx.HTTPError:
            await h.aclose()
            release()
            raise HTTPException(503, copy.WORLD_STARTING) from None

        async def gen():
            try:
                async for chunk in up.aiter_raw():
                    yield chunk
            except httpx.HTTPError:
                return
            finally:
                await up.aclose()
                await h.aclose()
        return StreamingResponse(gen(), media_type="text/event-stream", background=BackgroundTask(release),
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
