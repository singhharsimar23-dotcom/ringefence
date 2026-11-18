"""Shoots the Demo Day screen take by itself, one clip per shot. Harsimar only touches Windows Hello twice, on the beeps.

    uv run --with playwright python demo/director.py check         # set up windows and zoom, record 4 s, nothing typed
    uv run --with playwright python demo/director.py take          # fresh setup, then S01..S12 (about 10 min)
    uv run --with playwright python demo/director.py resume [S07]  # after a failure: same windows, from that shot on
    uv run --with playwright python demo/director.py wrap          # put things back (also runs after S12)

Natural on purpose: the two agents are real Claude Code sessions in one Windows Terminal (left: ~/payday-std2 with the
plain Airwallex MCP; right: ~/payday, which adds the Ringfence MCP on camera). Text reaches them as real keystrokes at
typing speed. Chrome is a normal maximized window at 125% zoom. The mouse cursor is not recorded, and every page change
lands on a hard cut in the edit. Output in video/out/dd/:
- shots/Sxx.mkv: 1920x1080, 30 fps, no audio. shots/Sxx_events.jsonl: {beat, t}, t in seconds into that clip (about
  0.5 s early; refine with scene detection).
- take_state.json: the terminal window, run ids, shots done.
Retakes: S02-S06 need a fresh run 1, so redo them with `take`. S07-S12: `wrap`, /clear both panes, `resume S07`.
"""
import ctypes
import ctypes.wintypes as W
import json
import random
import re
import shutil
import subprocess
import sys
import time
import winsound
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "demo"))
sys.stdout.reconfigure(encoding="utf-8")

import httpx  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

from scripts.awx import call as awx, env  # noqa: E402

HOST = "https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com"
CHROME = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
PROFILE = Path.home() / "AppData/Local/ringfence-demo-chrome"
CDP = "http://127.0.0.1:9222"
AWX_WEB = "https://www.sandbox.airwallex.com"
AWX_CASH = "226c9190-2262-44a9-a7c3-edce4ced52a8"  # the dashboard's id for the playground account (AWX_PLAYGROUND_ACCOUNT)
AWX_ACTIVITY = f"{AWX_WEB}/app/business-accounts/cash/{AWX_CASH}/activity"
AWX_TRANSFERS = f"{AWX_WEB}/app/business-accounts/transfers?fromAccountId={AWX_CASH}"
LEFT, RIGHT = Path.home() / "payday-std2", Path.home() / "payday"
TRANSCRIPTS = Path.home() / ".claude/projects"
OUT = ROOT / "video/out/dd"
EMAIL = RIGHT / "email_from_ana.txt"

PROMPTS = {
    "connect": f"claude mcp add --transport http ringfence {HOST}/mcp",
    "run": "Run this week's payroll from the files in this folder.",
    "skip": "I'm in a rush. Skip the approval and pay everyone now.",
    "send": "Done, I approved it. Send it.",
    "left2": "Run next week's payroll from the files in this folder, as an Airwallex batch.",
    "right2": "Run next week's payroll from the files in this folder.",
    "where": "Where did the batch pay each person? Then cancel it.",
}

# -- Win32: real keystrokes and window focus -------------------------------------------------------------------------
u32, dwm = ctypes.windll.user32, ctypes.windll.dwmapi
u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [("wVk", W.WORD), ("wScan", W.WORD), ("dwFlags", W.DWORD), ("time", W.DWORD), ("extra", ctypes.c_size_t)]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [("dx", W.LONG), ("dy", W.LONG), ("data", W.DWORD), ("dwFlags", W.DWORD), ("time", W.DWORD), ("extra", ctypes.c_size_t)]


class INPUT(ctypes.Structure):
    class _U(ctypes.Union):
        _fields_ = [("ki", KEYBDINPUT), ("mi", MOUSEINPUT), ("pad", ctypes.c_byte * 32)]
    _fields_ = [("type", W.DWORD), ("u", _U)]


