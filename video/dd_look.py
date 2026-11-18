"""Tiles crops of one clip at several times, labelled:  python video/dd_look.py CLIP x,y,w,h t0 t1 step [out]"""
import subprocess, sys
from PIL import Image, ImageDraw
clip, reg, t0, t1, st = sys.argv[1], [int(v) for v in sys.argv[2].split(",")], *map(float, sys.argv[3:6])
out = sys.argv[6] if len(sys.argv) > 6 else "C:/Users/hprad/AppData/Local/Temp/v/look.png"
x, y, w, h = reg
ts, t = [], t0
while t <= t1 + 1e-6:
    ts.append(round(t, 2)); t += st
cols = 4; sw = 480; sh = int(h * sw / w)
im = Image.new("RGB", (sw * cols, sh * ((len(ts) + cols - 1) // cols)))
for i, t in enumerate(ts):
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", str(t), "-i", f"video/out/dd/manual/{clip}.mkv", "-frames:v", "1",
                          "-vf", f"crop={w}:{h}:{x}:{y},scale={sw}:{sh}", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
    if len(raw) < sw * sh * 3: continue
    a = Image.frombytes("RGB", (sw, sh), raw); ImageDraw.Draw(a).text((4, 2), str(t), fill=(255, 255, 0))
    im.paste(a, (sw * (i % cols), sh * (i // cols)))
im.save(out)
