"""Tiles frames of the preview at film times, labelled:  python video/dd_qc.py t1 t2 ... [--out name]"""
import subprocess, sys
from PIL import Image, ImageDraw
a = sys.argv[1:]
out = a[a.index("--out") + 1] if "--out" in a else "qc"
ts = [float(x) for x in a if x.replace(".", "").isdigit()]
cols, sw, sh = 4, 480, 270
im = Image.new("RGB", (sw * cols, sh * ((len(ts) + cols - 1) // cols)))
for i, t in enumerate(ts):
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t}", "-i", "video/out/demo_day_preview.mp4", "-frames:v", "1",
                          "-vf", f"scale={sw}:{sh}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    if len(raw) < sw * sh * 3: continue
    b = Image.frombytes("RGB", (sw, sh), raw); ImageDraw.Draw(b).text((4, 2), f"{t:.2f}", fill=(255, 255, 0))
    im.paste(b, (sw * (i % cols), sh * (i // cols)))
im.save(f"C:/Users/hprad/AppData/Local/Temp/v/{out}.png")
