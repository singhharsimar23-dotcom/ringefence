"""Renders the Demo Day film from the manual full-desktop clips in video/out/dd/manual. Hard cuts only.

    python video/dd_render.py preview   # video/out/demo_day_preview.mp4, 1280x720
    python video/dd_render.py final     # video/out/demo_day.mp4, 1920x1080, crf 18 slow

The face/voice track (face_cfr.mov, 1.79 s to the end) plays straight through, never cut or frozen. Only the screen
changes, on the beat boundaries of cut_plan.json. The taskbar is cropped off every clip; the face is a bubble in the
bottom-right corner, or large and centred over darkened site footage for the open and the close. No labels, no motion.
"""
import subprocess
import sys
from pathlib import Path

from PIL import Image, ImageDraw

DD = Path(__file__).resolve().parent / "out" / "dd"
MAN = DD / "manual"
FACE = DD / "face_cfr.mov"
FPS = 30
CX, CY, R = 260, 582, 246  # the face circle in face_cfr.mov, kept 4 px inside Loom's edge
BIG, SMALL = 720, 170
BG = "0x0b0b0c"
VOICE = "highpass=f=80,afftdn=nf=-25,acompressor=threshold=-18dB:ratio=3:attack=5:release=80,loudnorm=I=-16:TP=-1.5:LRA=11"

# Beat starts in face_cfr.mov (cut_plan.json src_start); each screen segment runs to the next one.
START, END = 1.79, 198.5
# (beat start, kind, pieces). A piece is (clip, in) or (clip, in, seconds); the last piece takes the rest of the beat.
# ("freeze", clip, t, seconds) holds one frame. kind "site" = darkened, with the big face.
SEGS = [
    (1.79, "site", [("S11", 4.5)]),                                             # open
    (18.635, "term", [("S1", 89.7, 5.2), ("freeze", "S1", 94.9)]),              # setup_a: two agents, idle
    (29.811, "term", [("S0", 6.1)]),                                            # setup_b: the one-line connect
    (35.685, "term", [("freeze", "S1", 94.9, 6.53), ("S1", 94.9)]),             # pay_a: prompt typed
    (46.865, "term", [("S1", 124.7)]),                                          # pay_b: agent works
    (61.747, "term", [("S1", 139.6, 10.6), ("freeze", "S1", 150.1)]),                                          # pay_c: table, Ana flagged, link
    (77.396, "term", [("S2", 10.8)]),                                           # skip_a: skip prompt typed
    (81.188, "term", [("S2", 18.0)]),                                           # skip_b: refusal
    (86.522, "chrome", [("S3", 24.0, 0.85), ("S3", 32.0)]),                     # approve: reject, approve
    (88.22, "chrome", [("S3", 38.2)]),                                          # send: Approved
    (89.538, "chromeL", [("S10", 5.0)]),                                         # paid: Airwallex activity
    (92.854, "chrome", [("S12", 6.0)]),                                        # hard_a
    (105.681, "term", [("S13", 42.0)]),                                         # next: both prompts
    (108.405, "term", [("S8", 24.6)]),                                          # left: batch
    (119.793, "chrome", [("S14", 13.4)]),                                       # pk2: passkey
    (121.72, "chrome", [("S7", 11.7)]),                                         # swap: Tom's account changed
    (127.539, "term", [("S8", 36.2)]),                                          # lapp: left approve prompt
    (128.933, "term", [("S8", 61.5)]),                                          # lres: paid to new account, cancel 401
    (143.225, "term", [("S15", 11.3)]),                                         # rsend_a: send typed
    (145.027, "term", [("S15", 21.0)]),                                         # rsend_b: HELD
    (154.755, "chrome", [("S11", 12.5)]),                                       # lesson: the playground
    (169.814, "chromeL", [("S10", 8.0)]),                                        # close_a: Airwallex activity
    (176.541, "site", [("S12", 5.0)]),                                          # close
]
NAMES = ["open", "setup_a", "setup_b", "pay_a", "pay_b", "pay_c", "skip_a", "skip_b", "approve", "send", "paid",
         "hard_a", "next", "left", "pk2", "swap", "lapp", "lres", "rsend_a", "rsend_b", "lesson", "close_a", "close"]


def mask(size: int) -> Path:
    p = DD / f"mask{size}.png"
    k = 4  # supersampled, so the circle edge is antialiased
    im = Image.new("L", (size * k, size * k), 0)
    ImageDraw.Draw(im).ellipse((0, 0, size * k - 1, size * k - 1), fill=255)
    im.resize((size, size), Image.LANCZOS).save(p)
    return p


