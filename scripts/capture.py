"""Clean screen clips for the video: Playwright drives headed Chromium at 1440x900 while ffmpeg (gdigrab, Windows) records the screen.
One clip per beat lands in var/capture/<beat>.mp4. Usage: uv run --with playwright python scripts/capture.py --url URL [--beat NAME]
The window sits at the top-left so the capture region matches it. Nothing here touches money: it only scrolls the landing page."""
from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

OUT = Path(__file__).resolve().parent.parent / "var" / "capture"
W, H = 1440, 900
BEATS = {  # beat -> (scene ids to scroll to, seconds on each)
    "landing": (["top", "email", "why"], 6),
    "proof": (["how", "isolation", "storm", "proof", "ledger"], 7),
    "real": (["short", "real", "try"], 6),
}


def record(page, name: str, scenes: list[str], hold: int) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    dst = OUT / f"{name}.mp4"
    ff = subprocess.Popen(["ffmpeg", "-y", "-f", "gdigrab", "-framerate", "60", "-offset_x", "0", "-offset_y", "0",
                           "-video_size", f"{W}x{H}", "-i", "desktop", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p", str(dst)],
                          stdin=subprocess.PIPE, stderr=subprocess.DEVNULL)
    try:
        time.sleep(1.5)
        for sid in scenes:
            page.evaluate(f"document.getElementById('{sid}').scrollIntoView({{behavior: 'smooth'}})")
            time.sleep(hold)
    finally:
        ff.communicate(b"q", timeout=30)  # ffmpeg finalises the file on "q"
    return dst


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--beat", choices=sorted(BEATS))
    a = ap.parse_args()
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=False, args=["--window-position=0,0", f"--window-size={W},{H + 120}"])
        page = b.new_context(viewport={"width": W, "height": H}).new_page()
        for name, (scenes, hold) in BEATS.items():
            if a.beat and a.beat != name:
                continue
            page.goto(a.url.rstrip("/") + "/")
            page.wait_for_timeout(2500)
            print("recorded", record(page, name, scenes, hold))
        b.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
