"""Tiles full frames (or one region) of several clip@time points:  python video/dd_peek.py S0@18 S1@94.9 ... [--reg x,y,w,h] [--cols 3]"""
import subprocess, sys
from PIL import Image, ImageDraw
a = sys.argv[1:]
reg = [int(v) for v in a[a.index("--reg") + 1].split(",")] if "--reg" in a else [0, 0, 1920, 1020]
cols = int(a[a.index("--cols") + 1]) if "--cols" in a else 3
pts = [p for p in a if "@" in p]
x, y, w, h = reg; sw = 1920 // cols; sh = int(h * sw / w)
im = Image.new("RGB", (sw * cols, sh * ((len(pts) + cols - 1) // cols)))
for i, p in enumerate(pts):
    c, t = p.split("@")
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", t, "-i", f"video/out/dd/manual/{c}.mkv", "-frames:v", "1",
                          "-vf", f"crop={w}:{h}:{x}:{y},scale={sw}:{sh}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    if len(raw) < sw * sh * 3: continue
    b = Image.frombytes("RGB", (sw, sh), raw); ImageDraw.Draw(b).text((4, 2), p, fill=(255, 255, 0))
    im.paste(b, (sw * (i % cols), sh * (i // cols)))
im.save("C:/Users/hprad/AppData/Local/Temp/v/peek.png")