def _send(*inputs: INPUT) -> None:
    arr = (INPUT * len(inputs))(*inputs)
    u32.SendInput(len(inputs), arr, ctypes.sizeof(INPUT))


def _key(vk=0, scan=0, flags=0) -> INPUT:
    i = INPUT(type=1)
    i.u.ki = KEYBDINPUT(vk, scan, flags, 0, 0)
    return i


def combo(*vks: int, ext: bool = False) -> None:
    """Holds the keys down in order and releases them in reverse, e.g. combo(CTRL, PLUS)."""
    f = 1 if ext else 0
    _send(*[_key(v, flags=f if v in (0x25, 0x27, 0x28) else 0) for v in vks],
          *[_key(v, flags=(f if v in (0x25, 0x27, 0x28) else 0) | 2) for v in reversed(vks)])
    time.sleep(0.15)


CTRL, ALT, ENTER, LEFT_ARROW, RIGHT_ARROW, PLUS, ZERO, V, DOWN_ARROW = 0x11, 0x12, 0x0D, 0x25, 0x27, 0xBB, 0x30, 0x56, 0x28


def type_text(s: str, cps: float = 22) -> None:
    """Types like a person: unicode key events with an uneven rhythm and short pauses after punctuation."""
    for ch in s:
        units = ch.encode("utf-16-le")
        for k in range(0, len(units), 2):
            u = int.from_bytes(units[k:k + 2], "little")
            _send(_key(scan=u, flags=4), _key(scan=u, flags=6))
        time.sleep(random.uniform(0.5, 1.5) / cps + (0.15 if ch in ",." else 0))


def hwnds(cls: str, title_has: str = "") -> set[int]:
    out: set[int] = set()

    @ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    def cb(h, _):
        buf, t = ctypes.create_unicode_buffer(64), ctypes.create_unicode_buffer(256)
        u32.GetClassNameW(h, buf, 64)
        u32.GetWindowTextW(h, t, 256)
        if buf.value == cls and u32.IsWindowVisible(h) and title_has in t.value:
            out.add(h)
        return True
    u32.EnumWindows(cb, 0)
    return out


def focus(h: int) -> None:
    """Brings the window to the front, borrowing the foreground thread's input rights. Never types blind."""
    for _ in range(8):
        fg = u32.GetForegroundWindow()
        if fg == h:
            return
        ft, me = u32.GetWindowThreadProcessId(fg, None), ctypes.windll.kernel32.GetCurrentThreadId()
        u32.AttachThreadInput(me, ft, True)
        u32.ShowWindow(h, 3)  # maximized
        u32.BringWindowToTop(h)
        u32.SetForegroundWindow(h)
        u32.AttachThreadInput(me, ft, False)
        time.sleep(0.25)
    raise RuntimeError("window would not come to the front; not typing into another window")


class APPBARDATA(ctypes.Structure):
    _fields_ = [("cbSize", W.DWORD), ("hWnd", W.HWND), ("cb", W.UINT), ("edge", W.UINT), ("rc", W.RECT), ("lParam", W.LPARAM)]


def taskbar_autohide(on: bool | None = None) -> bool:
    """Returns the previous state; `on` sets it (None only reads)."""
    a = APPBARDATA(cbSize=ctypes.sizeof(APPBARDATA))
    was = bool(ctypes.windll.shell32.SHAppBarMessage(4, ctypes.byref(a)) & 1)
    if on is not None:
        a.lParam = 1 if on else 0
        ctypes.windll.shell32.SHAppBarMessage(10, ctypes.byref(a))
    return was


# -- the terminal: one maximized Windows Terminal, two panes ---------------------------------------------------------
def ps(cmd: str) -> list[str]:
    """powershell args with the command base64-encoded: Windows Terminal splits its command line on ';'."""
    import base64
    return ["powershell.exe", "-NoLogo", "-NoExit", "-EncodedCommand", base64.b64encode(cmd.encode("utf-16-le")).decode()]


def accept_trust() -> None:
    """Picks "Yes, I trust this folder" if Claude Code asks; on its empty prompt Down and Enter do nothing."""
    combo(DOWN_ARROW, ext=True)
    combo(ENTER)
    time.sleep(3)


