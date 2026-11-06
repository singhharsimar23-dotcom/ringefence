"""Screenshots of REAL desktop windows (title bar, tabs, bookmarks and all) for the film. Nothing cropped, nothing headless.
Opens each thing in the real app (Chrome, VS Code, PowerShell), brings the window up, grabs its on-screen rectangle.
Writes video/public/real/<name>.png (gitignored: personal screens). Usage: uv run --with pillow python video/realshots.py [name ...]"""
import ctypes
import json
import subprocess
import sys
import time
from ctypes import wintypes
from pathlib import Path

from PIL import ImageGrab

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parent
OUT = ROOT / "public/real"
IDE = str(Path.home() / "AppData/Local/Programs/Antigravity IDE/bin/antigravity-ide.cmd")  # the IDE Harsimar actually works in
U = ctypes.windll.user32
ctypes.windll.shcore.SetProcessDpiAwareness(2)  # real pixel coordinates on a scaled display


def windows() -> list[tuple[int, str]]:
    found = []

    def cb(h, _):
        if U.IsWindowVisible(h):
            n = U.GetWindowTextLengthW(h)
            if n:
                b = ctypes.create_unicode_buffer(n + 1)
                U.GetWindowTextW(h, b, n + 1)
                found.append((h, b.value))
        return True
    U.EnumWindows(ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)(cb), 0)
    return found


def find(part: str, wait: float = 20) -> int:
    end = time.time() + wait
    while time.time() < end:
        for h, title in windows():
            if part.lower() in title.lower():
                return h
        time.sleep(0.5)
    raise SystemExit(f"no window with '{part}' in its title; open: {[t for _, t in windows()][:15]}")


def grab(h: int, name: str) -> None:
    if U.IsIconic(h):
        U.ShowWindow(h, 9)  # restore only if minimised; SW_RESTORE would un-maximise
    U.keybd_event(0x12, 0, 0, 0); U.keybd_event(0x12, 0, 2, 0)  # an Alt tap lets SetForegroundWindow through
    U.SetForegroundWindow(h)
    time.sleep(1.2)
    r = wintypes.RECT()
    ctypes.windll.dwmapi.DwmGetWindowAttribute(h, 9, ctypes.byref(r), ctypes.sizeof(r))  # frame without the invisible resize border
    OUT.mkdir(parents=True, exist_ok=True)
    box = (max(r.left, 0), max(r.top, 0), min(r.right, U.GetSystemMetrics(0)), min(r.bottom, U.GetSystemMetrics(1)))  # a maximised window overhangs the screen
    ImageGrab.grab(bbox=box, all_screens=True).save(OUT / f"{name}.png")
    print(name, box)


def chrome(name: str, url: str, title: str, settle: float = 7) -> None:
    subprocess.Popen(["cmd", "/c", "start", "", "chrome", url])
    time.sleep(settle)
    grab(find(title), name)


def code(name: str, target: str, title: str, first: bool) -> None:
    subprocess.Popen(["cmd", "/c", IDE, "-n" if first else "-r", "-g", str(REPO / target)])
    time.sleep(4)
    h = find(title)
    U.ShowWindow(h, 3)  # maximised, so the long lines are not cut off
    time.sleep(1)
    grab(h, name)


def term(name: str, cmd: str, tag: str, wait: float) -> None:
    done = OUT / f".{name}.done"
    done.unlink(missing_ok=True)
    ps = f"$Host.UI.RawUI.WindowTitle='{tag}'; cd '{REPO}'; $env:PYTHONIOENCODING='utf-8'; {cmd}; New-Item -Force '{done}' | Out-Null"
    subprocess.Popen(["cmd", "/c", "start", "", "powershell", "-NoExit", "-Command", ps])
    end = time.time() + wait
    while not done.exists() and time.time() < end:
        time.sleep(1)
    time.sleep(1)
    grab(find(tag), name)
    done.unlink(missing_ok=True)


A, B, C, P = "acct_Y5VX3QXWNSyiun0cbai15A", "acct_FG3wEt9HNg29C0zhpelKHg", "acct_8bUTqZJePIG80-z_-xiutw", "acct_NIym7HZZOOOqBCE7F6LkMA"
PAIRS = [(A, B, "northwind", "kestrel"), (A, C, "northwind", "harbour"), (B, C, "kestrel", "harbour"), (C, A, "harbour", "northwind"), (C, P, "harbour", "platform")]
ISO = "; ".join(f"Write-Host ''; Write-Host '# {x} token -> {y} account' -Fo Yellow; Write-Host 'PS> python scripts/awx.py GET /balances/current --as {a} --obo {b}'; "
                f"python scripts/awx.py GET /balances/current --as {a} --obo {b}" for a, b, x, y in PAIRS)


def main() -> None:
    f = json.loads((ROOT / "src/facts.json").read_text(encoding="utf-8"))
    pull = f["metal_pull"][0]
    ref = {r["code"]: r["tx"] for r in f["metal_refused"]}
    tx = "https://testnet.metalntwx.com/tx/"
    shots = {
        "tx_bind": lambda: chrome("tx_bind", tx + pull["bind_tx"], "Chrome"),
        "tx_pull": lambda: chrome("tx_pull", tx + pull["tx"], "Chrome"),
        "tx_over": lambda: chrome("tx_over", tx + ref["mandate_cap_exceeded"], "Chrome"),
        "tx_poison": lambda: chrome("tx_poison", tx + ref["mandate_payee_not_listed"], "Chrome"),
        "app_proof": lambda: chrome("app_proof", "https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com/#proof", "Chrome", 10),
        "code_mandate": lambda: code("code_mandate", "ringfence/metal.py:103", "metal.py", True),
        "code_gate": lambda: code("code_gate", "ringfence/gate.py:87", "gate.py", False),
        "code_login": lambda: code("code_login", "ringfence/awx.py:80", "awx.py", False),
        "code_once": lambda: code("code_once", "ringfence/executor.py:211", "executor.py", False),
        "code_quarantine": lambda: code("code_quarantine", "ringfence/beneficiaries.py:117", "beneficiaries.py", False),
        "code_hash": lambda: code("code_hash", "ringfence/gate.py:167", "gate.py", False),
        "code_mcp": lambda: code("code_mcp", "ringfence/mcp_server.py:1", "mcp_server.py", False),
        "code_gauntlet": lambda: code("code_gauntlet", "docs/gauntlet/results.json:1", "results.json", False),
        # read-only cross-tenant GETs (recon_isolation.py would create a deposit on Harbour and spoil the demo state)
        "term_isolation": lambda: term("term_isolation", ISO, "rf-isolation", 180),
        "term_tests": lambda: term("term_tests", "uv run pytest -q", "rf-tests", 600),
    }
    for n in sys.argv[1:] or shots:
        shots[n]()


if __name__ == "__main__":
    main()
