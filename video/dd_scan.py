"""Flags IDE-teal frames and listing hard cuts in the preview: python video/dd_scan.py [file]"""
import subprocess
import sys
import numpy as np

W, H = 160, 90
src = sys.argv[1] if sys.argv[1:] else "video/out/demo_day_preview.mp4"
raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", src, "-vf", f"fps=15,scale={W}:{H}:flags=area",
                      "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
f = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3).astype(float)
reg = f[:, 25:50, 16:72, :].mean((1, 2))
bad = [round(i / 15, 2) for i in range(len(f)) if reg[i][1] - reg[i][0] > 22]
print(f"{len(f) / 15:.1f}s, IDE-teal frames: {len(bad)}", bad[:30])
d = np.abs(np.diff(f, axis=0)).mean((1, 2, 3))
print("big changes at", [round((i + 1) / 15, 2) for i in np.nonzero(d > 10)[0]])
