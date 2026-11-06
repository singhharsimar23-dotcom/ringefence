"""Screen clips for the video. Headless Edge draws 1920x1080 frames (viewport 1440x810 at 2x, so 2880x1620) over the Chrome DevTools
screencast, a fake cursor shows where the "mouse" is, and ffmpeg writes a constant 30 fps clip per beat into var/capture/.
Each beat also writes <beat>.json: the second each step started, so the edit can cut on the voice.

  uv run --with playwright python scripts/capture.py --url https://SITE [--beat NAME ...]

Beats run in order: problem, design, app (one continuous payroll run: it presses Start over first, so it moves sandbox
money on that site), breakit, try. Don't use the site while it records."""
from __future__ import annotations

import argparse
import asyncio
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "var" / "capture"
VW, VH, DPR, FPS = 1440, 810, 2, 30  # 2880x1620 frames: zooms up to 1.5x in the edit stay sharp at 1080p
W, H = int(VW * DPR), int(VH * DPR)
REC: list = []  # the clip being recorded, so move() can log what it pointed at

CURSOR = """addEventListener('DOMContentLoaded', () => {
  const c = document.createElement('div');
  c.innerHTML = '<svg width="26" height="30" viewBox="0 0 26 30"><path d="M3 2 L3 24 L9 18.5 L13 27 L17 25.2 L13 17 L21 17 Z" fill="#fff" stroke="#000" stroke-width="1.6" stroke-linejoin="round"/></svg>';
  c.style.cssText = 'position:fixed;z-index:2147483647;left:-40px;top:-40px;width:26px;height:30px;margin:-2px 0 0 -3px;pointer-events:none;'
    + 'filter:drop-shadow(0 3px 6px rgba(0,0,0,.55));transform-origin:3px 2px;transition:scale .12s';
  document.body.append(c);
  const ripple = (x, y) => { const r = document.createElement('div');
    r.style.cssText = `position:fixed;z-index:2147483646;left:${x}px;top:${y}px;width:12px;height:12px;margin:-6px 0 0 -6px;border-radius:50%;border:2px solid rgba(255,255,255,.9);pointer-events:none`;
    document.body.append(r); r.animate([{scale: 1, opacity: 1}, {scale: 4.5, opacity: 0}], {duration: 450, easing: 'cubic-bezier(.16,1,.3,1)'}).onfinish = () => r.remove(); };
  const p = JSON.parse(sessionStorage.getItem('rf_cur') || 'null'); if (p) { c.style.left = p[0] + 'px'; c.style.top = p[1] + 'px'; }
  addEventListener('mousemove', (e) => { c.style.left = e.clientX + 'px'; c.style.top = e.clientY + 'px'; sessionStorage.setItem('rf_cur', JSON.stringify([e.clientX, e.clientY])); }, true);
  addEventListener('mousedown', (e) => { c.style.scale = '.82'; ripple(e.clientX, e.clientY); }, true);
  addEventListener('mouseup', () => { c.style.scale = ''; }, true);
});"""


