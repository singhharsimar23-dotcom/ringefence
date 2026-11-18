"""Contact sheets of the preview: one still per segment (its midpoint) in video/out/dd/qc/sheetN.png."""
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import dd_render as d

Q = d.DD / "qc"
Q.mkdir(exist_ok=True)
src = Path(__file__).parent / "out" / "demo_day_preview.mp4"
segs = d.plan()
offs = [float(a) for a in sys.argv[1:2]] or [0.5]  # fraction of the way into each segment
for s in segs:
    t = (s["f0"] + (s["f1"] - s["f0"]) * offs[0]) / 30
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.3f}", "-i", str(src),
                    "-frames:v", "1", "-vf", "scale=640:-1", str(Q / f"{s['name']}.png")], check=True)
names = [s["name"] for s in segs]
for i in range(0, len(names), 6):
    ch = names[i:i + 6]
    ins = sum([["-i", str(Q / f"{n}.png")] for n in ch], [])
    fl = "".join(f"[{k}:v]drawtext=fontfile='C\:/Windows/Fonts/arialbd.ttf':text='{n}':x=6:y=6:fontsize=24:fontcolor=yellow:box=1:boxcolor=black@0.7[t{k}];" for k, n in enumerate(ch))
    fl += "".join(f"[t{k}]" for k in range(len(ch))) + f"xstack=inputs={len(ch)}:layout=" + "|".join(f"{(k % 3) * 640}_{(k // 3) * 360}" for k in range(len(ch))) + "[o]"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *ins, "-filter_complex", fl, "-map", "[o]", "-frames:v", "1", str(Q / f"sheet{i // 6}.png")], check=True)