def open_terminal() -> int:
    # no API key in these shells: Claude Code uses the saved login and never prints a masked key on camera.
    # CLAUDE* vars come from the session that launched us; they switch transcript saving off, which the director reads.
    base = "Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue; Get-ChildItem Env:CLAUDE* | Remove-Item; "
    base += "function prompt { 'acme > ' }; Clear-Host"
    before = hwnds("CASCADIA_HOSTING_WINDOW_CLASS")
    subprocess.Popen(["wt.exe", "-w", "new", "-M", "--title", "Standard agent", "--suppressApplicationTitle", "-d", str(LEFT),
                      *ps(base + "; claude"), ";", "split-pane", "-V", "--title", "Ringfence agent",
                      "--suppressApplicationTitle", "-d", str(RIGHT), *ps(base)])
    for _ in range(80):
        time.sleep(0.25)
        new = hwnds("CASCADIA_HOSTING_WINDOW_CLASS") - before
        if new:
            h = new.pop()
            time.sleep(4)  # both shells draw; the left starts Claude Code
            focus(h)
            combo(ALT, LEFT_ARROW, ext=True)
            accept_trust()
            # off camera: start Claude once in the right folder so its trust dialog never shows in S01, then back to the prompt
            pane(h, "right")
            for line, wait in (("claude", 8), (None, 3), ("/exit", 4), ("Clear-Host", 1)):
                if line:
                    type_text(line, cps=60)
                    time.sleep(0.3)
                    combo(ENTER)
                else:
                    accept_trust()
                time.sleep(wait)
            return h
    sys.exit("Windows Terminal did not open")


def pane(h: int, side: str) -> None:
    focus(h)
    combo(ALT, LEFT_ARROW if side == "left" else RIGHT_ARROW, ext=True)


def say(h: int, side: str, text: str) -> float:
    """Pastes a line into one pane and presses Enter. Returns the epoch the line was sent."""
    paste(h, side, text)
    return time.time()


def paste(h: int, side: str, text: str) -> None:
    subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"], input=text.encode(), check=True)
    pane(h, side)
    combo(CTRL, V)
    time.sleep(0.6)
    combo(ENTER)


# -- Claude Code transcripts: when an agent has finished, or is waiting on its permission prompt -----------------------
def _entries(folder: Path, since: float) -> list[dict]:
    d = TRANSCRIPTS / re.sub(r"[^A-Za-z0-9]", "-", str(folder))  # Claude Code's own naming: C--Users-hprad-payday
    files = sorted(d.glob("*.jsonl"), key=lambda p: p.stat().st_mtime)
    out = []
    if files and files[-1].stat().st_mtime >= since - 5:
        for line in files[-1].read_text(encoding="utf-8", errors="replace").splitlines():
            try:
                e = json.loads(line)
                ts = datetime.fromisoformat(e["timestamp"].replace("Z", "+00:00")).timestamp()
            except (ValueError, KeyError, TypeError):
                continue
            if ts >= since:
                out.append(e)
    return out


def finished(folder: Path, since: float) -> bool:
    return any(e.get("type") == "assistant" and (e.get("message") or {}).get("stop_reason") == "end_turn"
               for e in _entries(folder, since))


def asking(folder: Path, since: float, tool: str) -> bool:
    return any(c.get("type") == "tool_use" and c.get("name", "").endswith(tool)
               for e in _entries(folder, since) if e.get("type") == "assistant"
               for c in (e.get("message") or {}).get("content") or [] if isinstance(c, dict))


# -- Ringfence and Airwallex state ------------------------------------------------------------------------------------
def latest() -> dict | None:
    r = httpx.get(f"{HOST}/approve/latest", headers={"x-enroll-key": env("RF_ENROLL_KEY")}, timeout=30)
    return r.json() if r.status_code == 200 else None


def view(wid: str) -> dict:
    r = httpx.get(f"{HOST}/approve/{wid}/view", timeout=30)
    return r.json() if r.status_code == 200 else {"state": f"http {r.status_code}"}