class Rec:
    """Screencast frames -> ffmpeg at a constant FPS: the newest frame is repeated until the page paints again."""

    def __init__(self, page, name: str):
        self.page, self.name, self.marks, self.last = page, name, [], None

    async def __aenter__(self):
        OUT.mkdir(parents=True, exist_ok=True)
        self.ff = subprocess.Popen(  # noqa: ASYNC220 -- started once per clip, before recording begins
            ["ffmpeg", "-y", "-loglevel", "error", "-f", "image2pipe", "-c:v", "mjpeg", "-framerate", str(FPS), "-i", "-",
                                    "-vf", f"scale={W}:{H}", "-c:v", "libx264", "-preset", "veryfast", "-crf", "16", "-g", "15", "-pix_fmt", "yuv420p",
                                    str(OUT / f"{self.name}.mp4")], stdin=subprocess.PIPE)
        self.cdp = await self.page.context.new_cdp_session(self.page)
        self.cdp.on("Page.screencastFrame", self._frame)
        await self.cdp.send("Page.startScreencast", {"format": "jpeg", "quality": 92, "maxWidth": W, "maxHeight": H, "everyNthFrame": 1})
        while self.last is None:
            await asyncio.sleep(0.05)
        self.t0, self.n, self.run = time.monotonic(), 0, True
        self.pump = asyncio.create_task(self._pump())
        REC[:] = [self]
        return self

    async def _frame(self, e):
        self.last = base64.b64decode(e["data"])
        try:
            await self.cdp.send("Page.screencastFrameAck", {"sessionId": e["sessionId"]})
        except Exception:  # noqa: BLE001, S110 -- the page navigated away; the next session acks its own frames
            pass

    async def _pump(self):
        while self.run:
            due = int((time.monotonic() - self.t0) * FPS)
            while self.n < due:
                self.ff.stdin.write(self.last)
                self.n += 1
            await asyncio.sleep(1 / (2 * FPS))

    def mark(self, step: str):
        self.marks.append([round(time.monotonic() - self.t0, 2), step])
        print(f"  {self.name} {self.marks[-1][0]:7.2f}s {step}", flush=True)

    async def __aexit__(self, *exc):
        self.run = False
        await self.pump
        await self.cdp.send("Page.stopScreencast")
        self.ff.stdin.close()
        self.ff.wait(timeout=120)
        (OUT / f"{self.name}.json").write_text(json.dumps(self.marks, indent=0))
        print("recorded", OUT / f"{self.name}.mp4")


async def move(page, sel: str, steps: int = 28):
    from playwright.async_api import Error as PlaywrightError
    loc = page.locator(sel).first
    for _ in range(20):  # the page redraws cards on each SSE update, so the element can be swapped out between scroll and measure
        try:
            await loc.scroll_into_view_if_needed(timeout=2000)
            b = await loc.bounding_box()
        except PlaywrightError:  # detached mid-measure by a redraw
            b = None
        if b:
            break
        await page.wait_for_timeout(250)
    else:
        raise RuntimeError(f"{sel} never became visible")
    if REC:  # the edit zooms onto exactly this box (CSS px in the viewport)
        REC[0].marks.append([round(time.monotonic() - REC[0].t0, 2), "box", sel, [round(b[k]) for k in ("x", "y", "width", "height")]])
    await page.mouse.move(b["x"] + b["width"] / 2, b["y"] + b["height"] / 2, steps=steps)
    await page.wait_for_timeout(250)


async def click(page, sel: str):
    await move(page, sel)
    await page.mouse.down()
    await page.wait_for_timeout(90)
    await page.mouse.up()


async def press(page, sel: str, path: str, tries: int = 4):
    """Click a button that POSTs, and make sure the POST went out and was accepted.
    The page ignores clicks while an earlier action is still in flight, and the public demo answers 429 to a POST too soon after the last."""
    sent: list = []
    def seen(r):
        if r.method == "POST" and path in r.url:
            sent.append(r)
    page.on("request", seen)
    try:
        for _ in range(tries):
            await page.wait_for_selector(sel + ":not([disabled])", timeout=180_000)
            n = len(sent)
            await click(page, sel)
            for _ in range(20):  # the click lands a few seconds after the glide starts while the screencast is running
                if len(sent) > n:
                    break
                await page.wait_for_timeout(250)
            resp = await sent[-1].response() if len(sent) > n else None
            if resp is not None and resp.status not in (409, 429):
                return
            print(f"  {sel}: not accepted ({resp.status if resp else 'page busy'}), pressing again", flush=True)
            await page.wait_for_timeout(1500)
        raise RuntimeError(f"{sel} was never accepted")
    finally:
        page.remove_listener("request", seen)


async def hold(page, sel: str, ms: int = 1300):  # the approve button fills while held
    await move(page, sel)
    await page.mouse.down()
    await page.wait_for_timeout(ms)
    await page.mouse.up()


async def glide(page, sel: str, pause: float):
    await page.evaluate("(s) => document.querySelector(s).scrollIntoView({behavior: 'smooth', block: 'start'})", sel)
    await page.wait_for_timeout(int(pause * 1000))


