"""Desktop helpers for the extra Demo Day screen shots (S16+): windows at exact rects, smooth real cursor moves, clicks.

    python video/dd_desk.py terminal      # the two-pane terminal at the S0/S1 rect, both panes on the Claude welcome
    python video/dd_desk.py rect          # print visible windows and their rects
"""
import base64
import ctypes
import ctypes.wintypes as W
import math
import subprocess
import sys
import time
from pathlib import Path

u32 = ctypes.windll.user32
u32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
dwm = ctypes.windll.dwmapi
LEFT, RIGHT = Path.home() / "payday-std2", Path.home() / "payday"
TERM = (128, 128, 1610, 888)  # visible terminal frame in S0 and S1 (x0, y0, x1, y1), measured off S1 at 95 s


def windows(cls: str = "", title_has: str = "") -> list[tuple[int, str, str]]:
    out = []

    @ctypes.WINFUNCTYPE(W.BOOL, W.HWND, W.LPARAM)
    def cb(h, _):
        c, t = ctypes.create_unicode_buffer(64), ctypes.create_unicode_buffer(256)
        u32.GetClassNameW(h, c, 64)
        u32.GetWindowTextW(h, t, 256)
        if u32.IsWindowVisible(h) and t.value and (not cls or c.value == cls) and title_has in t.value:
            out.append((h, c.value, t.value))
        return True
    u32.EnumWindows(cb, 0)
    return out


def frame(h: int) -> tuple[int, int, int, int]:
    """The visible frame (DWM extended bounds), without the invisible resize border."""
    r = W.RECT()
    dwm.DwmGetWindowAttribute(h, 9, ctypes.byref(r), ctypes.sizeof(r))
    return r.left, r.top, r.right, r.bottom


def place(h: int, x0: int, y0: int, x1: int, y1: int) -> None:
    """Moves the window so its visible frame is exactly (x0, y0, x1, y1)."""
    u32.ShowWindow(h, 9)  # restore, never maximized
    for _ in range(3):
        r = W.RECT()
        u32.GetWindowRect(h, ctypes.byref(r))
        f = frame(h)
        dl, dt, dr, db = f[0] - r.left, f[1] - r.top, r.right - f[2], r.bottom - f[3]
        u32.SetWindowPos(h, 0, x0 - dl, y0 - dt, (x1 - x0) + dl + dr, (y1 - y0) + dt + db, 0x0004 | 0x0010)
        time.sleep(0.4)


def front(h: int) -> None:
    for _ in range(8):
        fg = u32.GetForegroundWindow()
        if fg == h:
            return
        ft, me = u32.GetWindowThreadProcessId(fg, None), ctypes.windll.kernel32.GetCurrentThreadId()
        u32.AttachThreadInput(me, ft, True)
        u32.BringWindowToTop(h)
        u32.SetForegroundWindow(h)
        u32.AttachThreadInput(me, ft, False)
        time.sleep(0.25)
    raise RuntimeError("window would not come to the front")


def pos() -> tuple[int, int]:
    p = W.POINT()
    u32.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def glide(x: int, y: int, secs: float = 0.6) -> None:
    """Moves the real cursor along a slight arc with ease-in-out, 120 steps a second, like a hand on a mouse."""
    x0, y0 = pos()
    n = max(2, int(secs * 120))
    bend = 0.08 * math.hypot(x - x0, y - y0)
    for i in range(1, n + 1):
        t = i / n
        e = t * t * (3 - 2 * t)
        off = bend * math.sin(math.pi * e)
        dx, dy = x - x0, y - y0
        L = math.hypot(dx, dy) or 1
        u32.SetCursorPos(round(x0 + dx * e - dy / L * off), round(y0 + dy * e + dx / L * off))
        time.sleep(secs / n)


def click() -> None:
    u32.mouse_event(2, 0, 0, 0, 0)
    time.sleep(0.07)
    u32.mouse_event(4, 0, 0, 0, 0)


def key(*vks: int) -> None:
    for v in vks:
        u32.keybd_event(v, 0, 0, 0)
    for v in reversed(vks):
        u32.keybd_event(v, 0, 2, 0)
    time.sleep(0.15)


def ps(cmd: str) -> list[str]:
    return ["powershell.exe", "-NoLogo", "-NoExit", "-EncodedCommand", base64.b64encode(cmd.encode("utf-16-le")).decode()]


def terminal() -> int:
    """Same launch as demo/director.py open_terminal, but both panes start Claude Code and the window is not maximized."""
    base = ("Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue; Get-ChildItem Env:CLAUDE* | Remove-Item; "
            "function prompt { 'acme > ' }; Clear-Host; claude --model sonnet")
    before = {w[0] for w in windows("CASCADIA_HOSTING_WINDOW_CLASS")}
    subprocess.Popen(["wt.exe", "-w", "new", "--title", "Standard agent", "--suppressApplicationTitle", "-d", str(LEFT),
                      *ps(base), ";", "split-pane", "-V", "--title", "Ringfence agent", "--suppressApplicationTitle",
                      "-d", str(RIGHT), *ps(base)])
    for _ in range(80):
        time.sleep(0.25)
        new = {w[0] for w in windows("CASCADIA_HOSTING_WINDOW_CLASS")} - before
        if new:
            h = new.pop()
            time.sleep(1)
            place(h, *TERM)
            return h
    sys.exit("Windows Terminal did not open")


if __name__ == "__main__":
    if sys.argv[1:] == ["terminal"]:
        print(terminal())
    elif sys.argv[1:] == ["rect"]:
        for h, c, t in windows():
            print(h, c, t[:50], frame(h))
    else:
        sys.exit(__doc__)
