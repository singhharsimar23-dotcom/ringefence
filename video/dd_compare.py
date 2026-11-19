"""Builds docs/img/mcp-compare.png for the README: the standard agent (left) and the Ringfence agent (right), after Tom's
bank account was changed on Airwallex. Same composite as the film: the right pane is the reshoot (S15), the left pane is
the earlier take (S8) laid into the same window, so the image is two takes of the same demo.

    python video/dd_compare.py
"""
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

V = Path(__file__).resolve().parent
MAN = V / "out" / "dd" / "manual"
OUT = V.parent / "docs" / "img" / "mcp-compare.png"
TMP = V / "out" / "dd" / "film"
WIN = (16, 182, 1778, 880)  # the two panes of the terminal window (title bar and taskbar cropped off)
OLD, NEW = (203, 888, 8, 887), (182, 867, 17, 896)  # (y0, y1, x0, x1): the old take's left pane -> the reshoot window


def grab(clip: str, t: float) -> Image.Image:
    p = TMP / f"cmp_{clip}_{t}.png"
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", str(t), "-i", str(MAN / f"{clip}.mkv"),
                    "-frames:v", "1", str(p)], check=True)
    return Image.open(p).convert("RGB")


def font(size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype("C:/Windows/Fonts/segoeui.ttf", size)


right, left = grab("S15", 30.5), grab("S8", 105.0)
pane = left.crop((OLD[2], OLD[0], OLD[3], OLD[1]))
right.paste(pane, (NEW[2], NEW[0]))
win = right.crop(WIN)
bar = 84
img = Image.new("RGB", (win.width, win.height + bar), (11, 11, 12))
img.paste(win, (0, bar))
d = ImageDraw.Draw(img)
mid = win.width // 2
for x, head, sub in ((24, "Standard agent", "Airwallex API tools. Approved a batch of IDs; Tom's account was changed before it sent."),
                     (mid + 24, "Ringfence agent", "Ringfence MCP. Re-read every payee before sending; the run was held, nothing sent.")):
    d.text((x, 12), head, font=font(30), fill=(245, 245, 245))
    d.text((x, 50), sub, font=font(18), fill=(160, 160, 165))
OUT.parent.mkdir(parents=True, exist_ok=True)
img.save(OUT, optimize=True)
print("wrote", OUT, img.size)