def plan() -> list[dict]:
    """Per segment: name, kind, film frames, and its pieces with whole-frame lengths."""
    bounds = [s[0] for s in SEGS] + [END]
    out, f0 = [], 0
    for i, (t0, kind, pieces) in enumerate(SEGS):
        f1 = round((bounds[i + 1] - START) * FPS)
        total, left, ps = f1 - f0, f1 - f0, []
        for p in pieces:
            frz = p[0] == "freeze"
            clip, t, *rest = p[1:] if frz else p
            n = round(rest[0] * FPS) if rest else left
            ps.append(dict(freeze=frz, clip=clip, t=t, n=min(n, left)))
            left -= ps[-1]["n"]
        assert left == 0 and total > 0, (NAMES[i], left)
        out.append(dict(name=NAMES[i], kind=kind, f0=f0, f1=f1, pieces=ps))
        f0 = f1
    return out


def build(final: bool) -> list[str]:
    segs = plan()
    total = segs[-1]["f1"] / FPS
    args, fc, n = [], [], 0

    def inp(*a) -> int:
        nonlocal n
        args.extend(a)
        n += 1
        return n - 1

    k = inp("-ss", f"{START}", "-t", f"{total:.3f}", "-i", str(FACE))
    fc.append(f"[{k}:v]fps={FPS},setpts=PTS-STARTPTS[fv]")
    fc.append(f"[{k}:a]aresample=48000,asetpts=PTS-STARTPTS,afade=t=in:d=0.01,afade=t=out:st={total - 0.01:.3f}:d=0.01,"
              f"{VOICE},aresample=48000,aformat=channel_layouts=stereo[aout]")

    labels, big, left = [], [], []
    for s in segs:
        for j, p in enumerate(s["pieces"]):
            src = MAN / f"{p['clip']}.mkv"
            if p["freeze"]:  # one frame, extracted once, held
                png = MAN / "freeze" / f"{p['clip']}_{p['t']:.2f}.png"
                png.parent.mkdir(exist_ok=True)
                if not png.exists():
                    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{p['t']:.3f}", "-i", str(src),
                                    "-frames:v", "1", str(png)], check=True)
                k = inp("-loop", "1", "-framerate", str(FPS), "-t", f"{p['n'] / FPS:.4f}", "-i", str(png))
            else:
                k = inp("-ss", f"{p['t']:.3f}", "-i", str(src))
            lab = f"p{len(labels)}"
            dark = ",eq=brightness=-0.42:saturation=0.75" if s["kind"] == "site" else ""
            fc.append(f"[{k}:v]fps={FPS},setpts=PTS-STARTPTS,trim=end_frame={p['n']},setpts=PTS-STARTPTS,"
                      f"crop=1920:1020:0:0{dark},pad=1920:1080:0:0:color={BG},format=yuv420p[{lab}]")
            labels.append(lab)
        if s["kind"] == "site":
            big.append((s["f0"] / FPS, s["f1"] / FPS))
        if s["kind"].endswith("L"):
            left.append((s["f0"] / FPS, s["f1"] / FPS))
    fc.append("".join(f"[{l}]" for l in labels) + f"concat=n={len(labels)}:v=1:a=0[scr]")

    mb, ms = inp("-loop", "1", "-i", str(mask(BIG))), inp("-loop", "1", "-i", str(mask(SMALL)))
    fc.append(f"[fv]crop={2 * R}:{2 * R}:{CX - R}:{CY - R},split[c1][c2]")
    fc.append(f"[c1]scale={BIG}:{BIG}:flags=lanczos,format=yuva420p[b0];[b0][{mb}:v]alphamerge[bigf]")
    fc.append(f"[c2]scale={SMALL}:{SMALL}:flags=lanczos,format=yuva420p[s0];[s0][{ms}:v]alphamerge,split[smallf][smalll]")
    rng = lambda xs: "+".join(f"between(t,{a:.4f},{b - 0.001:.4f})" for a, b in xs)
    on_big, on_left = rng(big), rng(left)
    fc.append(f"[scr][bigf]overlay=(W-w)/2:(H-h)/2-30:enable='{on_big}':shortest=1[v1]")
    fc.append(f"[v1][smallf]overlay=W-w-24:H-h-10:enable='not({on_big}+{on_left})':shortest=1[v1b]")
    fc.append(f"[v1b][smalll]overlay=24:H-h-10:enable='{on_left}':shortest=1[v2]")
    if final:
        fc.append("[v2]format=yuv420p[vout]")
        out, enc = Path(__file__).parent / "out" / "demo_day.mp4", ["-crf", "18", "-preset", "slow"]
    else:
        fc.append("[v2]scale=1280:720:flags=lanczos,format=yuv420p[vout]")
        out, enc = Path(__file__).parent / "out" / "demo_day_preview.mp4", ["-crf", "23", "-preset", "veryfast"]
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *args, "-filter_complex", ";".join(fc),
            "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}", "-r", str(FPS), "-c:v", "libx264", *enc,
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]


if __name__ == "__main__":
    if sys.argv[1:] not in (["preview"], ["final"]):
        sys.exit(__doc__)
    cmd = build(sys.argv[1] == "final")
    if subprocess.run(cmd).returncode:
        sys.exit("ffmpeg failed")
    print("wrote", cmd[-1])
