"""S17/S18: Airwallex Activity in the user's Chrome (already logged in, maximized, tabs: Approve payroll | Airwallex).

    python video/dd_shoot_awx.py S17   # week 1: the run's three payouts, Tom's opens: Settled
    python video/dd_shoot_awx.py S18   # close: the standard agent's batch (Settled), then this run's reference: nothing
"""
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import dd_desk as d  # noqa: E402

ACT = "https://www.sandbox.airwallex.com/app/business-accounts/cash/226c9190-2262-44a9-a7c3-edce4ced52a8/activity"
OUT = Path(__file__).parent / "out/dd/manual"


def clip(s: str) -> None:
    subprocess.run(["powershell", "-NoProfile", "-Command", "Set-Clipboard -Value $input"], input=s.encode(), check=True)


def go(url: str) -> None:
    d.key(0x11, 0x4C); clip(url); d.key(0x11, 0x56); time.sleep(0.2); d.key(0x0D); time.sleep(16)


def typ(s: str) -> None:
    for ch in s:
        u = ord(ch)
        d.u32.keybd_event(0, u, 4, 0); d.u32.keybd_event(0, u, 6, 0)  # KEYEVENTF_UNICODE
        time.sleep(0.11)


def shoot(name: str) -> None:
    h = next(w[0] for w in d.windows("Chrome_WidgetWin_1") if "Airwallex" in w[2] or "Approve payroll" in w[2])
    d.front(h)
    go(f"{ACT}?search={'_39V' if name == 'S17' else 'I3NK'}")
    d.glide(1500, 900, 0.3); time.sleep(1.5)
    cam = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "gdigrab", "-framerate", "30", "-draw_mouse", "1",
                            "-i", "desktop", "-c:v", "libx264", "-preset", "ultrafast", "-crf", "16", "-pix_fmt", "yuv420p",
                            str(OUT / f"{name}.mkv")], stdin=subprocess.PIPE)
    t0, marks = time.time(), {}
    m = lambda k: marks.__setitem__(k, round(time.time() - t0, 2))
    time.sleep(3.0)
    m("to_row"); d.glide(1210, 716, 1.0); time.sleep(0.35); d.click(); m("panel")
    time.sleep(0.2); d.glide(1560, 760, 0.9); time.sleep(4.0)
    if name == "S18":
        m("close"); d.glide(1813, 648, 0.9); time.sleep(0.25); d.click(); time.sleep(0.8)
        m("to_search"); d.glide(760, 578, 0.9); time.sleep(0.2); d.click(); time.sleep(0.3)
        d.key(0x11, 0x41); time.sleep(0.25); typ("PT4W"); m("typed"); time.sleep(0.6)
        d.glide(1000, 760, 0.9); time.sleep(4.5)
    cam.communicate(b"q", timeout=10)
    print(name, marks)


if __name__ == "__main__":
    if sys.argv[1:] not in (["S17"], ["S18"]):
        sys.exit(__doc__)
    shoot(sys.argv[1])