async def state(page) -> dict:
    return await page.evaluate("fetch('/api/state').then((r) => r.json())")


async def until(page, test, secs: int = 150):
    for _ in range(secs * 2):
        if test(await state(page)):
            return
        await page.wait_for_timeout(500)
    raise TimeoutError("the app never reached the expected state")


lane = lambda s, t: ((s.get("lanes") or {}).get(t) or {}).get("state")


async def landing(page, url: str, name: str, scenes: list[tuple[str, float]]):
    await page.goto(url + "/")
    await page.wait_for_timeout(1500)
    async with Rec(page, name) as r:
        for sel, pause in scenes:
            r.mark(sel)
            await glide(page, sel, pause)


async def app(page, url: str):
    await page.goto(url + "/app#/demo")
    await page.evaluate("fetch('/api/reset', {method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify({user: 'maya'})})")
    await until(page, lambda s: all(lane(s, t) in (None, "") for t in ("northwind", "kestrel", "harbour")), 60)
    await page.reload()
    await page.wait_for_timeout(2500)
    async with Rec(page, "app") as r:
        r.mark("run")
        await page.wait_for_timeout(1200)
        await press(page, "#next button.primary", "/api/start")
        await until(page, lambda s: lane(s, "harbour") == "AWAITING_FUNDS" and lane(s, "northwind") == "AWAITING_APPROVAL" and s["lanes"]["northwind"].get("diff"))
        await page.wait_for_timeout(1500)
        r.mark("read")
        await click(page, "[data-act=inbox][data-t=northwind]")
        await page.wait_for_timeout(4500)
        await page.keyboard.press("Escape")
        r.mark("plan")
        for t in ("kestrel", "northwind", "harbour"):
            await move(page, f".lane[data-t={t}] .status")
            await page.wait_for_timeout(2600)
        r.mark("deposit")
        await press(page, ".card[data-id=other_tenant_deposit] [data-act=scenario]", "/api/scenario/")
        await page.wait_for_selector(".card[data-id=other_tenant_deposit] .result", timeout=120_000)
        await page.wait_for_timeout(3500)
        await move(page, ".lane[data-t=harbour] .status")
        await page.wait_for_timeout(2000)
        r.mark("approve_northwind")
        await click(page, "[data-act=review][data-t=northwind]")
        await page.wait_for_selector("#hold-ok:not([disabled])")
        await page.wait_for_timeout(3000)
        await hold(page, "#hold-ok")
        await until(page, lambda s: lane(s, "northwind") in ("RELEASING", "RELEASED", "DONE"))
        await page.wait_for_timeout(1500)
        r.mark("metal_pull")
        await glide(page, "#chain", 1.5)
        await press(page, "#chain [data-id=metal_topup]", "/api/scenario/")
        await page.wait_for_selector("#chain .block.ok", timeout=180_000)
        r.mark("metal_pulled")
        await move(page, "#chain .block.ok")
        await page.wait_for_timeout(3000)
        r.mark("metal_overpull")
        await press(page, "#chain [data-id=metal_overpull]", "/api/scenario/")
        await page.locator("#chain .block.no").nth(0).wait_for(timeout=180_000)  # no wait_for_function: the app's CSP blocks eval
        await page.wait_for_timeout(3000)
        r.mark("metal_poison")
        await press(page, "#chain [data-id=metal_poison]", "/api/scenario/")
        await page.locator("#chain .block.no").nth(1).wait_for(timeout=180_000)
        await page.wait_for_timeout(3500)
        r.mark("approve_harbour")
        await until(page, lambda s: lane(s, "harbour") == "AWAITING_APPROVAL" and s["lanes"]["harbour"].get("diff"), 900)  # the dialog is drawn once: open it only when the diff is ready  # the sandbox sometimes 500s on settles for minutes
        await click(page, "[data-act=review][data-t=harbour]")
        await page.wait_for_selector("#hold-ok:not([disabled])")
        await page.wait_for_timeout(2500)
        await hold(page, "#hold-ok")
        await until(page, lambda s: all(lane(s, t) in ("RELEASED", "DONE") for t in ("northwind", "kestrel", "harbour")), 240)  # sent; settling depends on the sandbox simulator
        r.mark("all_paid")
        await glide(page, "#lanes", 4)
        await cards(page, r)