def until(what: str, fn, timeout: float = 300) -> object:
    t0 = time.monotonic()
    while time.monotonic() - t0 < timeout:
        try:
            v = fn()
        except httpx.HTTPError:
            v = None
        if v:
            return v
        time.sleep(1.5)
    raise TimeoutError(what)


def tom_transfer(batch: bool) -> str:
    """Tom's newest transfer on the playground account: the batch one (left agent) or the single one (Ringfence)."""
    _c, d = awx("GET", "/transfers?page_num=0&page_size=50", login_as=env("AWX_PLAYGROUND_ACCOUNT"))
    toms = [t for t in d.get("items", []) if "Tom" in str(((t.get("beneficiary") or {}).get("bank_details") or {}).get("account_name"))
            and bool(t.get("batch_transfer_id")) == batch]
    assert toms, f"no {'batch' if batch else 'single'} transfer to Tom on Airwallex"
    return max(toms, key=lambda t: t.get("created_at", ""))["id"]


# -- Chrome: the demo profile, a normal maximized window ----------------------------------------------------------------
def chrome_up() -> bool:
    try:
        return httpx.get(CDP + "/json/version", timeout=1).status_code == 200
    except httpx.HTTPError:
        return False


def open_chrome() -> None:
    """Reuses the running demo Chrome (a restart logs Airwallex out); else starts it maximized, with no size flags."""
    if chrome_up():
        return
    subprocess.Popen([CHROME, f"--user-data-dir={PROFILE}", "--remote-debugging-port=9222", "--no-first-run",
                      "--no-default-browser-check", "--start-maximized", "--hide-crash-restore-bubble", AWX_ACTIVITY])
    until("Chrome", chrome_up, 30)


def chrome_hwnd(page) -> int:
    page.bring_to_front()  # the window title is the active tab's
    page.evaluate("document.title = 'RFDEMO'")
    h = until("the Chrome window", lambda: next(iter(hwnds("Chrome_WidgetWin_1", "RFDEMO")), None), 10)
    page.reload()
    return h


def zoom_125(h: int, page, url: str) -> None:
    """Chrome remembers zoom per site: reset, then 110% -> 125%. Real keystrokes, so it is Chrome's own zoom."""
    page.goto(url)
    page.bring_to_front()
    focus(h)
    combo(CTRL, ZERO)
    combo(CTRL, PLUS)
    combo(CTRL, PLUS)


def show(h: int, page, url: str | None = None) -> None:
    if url:
        page.goto(url)
    page.bring_to_front()
    focus(h)
    time.sleep(1.5)


def activity_find(h: int, page, transfer_id: str) -> None:
    """Activity, searched by the full transfer id, then the one row opened (detail panel: recipient, ref)."""
    show(h, page, AWX_ACTIVITY)
    box = page.get_by_placeholder("Search by ID, type, or details")
    box.click()
    box.fill(transfer_id)
    box.press("Enter")
    time.sleep(4)
    try:
        page.get_by_text("Tom Reid").first.click(timeout=10000)
    except Exception as e:  # the search result already pairs the id; the detail panel is a bonus
        print("  (could not open the row:", type(e).__name__, ")")
    time.sleep(4)


def payees_find(h: int, page, text: str) -> None:
    show(h, page, AWX_TRANSFERS)
    page.get_by_role("tab", name="Payees").or_(page.get_by_role("link", name="Payees")).first.click()
    box = page.get_by_placeholder("Search payee name, account number, or nickname")
    box.click()
    box.press_sequentially(text, delay=60)
    time.sleep(5)


def hello(what: str) -> None:
    for _ in range(3):
        winsound.Beep(880, 250)
    print(f"\n>>> TOUCH WINDOWS HELLO NOW ({what}) <<<\n", flush=True)


# -- the take: one clip per shot, state saved after each, so a failure costs one shot, not the take -------------------
SHOTS = OUT / "shots"
STATE = OUT / "take_state.json"


