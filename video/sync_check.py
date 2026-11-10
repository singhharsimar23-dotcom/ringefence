"""Lip-sync check for video/public/loom_cut.mp4: for sample words, the face frame shown at the word's film time must be the raw
Loom frame at the word's original time. Prints the offset (in raw frames) where the best-matching raw frame sits; 0 = in sync."""
import json
import subprocess
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
SRC, CUT = ROOT / "var/loom_v10.mp4", ROOT / "video/public/loom_cut.mp4"
FACE = "crop=470:470:25:303,scale=48:48,format=gray"  # the bubble region (after the switch); before it the face fills the frame


def frames(path: Path, t: float, n: int, vf: str) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", f"{max(t, 0):.3f}", "-i", str(path), "-frames:v", str(n), "-vf", vf,
                          "-f", "rawvideo", "-"], capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(-1, 48 * 48).astype(np.float32)


def main():
    d = json.loads((CUT.with_name("words.json")).read_text(encoding="utf-8"))
    words = [w for w in d["words"] if w["s"] > d["switch"] + 1]
    worst = 0
    for w in words[:: max(1, len(words) // 14)]:
        out = frames(CUT, w["s"], 1, FACE)[0]
        src = frames(SRC, w["o"] - 20 / 30, 41, "fps=30," + FACE)
        err = np.abs(src - out).mean(axis=1)
        k = int(err.argmin()) - 20
        worst = max(worst, abs(k))
        print(f"film {w['s']:7.2f}s  raw {w['o']:7.2f}s  offset {k:+d} frames  (match {err.min():.1f} vs median {np.median(err):.1f})")
    print(f"worst offset: {worst} frames")


if __name__ == "__main__":
    main()