async def tail(page, url: str):
    """The end of the app beat on its own, on whatever run is live (no reset)."""
    await page.goto(url + "/app#/demo")
    await page.wait_for_timeout(2500)
    async with Rec(page, "tail") as r:
        r.mark("all_paid")
        await glide(page, "#lanes", 4)
        await cards(page, r)


async def cards(page, r):
    for card in ("bank_change_email", "cross_tenant_call"):
        r.mark(card)
        await press(page, f".card[data-id={card}] [data-act=scenario]", "/api/scenario/")
        await page.wait_for_selector(f".card[data-id={card}] .result", timeout=120_000)
        await page.wait_for_timeout(1200)
        await click(page, f".card[data-id={card}] details summary")
        await page.wait_for_timeout(4500)
    r.mark("proof")
    await click(page, "#tab-proof")
    await page.wait_for_timeout(3000)
    await page.mouse.wheel(0, 700)
    await page.wait_for_timeout(5000)


async def try_it(page, url: str):
    await page.goto(url + "/")
    await page.wait_for_timeout(1500)
    async with Rec(page, "try") as r:
        r.mark("live_demo")
        await page.wait_for_timeout(800)
        await click(page, "nav a[href='/app#/try']")
        await page.wait_for_selector(".guide:not([hidden])", timeout=20_000)
        r.mark("guide")
        await page.wait_for_timeout(3500)
        await click(page, ".guide [data-g=next]")
        await page.wait_for_timeout(3500)
        await click(page, ".guide [data-g=close]")
        r.mark("redteam")
        await move(page, "#pl-red")
        await page.wait_for_timeout(2500)  # the hover tip
        await click(page, "#pl-red")
        for _ in range(180):
            if len(await page.input_value("#pl-text")) > 40:
                break
            await page.wait_for_timeout(500)
        await page.wait_for_timeout(2000)
        r.mark("read")
        await click(page, "#pl-read")
        await page.wait_for_selector("#pl-run", timeout=120_000)  # the review: what the agent understood
        r.mark("review")
        await glide(page, ".rv-head", 4)
        await click(page, "#pl-run")
        r.mark("run")
        await page.wait_for_selector("#r-dec .decs, #r-dec p", timeout=240_000)
        r.mark("decided")
        await glide(page, "#r-dec", 6)


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--beat", nargs="*", choices=["problem", "design", "app", "tail", "breakit", "try"])
    a = ap.parse_args()
    url, want = a.url.rstrip("/"), set(a.beat or ["problem", "design", "app", "breakit", "try"])
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        b = await p.chromium.launch(channel="msedge", headless=True)
        async def page(seen_guides: bool):
            ctx = await b.new_context(viewport={"width": VW, "height": VH}, device_scale_factor=DPR, color_scheme="dark")
            await ctx.add_init_script(CURSOR)
            if seen_guides:  # the guide widget only appears in the Try it beat
                await ctx.add_init_script("try { localStorage.setItem('rf_guide_demo', '1'); localStorage.setItem('rf_guide_try', '1'); } catch (_) {}")
            return await ctx.new_page()
        if "problem" in want:
            await landing(await page(True), url, "problem", [("#top", 5), ("#band", 6), ("#email", 9)])
        if "design" in want:
            await landing(await page(True), url, "design", [("#how", 8), ("#isolation", 8)])
        if "app" in want:
            await app(await page(True), url)
        if "tail" in want:
            await tail(await page(True), url)
        if "breakit" in want:
            await landing(await page(True), url, "breakit", [("#proof", 8), ("#storm", 8), ("#ledger", 6), ("#band", 5)])
        if "try" in want:
            await try_it(await page(False), url)
        await b.close()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