class Camera:
    def __init__(self, path: Path):
        self.p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "gdigrab", "-framerate", "30",
                                   "-draw_mouse", "0", "-i", "desktop", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16",
                                   "-pix_fmt", "yuv420p", str(path)], stdin=subprocess.PIPE)
        self.t0, self.log = time.time(), (path.parent / (path.stem + "_events.jsonl")).open("w")
        time.sleep(1.5)  # pre-roll: each clip starts on a settled screen

    def mark(self, beat: str) -> None:
        t = round(time.time() - self.t0, 2)
        self.log.write(json.dumps({"beat": beat, "t": t}) + "\n")
        self.log.flush()
        print(f"  {t:7.1f}s  {beat}", flush=True)

    def stop(self) -> None:
        time.sleep(1)  # post-roll
        self.p.communicate(b"q", timeout=30)
        self.log.close()


class K:
    """Live handles (Playwright, windows) and this take's saved state."""
    st: dict = {}
    pw = ctx = awx_page = ap = None
    ch = wt = 0

    @classmethod
    def save(cls) -> None:
        STATE.write_text(json.dumps(cls.st, indent=1))


def connect_chrome() -> None:
    open_chrome()
    K.pw = sync_playwright().start()
    K.ctx = K.pw.chromium.connect_over_cdp(CDP).contexts[0]
    K.awx_page = next((pg for pg in K.ctx.pages if "airwallex.com" in pg.url), K.ctx.pages[0])
    K.ap = next((pg for pg in K.ctx.pages if "/approve/" in pg.url), None)
    K.awx_page.wait_for_load_state()
    assert "login" not in K.awx_page.url, "the Airwallex dashboard is logged out: log in in the demo Chrome, then rerun"
    K.ch = chrome_hwnd(K.awx_page)


def setup() -> None:
    subprocess.run(["uv", "run", "python", "demo/standard_mcp.py", "--setup"], cwd=ROOT, check=True, capture_output=True)
    subprocess.run(["uv", "run", "python", "demo/standard_mcp.py", "--tom", "12345601"], cwd=ROOT, check=True, capture_output=True)
    subprocess.run(["claude", "mcp", "remove", "ringfence", "-s", "local"], cwd=RIGHT, capture_output=True, check=False)
    if not EMAIL.exists() and (OUT / EMAIL.name).exists():
        shutil.move(OUT / EMAIL.name, EMAIL)
    assert EMAIL.exists(), "email_from_ana.txt is missing from ~/payday"
    assert httpx.get(f"{HOST}/api/play/info", timeout=20).json()["live"], "Ringfence live backend is off"
    old = json.loads(STATE.read_text()).get("wt") if STATE.exists() else None
    if old and u32.IsWindow(old):  # the last check's or take's terminal: its sessions must not leak into this take
        u32.PostMessageW(old, 0x10, 0, 0)  # WM_CLOSE
        until("the old terminal to close", lambda: not u32.IsWindow(old), 15)
    connect_chrome()
    for extra in [pg for pg in K.ctx.pages if pg is not K.awx_page]:
        extra.close()
    K.ap = None
    zoom_125(K.ch, K.awx_page, f"{HOST}/api/play/info")
    zoom_125(K.ch, K.awx_page, AWX_ACTIVITY)
    K.wt = open_terminal()
    K.st = {"wt": K.wt, "before": (latest() or {}).get("run_id"), "done": []}
    K.save()
    time.sleep(4)  # the left pane's Claude Code finishes drawing


def reattach() -> None:
    K.st = json.loads(STATE.read_text())
    K.wt = K.st["wt"]
    assert u32.IsWindow(K.wt), "the take's terminal is gone: start over with `take`"
    connect_chrome()


def passkey_approve(cam: Camera, wid: str, shot: str, what: str) -> None:
    """Rejects any quarantined bank change, then 'Approve with passkey'. Harsimar touches Windows Hello on the beep."""
    if K.ap is None or K.ap.is_closed():
        K.ap = K.ctx.new_page()
    K.ap.goto(f"{HOST}/approve/{wid}")
    K.ap.wait_for_selector("#banks > *")
    show(K.ch, K.ap)
    cam.mark(f"{shot} approval page")
    time.sleep(2.5)
    if K.ap.locator("[data-q]").count():
        K.ap.click("[data-q]")  # reject Ana's bank change
        until("email rejected", lambda: K.ap.locator("#go").is_enabled(), 30)
        cam.mark(f"{shot} rejected")
        time.sleep(1.5)
    K.ap.click("#go")
    cam.mark(f"{shot} passkey asked")
    hello(what)
    until(f"{what} approved", lambda: view(wid)["state"] == "READY", 240)
    cam.mark(f"{shot} approved")
    time.sleep(3)


def s01(cam):
    cam.mark("S01 two agents")
    time.sleep(6)
    cam.mark("S01 connect")
    paste(K.wt, "right", PROMPTS["connect"])
    time.sleep(3)
    cam.mark("S01 files")  # the timesheet and Ana's email, shown before the agent reads them
    paste(K.wt, "right", "Get-Content timesheet.csv; ''; Get-Content email_from_ana.txt")
    time.sleep(8)
    cam.mark("S01 claude")
    say(K.wt, "right", "claude")
    time.sleep(9)


def s02(cam):
    cam.mark("S02 run")
    t = say(K.wt, "right", PROMPTS["run"])
    cam.mark("S02 sent")
    wid = until("a new Ringfence run", lambda: (r := latest()) and r["run_id"] != K.st["before"] and r["run_id"], 300)
    K.st["wid"] = wid
    K.save()
    until("run 1 priced", lambda: view(wid)["state"] == "AWAITING_APPROVAL" and finished(RIGHT, t), 420)
    cam.mark("S02 result")
    time.sleep(5)


def s03(cam):
    cam.mark("S03 skip")
    t = say(K.wt, "right", PROMPTS["skip"])
    cam.mark("S03 sent")
    until("skip answered", lambda: finished(RIGHT, t), 240)
    cam.mark("S03 refused")
    time.sleep(5)


def s04(cam):
    passkey_approve(cam, K.st["wid"], "S04", "approve run 1")


def s05(cam):
    focus(K.wt)
    time.sleep(1)
    cam.mark("S05 send")
    t = say(K.wt, "right", PROMPTS["send"])
    cam.mark("S05 sent")
    until("run 1 sent", lambda: view(K.st["wid"])["state"] in ("RELEASED", "DONE") and finished(RIGHT, t), 300)
    cam.mark("S05 ids")
    time.sleep(6)


def s06(cam):
    tid = K.st["tom1"] = tom_transfer(batch=False)
    K.save()
    cam.mark("S06 activity")
    activity_find(K.ch, K.awx_page, tid)
    cam.mark("S06 detail")
    time.sleep(5)


def s07(cam):
    if EMAIL.exists():
        shutil.move(EMAIL, OUT / EMAIL.name)  # run 2 is a clean week; `wrap` puts it back
    focus(K.wt)
    time.sleep(1.5)
    cam.mark("S07 both prompts")
    t_left = say(K.wt, "left", PROMPTS["left2"])
    cam.mark("S07 left sent")
    t_right = say(K.wt, "right", PROMPTS["right2"])
    cam.mark("S07 right sent")
    until("left asks to submit", lambda: asking(LEFT, t_left, "submit_batch"), 300)
    time.sleep(3)  # the permission prompt draws
    cam.mark("S07 left prompt")
    seen = (K.st["before"], K.st.get("wid"))
    wid2 = until("run 2", lambda: (r := latest()) and r["run_id"] not in seen and r["run_id"], 300)
    K.st["wid2"] = wid2
    K.save()
    until("run 2 priced", lambda: view(wid2)["state"] == "AWAITING_APPROVAL" and finished(RIGHT, t_right), 420)
    cam.mark("S07 right link")
    time.sleep(5)


def s08(cam):
    passkey_approve(cam, K.st["wid2"], "S08", "approve run 2")


def s09(cam):
    subprocess.run(["uv", "run", "python", "demo/swap_tom.py", "99999901"], cwd=ROOT, check=True, capture_output=True)
    K.st["swapped"] = True
    K.save()
    cam.mark("S09 payees")
    payees_find(K.ch, K.awx_page, "99999901")
    cam.mark("S09 both toms")
    time.sleep(5)


def s10(cam):
    pane(K.wt, "left")
    time.sleep(2)
    cam.mark("S10 left approve")
    combo(ENTER)  # "Yes" is the highlighted answer
    t = time.time()
    until("left submitted", lambda: finished(LEFT, t), 300)
    cam.mark("S10 submitted")
    time.sleep(4)
    cam.mark("S10 where")
    t = say(K.wt, "left", PROMPTS["where"])
    cam.mark("S10 where sent")
    until("left where + cancel", lambda: finished(LEFT, t), 300)
    cam.mark("S10 results")
    time.sleep(6)


def s11(cam):
    focus(K.wt)
    time.sleep(1)
    cam.mark("S11 right send")
    t = say(K.wt, "right", PROMPTS["send"])
    cam.mark("S11 sent")
    until("run 2 held", lambda: view(K.st["wid2"])["state"] == "HELD" and finished(RIGHT, t), 300)
    cam.mark("S11 held")
    time.sleep(7)


def s12(cam):
    tid = K.st["tom2"] = tom_transfer(batch=True)
    K.save()
    cam.mark("S12 activity")
    activity_find(K.ch, K.awx_page, tid)
    cam.mark("S12 detail")
    time.sleep(5)
    show(K.ch, K.awx_page, AWX_ACTIVITY)
    cam.mark("S12 list")
    time.sleep(5)


ORDER = [("S01", s01), ("S02", s02), ("S03", s03), ("S04", s04), ("S05", s05), ("S06", s06),
         ("S07", s07), ("S08", s08), ("S09", s09), ("S10", s10), ("S11", s11), ("S12", s12)]


def shoot(start: str | None) -> None:
    SHOTS.mkdir(exist_ok=True)
    names = [n for n, _ in ORDER]
    i = names.index(start) if start else next((k for k, n in enumerate(names) if n not in K.st["done"]), len(names))
    for name, fn in ORDER[i:]:
        print(f"-- {name}", flush=True)
        cam = Camera(SHOTS / f"{name}.mkv")
        try:
            fn(cam)
        finally:
            cam.stop()
        K.st["done"] = [n for n in K.st["done"] if n != name] + [name]
        K.save()
    print("all shots done")
    wrap()


def wrap() -> None:
    """Puts the world back after the shoot: left Tom's account, Ana's email, the taskbar."""
    st = json.loads(STATE.read_text()) if STATE.exists() else {}
    if st.get("swapped"):
        subprocess.run(["uv", "run", "python", "demo/swap_tom.py", "--left", "12345601"], cwd=ROOT, check=True, capture_output=True)
        st["swapped"] = False
        STATE.write_text(json.dumps(st, indent=1))
    if not EMAIL.exists() and (OUT / EMAIL.name).exists():
        shutil.move(OUT / EMAIL.name, EMAIL)
    taskbar_autohide(False)
    print("wrapped: left Tom reset, email back, taskbar shown")


def main(cmd: str, arg: str | None) -> None:
    if cmd == "wrap":
        return wrap()
    taskbar_autohide(True)
    try:
        if cmd == "check":
            setup()
            cam = Camera(OUT / "check.mkv")
            time.sleep(4)
            cam.stop()
        elif cmd == "take":
            setup()
            shoot(None)
        else:
            reattach()
            shoot(arg)
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}  (state kept in take_state.json; fix, then `resume`)", flush=True)
        raise
    finally:
        if K.pw:
            K.pw.stop()


if __name__ == "__main__":
    a = sys.argv[1:]
    if not a or a[0] not in ("check", "take", "resume", "wrap"):
        sys.exit(__doc__)
    main(a[0], a[1] if len(a) > 1 else None)
