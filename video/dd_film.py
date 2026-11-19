"""Demo Day film, cut to the voice. Hard cuts only, no zoom, no captions; taskbar cropped off every clip.

    python video/dd_film.py face      # voice track at 1.1x, long pauses trimmed, holds where the screen needs time
    python video/dd_film.py screen    # every shot retimed so each screen action lands on the word that names it
    python video/dd_film.py preview   # 1280x720 -> video/out/demo_day_preview.mp4
    python video/dd_film.py final     # 1920x1080 crf 18 -> video/out/demo_day.mp4
    python video/dd_film.py times     # print the film time of every voice unit

Screen pieces are piecewise-linear maps (film time -> clip time) anchored on words; equal clip times are a freeze.
Week 2 is a composite: the reshoot window (S13/S14/S15) with the earlier take's left pane (S5/S8) laid into it, so
the left pane keeps one unbroken history. The docs beat lays the Notepad from S16 over the S1 terminal at 94.9 s.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

V = Path(__file__).resolve().parent
DD, MAN, TMP = V / "out" / "dd", V / "out" / "dd" / "manual", V / "out" / "dd" / "film"
FACE = DD / "face_cfr.mov"
FPS, SPEED = 30, 1.02
GAP_MAX = 1e9             # pauses are never trimmed: the face plays straight through
SRC0, SRC1 = 1.62, 200.3   # voice in/out: a breath before "Every", a calm beat after "Thank you." (Loom's toolbar starts creeping into the circle at ~200.5)
CX, CY, R = 260, 582, 246
BIG, SMALL = 720, 200
VOICE = "highpass=f=80,afftdn=nf=-25,acompressor=threshold=-18dB:ratio=3:attack=5:release=80,loudnorm=I=-16:TP=-1.5:LRA=11"
H = 1020  # screen height after the taskbar crop

WORDS = json.load(open(DD / "words_merged.json"))
# extra film seconds in the pause that contains this clip time: the screen gets time, the speaker just waits
HOLDS: dict = {}  # never: the face is not paused or looped


def w(word: str, near: float) -> float:
    """Clip start time of the spoken word nearest `near`."""
    c = [x for x in WORDS if x["w"].lower().strip(".,").startswith(word.lower()) and abs(x["s"] - near) < 3]
    assert c, (word, near)
    return min(c, key=lambda x: abs(x["s"] - near))["s"]


def pauses() -> list[tuple[float, float]]:
    s = sorted(tuple(x) for x in json.load(open(DD / "silences.json")))
    s.append((w("account", 173.6) + 0.30, w("ringfence", 174.2) - 0.02))  # the breath before "Ringfence sent nothing"
    out = []
    for a, b in sorted(s):
        if out and a - out[-1][1] < 0.06:
            out[-1] = (out[-1][0], max(b, out[-1][1]))
        else:
            out.append((a, b))
    return [(max(a, SRC0), min(b, SRC1)) for a, b in out if b > SRC0 and a < SRC1 and min(b, SRC1) - max(a, SRC0) > 0.05]


def units() -> list[dict]:
    """Voice units in order: speech (played at 1.1x) and pauses (trimmed, maybe held). Film times in seconds."""
    out, t, f = [], SRC0, 0.0
    for a, b in pauses():
        if a > t:
            out.append(dict(kind="speech", a=t, b=a, f0=f, f1=f + (a - t) / SPEED))
            f = out[-1]["f1"]
        hold = sum(v for k, v in HOLDS.items() if a <= k <= b)
        keep = min(b - a, GAP_MAX)
        out.append(dict(kind="pause", a=a, b=b, keep=keep, hold=hold, f0=f, f1=f + keep / SPEED + hold))
        f, t = out[-1]["f1"], b
    if t < SRC1:
        out.append(dict(kind="speech", a=t, b=SRC1, f0=f, f1=f + (SRC1 - t) / SPEED))
    for u in out:  # whole frames, so face, audio and screen share one clock
        u["n0"], u["n1"] = round(u["f0"] * FPS), round(u["f1"] * FPS)
    return out


UNITS = units()
TOTAL = UNITS[-1]["n1"]


def F(src: float) -> float:
    """Film time of a clip time in face_cfr.mov. Inside a pause it spreads over the pause's film length."""
    for u in UNITS:
        if u["a"] <= src <= u["b"]:
            return u["f0"] + (src - u["a"]) / (u["b"] - u["a"]) * (u["f1"] - u["f0"])
    raise ValueError(src)


def gap_end(src: float) -> float:
    """Film time where the pause containing this clip time ends (the next word starts)."""
    return next(u["f1"] for u in UNITS if u["kind"] == "pause" and u["a"] <= src <= u["b"])


def gap_start(src: float) -> float:
    return next(u["f0"] for u in UNITS if u["kind"] == "pause" and u["a"] <= src <= u["b"])


# ---------------------------------------------------------------- shots
# (film cut time, bubble, spec). The shot runs to the next cut. Bubble: big (darkened still under the face), R, L.
# spec: ("clip", name, anchors) | ("still", name, t) | ("s16", anchors) | ("wk2", base, anchors, old, anchors)
def shots() -> list[tuple]:
    S = []
    add = lambda t, bub, spec: S.append((t, bub, spec))
    # open: the face over the site's hero, still
    add(0.0, "big", ("still", "S11", 4.5))
    # two agents side by side; the right pane connects with one line, then Claude starts
    c = F(18.9)
    add(c, "R", ("clip", "S0", [(c, 5.3), (F(29.9), 5.6), (F(34.4), 10.4), (F(35.72), 16.0)]))
    # the timesheet (Ana, Tom, Mia), then Ana's email on "email", closed; the cursor glides to the right pane's prompt
    c = F(35.72)
    add(c, "R", ("s16", [(c, 0.3), (F(w("email", 39.36)) - 0.2, 9.9), (F(43.9), 16.0), (F(45.7), 19.7)]))
    # the prompt, the work, the table with Ana flagged and the approval link
    c = F(45.7)
    add(c, "R", ("clip", "S1", [(c, 94.95), (F(46.44), 99.0), (F(46.94) + 0.4, 103.0), (F(50.48) + 0.6, 111.0),
                                (F(54.24) + 0.6, 115.0), (F(62.74), 139.5), (F(63.68) + 0.3, 143.0),
                                (F(66.58), 147.5), (F(67.26), 150.1)]))
    # talk it into skipping the approval; it refuses ("It can't. There is no tool for that.")
    c = F(77.6)
    add(c, "R", ("clip", "S2", [(c, 8.6), (F(81.27) + 0.3, 17.8), (F(83.0), 25.0)]))
    # "only I can approve with my passkey": the approval page opens (the refusal above already shows its link),
    # reject Ana's email, approve, passkey, Approved. No separate "send it" shot: Airwallex next shows it paid.
    c = F(83.0)
    add(c, "R", ("clip", "S3", [(c, 19.0), (F(w("reject", 86.78)) + 0.1, 24.3), (F(89.3), 31.0), (F(92.0), 39.6)]))
    # on Airwallex: paid to the right accounts ("Airwallex itself is secure")
    c = F(92.0)
    add(c, "L", ("clip", "S17", [(c, 0.4), (F(97.8), 9.5)]))
    # the agent in the middle is the risk; nine gaps
    c = F(97.8)
    add(c, "R", ("clip", "S11", [(c, 4.5), (F(w("here's", 103.84)) - 0.1, 12.5)]))
    # week 2, live: both prompts
    c = F(w("here's", 103.84)) - 0.1
    nx = F(w("next", 105.9))
    add(c, "R", ("wk2", "S13", [(c, 9.6), (nx - 0.6, 32.4), (nx + 1.4, 36.9), (nx + 1.9, 38.1), (F(113.9), 55.0), (F(119.3), 76.0)],
                 "S5", [(c, 11.9), (nx + 0.1, 12.0), (nx + 0.5, 12.6), (nx + 0.9, 14.6), (F(108.44), 20.0),
                        (F(113.9), 40.0)]))
    # the standard agent's own approval prompt: just IDs
    c = gap_start(114.5) + 0.1
    add(c, "R", ("wk2", "S13", [(F(113.9), 55.0), (F(119.3), 76.0)],
                 "S8", [(c, 24.0), (F(w("approve", 116.2)) + 0.2, 37.6)]))
    # the right one: open the link, approve with the passkey
    c = F(119.85)
    add(c, "R", ("wk2", "S14", [(c, 5.6), (c + 0.55, 7.4)], "S8", [(c, 37.6), (c + 1, 37.6)]))
    c2 = c + 0.55
    add(c2, "R", ("clip", "S14", [(c2, 7.4), (F(122.0), 12.2), (F(124.35), 19.3)]))
    # someone changes Tom's account on Airwallex: the attacker's view, search, both Toms
    c = F(124.35)
    add(c, "L", ("clip", "S7", [(c, 10.8), (F(w("on", 127.52)), 17.0)]))
    # the left one approves: paid to the new account, can't cancel, no admin key
    c = F(w("on", 127.52)) - 0.05
    add(c, "R", ("wk2", "S15", [(c, 8.0), (F(143.31), 8.0), (F(144.68), 12.4), (gap_end(144.9), 13.4),
                                (F(148.38), 21.0), (F(150.9), 23.0), (F(152.84), 25.5), (F(w("nothing", 153.5)), 27.4),
                                (F(154.34), 28.5)],
                 "S8", [(c, 37.6), (F(w("approve", 128.22)) + 0.2, 38.0), (F(128.52) + 0.3, 40.0),
                        (F(130.68), 50.5), (F(131.23), 52.0), (F(134.94), 68.0), (F(135.64), 72.0),
                        # skip 81.5-91.6: the take alt-tabs to the IDE; both ends show the same text, cursor off-pane
                        (sk := F(135.64) + (F(142.66) - F(135.64)) * 9.5 / 24.9, 81.5), (sk, 91.6),
                        (sk2 := sk + (F(142.66) - sk) * 10.2 / 14.9, 101.8), (sk2, 102.3),  # a second alt-tab
                        (F(142.66), 107.0)]))
    # what I learnt
    c = gap_start(154.6) + 0.1
    add(c, "R", ("clip", "S11", [(c, 12.5), (F(159.62), 13.6), (F(163.52), 15.5)]))
    # Ringfence approves the bank account itself
    c = gap_end(166.8) - 0.1
    on = F(w("on", 169.5))
    add(c, "R", ("clip", "S14", [(c, 9.7), (on - 0.1, 11.4)]))
    # on Airwallex: the batch settled; Ringfence's run: nothing
    c = on - 0.1
    add(c, "L", ("clip", "S18", [(c, 0.5), (F(176.3), 18.4)]))
    # close: the live playground at full brightness, played through to "Thank you": the description, Ana's email,
    # the three people it understood (Ana/Germany, Tom/UK, Mia/Australia), then the run and its map
    c = gap_end(176.3) - 0.12
    end, ty = TOTAL / FPS, F(w("connect", 193.32)) - 0.2   # the big face from "connect your agent" through "Thank you"
    add(c, "R", ("clip", "S12", [(c, 4.5), (end, 4.5 + (end - c))]))
    # "Thank you": the big face, as in the open, over the same playground still playing (darkened)
    add(ty, "big", ("clip", "S12", [(ty, 4.5 + (ty - c)), (end, 4.5 + (end - c))]))
    return S


# ---------------------------------------------------------------- face + voice
def face() -> None:
    """The face and voice in one pass, straight through at 1.1x: no cuts, no pauses, no loops."""
    TMP.mkdir(parents=True, exist_ok=True)
    d = TOTAL / FPS
    fc = (f"[0:v]crop={2 * R}:{2 * R}:{CX - R}:{CY - R},setpts=(PTS-STARTPTS)/{SPEED},fps={FPS},trim=end_frame={TOTAL}[v];"
          f"[0:a]asetpts=PTS-STARTPTS,atempo={SPEED},atrim=end={d:.6f},afade=t=in:d=0.01,afade=t=out:st={d - 0.3:.6f}:d=0.3[a]")
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{SRC0:.3f}", "-t", f"{SRC1 - SRC0 + 0.5:.3f}",
                    "-i", str(FACE), "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-preset", "veryfast",
                    "-crf", "10", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2", str(TMP / "face.mkv")], check=True)
    print("face", d)


# ---------------------------------------------------------------- screen
class Reader:
    """Sequential frames of a clip from t0, taskbar cropped. get(t) returns the frame at clip time t (t never goes back)."""

    def __init__(self, clip: str, t0: float):
        self.t0, self.k, self.f = t0, -1, None
        self.p = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t0:.3f}", "-i", str(MAN / f"{clip}.mkv"),
                                   "-vf", f"fps={FPS},crop=1920:{H}:0:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                                  stdout=subprocess.PIPE, bufsize=1920 * H * 3 * 2)

    def get(self, t: float) -> np.ndarray:
        want = max(0, round((t - self.t0) * FPS))
        while self.k < want:
            raw = self.p.stdout.read(1920 * H * 3)
            if len(raw) < 1920 * H * 3:
                break  # past the end: keep the last frame
            self.f, self.k = np.frombuffer(raw, np.uint8).reshape(H, 1920, 3), self.k + 1
        return self.f

    def close(self):
        self.p.kill()


def frame_at(clip: str, t: float) -> np.ndarray:
    raw = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-ss", f"{t:.3f}", "-i", str(MAN / f"{clip}.mkv"),
                          "-frames:v", "1", "-vf", f"crop=1920:{H}:0:0", "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
                         capture_output=True, check=True).stdout
    return np.frombuffer(raw, np.uint8).reshape(H, 1920, 3).copy()


def motion(clip: str, part: int = 0) -> np.ndarray:
    """Changed pixels per frame (480x255 grey, taskbar cropped), cached. Index k = clip time k/FPS.
    part 0 = whole screen, 1 = the left pane (x < 896), 2 = the right (week 2 shows each from a different take)."""
    p = TMP / f"{clip}_motion3.npy"
    if not p.exists():
        pr = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-t", "200", "-i", str(MAN / f"{clip}.mkv"), "-vf",
                               f"fps={FPS},crop=1920:{H}:0:0,scale=480:255,format=gray", "-f", "rawvideo", "-"],
                              stdout=subprocess.PIPE)
        out, prev, sz = [(0, 0, 0)], None, 255 * 480
        while len(raw := pr.stdout.read(sz)) == sz:  # streamed: some clips are 25+ minutes
            f = np.frombuffer(raw, np.uint8).astype(np.int16).reshape(255, 480)
            if prev is not None:
                d = np.abs(f - prev) > 16
                out.append((int(d.sum()), int(d[:, :224].sum()), int(d[:, 224:].sum())))
            prev = f
        pr.wait()
        np.save(p, np.array(out))
    return np.load(p)[:, part]


MOVING = 12        # changed px (at 1/4 scale) that count as something moving; a blinking caret is below this
UI_MAX = 1.25      # the fastest a moving cursor, window or page may play
IDLE_MAX = 8.0     # the fastest a still screen may play (invisible: nothing moves)


def warp(clip: str, anchors: list, part: int = 0) -> callable:
    """Film time -> clip time through the anchors. Inside each segment, moving frames play near real speed and still
    frames take up the slack, so a cursor never looks sped up. Returns the map and a report of motion speeds."""
    m = motion(clip, part) > MOVING
    segs = []
    for (x0, y0), (x1, y1) in zip(anchors, anchors[1:]):
        k0, k1 = round(y0 * FPS), max(round(y1 * FPS), round(y0 * FPS))
        mv = m[min(k0, len(m) - 1):min(k1, len(m))]
        M, I = mv.sum() / FPS, (len(mv) - mv.sum()) / FPS
        D = x1 - x0
        if k1 == k0 or D <= 0:
            segs.append((x0, x1, y0, y1, None, 0.0))
            continue
        room = D - I / IDLE_MAX                                         # film time left for moving frames
        sm = max(1.0, M / room) if M and room > 0.5 * D * M / (M + I) else (M + I) / D if M else 1.0
        si = I / (D - M / sm) if I and D - M / sm > 1e-6 else sm
        if M == 0:
            sm, si = 1.0, I / D
        # per-frame film durations, cumulative
        dt = np.where(mv, 1 / (FPS * sm), 1 / (FPS * si))
        dt *= D / dt.sum()
        segs.append((x0, x1, y0, y1, np.r_[0, np.cumsum(dt)], sm if M else 0.0))

    def f(t: float) -> float:
        for x0, x1, y0, y1, cum, _ in segs:
            if t <= x1:
                if t <= x0 or cum is None:
                    return y0
                return min(y1, y0 + float(np.interp(t - x0, cum, np.arange(len(cum)))) / FPS)
        return anchors[-1][1]
    f.report = [(x0, x1, y0, y1, sm) for x0, x1, y0, y1, _, sm in segs]
    return f


def interp(anchors, t):
    xs, ys = zip(*anchors)
    return float(np.interp(t, xs, ys))


def dark(img: np.ndarray) -> np.ndarray:
    g = img.mean(2, keepdims=True)
    return ((0.75 * img + 0.25 * g) * 0.36).astype(np.uint8)


def dilate(m: np.ndarray, r: int) -> np.ndarray:
    o = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            o |= np.roll(np.roll(m, dy, 0), dx, 1)
    return o


# Week 2: the earlier take's left pane (rows 203-888, x 8-887) sits at rows 182-867, x 17-896 in the reshoot window.
OLD = (slice(203, 888), slice(8, 887))
NEW = (slice(182, 867), slice(17, 896))


def screen(only: str = "") -> None:
    TMP.mkdir(parents=True, exist_ok=True)
    S = shots()
    cuts = [round(t * FPS) for t, *_ in S] + [TOTAL]
    enc = subprocess.Popen(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "rawvideo", "-pix_fmt", "rgb24",
                            "-s", f"1920x{H}", "-r", str(FPS), "-i", "-", "-c:v", "libx264", "-preset", "veryfast", "-crf", "12",
                            "-pix_fmt", "yuv420p", str(TMP / "screen.mkv")], stdin=subprocess.PIPE)
    under, rep = None, []
    for i, (t, bub, spec) in enumerate(S):
        n0, n1 = cuts[i], cuts[i + 1]
        assert n1 > n0, (i, spec[:2])
        kind = spec[0]
        if kind == "still":
            img = frame_at(spec[1], spec[2])
            img = dark(img) if bub == "big" else img
            for _ in range(n0, n1):
                enc.stdin.write(img.tobytes())
            continue
        if kind == "clip":
            an = warp(spec[1], spec[2])
            rep.append((i, spec[1], an.report))
            r = Reader(spec[1], an(n0 / FPS))
            for n in range(n0, n1):
                img = r.get(an(n / FPS))
                enc.stdin.write((dark(img) if bub == "big" else img).tobytes())
            r.close()
        elif kind == "s16":
            an = warp("S16", spec[1])
            rep.append((i, "S16", an.report))
            if under is None:
                under = frame_at("S1", 94.9)
                under[795:845, 1078:1122] = frame_at("S0", 18.1)[795:845, 1078:1122]  # S1's own pointer, so only S16's shows
            bg = np.asarray(Image.open(MAN / "S16_bg.png").convert("RGB"))[:H].astype(np.int16)
            r = Reader("S16", an(n0 / FPS))
            for n in range(n0, n1):
                f = r.get(an(n / FPS))
                m = dilate(np.abs(f.astype(np.int16) - bg).max(2) > 14, 2)
                enc.stdin.write(np.where(m[..., None], f, under).tobytes())
            r.close()
        elif kind == "wk2":
            ab, ao = warp(spec[1], spec[2], 2), warp(spec[3], spec[4], 1)
            rep += [(i, spec[1], ab.report), (i, spec[3], ao.report)]
            rb, ro = Reader(spec[1], ab(n0 / FPS)), Reader(spec[3], ao(n0 / FPS))
            for n in range(n0, n1):
                f = rb.get(ab(n / FPS)).copy()
                f[NEW] = ro.get(ao(n / FPS))[OLD]
                enc.stdin.write(f.tobytes())
            rb.close(), ro.close()
        print(f"{i:2} {n0 / FPS:7.2f}-{n1 / FPS:7.2f} {bub:3} {kind} {spec[1]}", flush=True)
    enc.stdin.close()
    enc.wait()
    speeds(rep)


def speeds(rep) -> None:
    """Moving-content speed per segment; anything a viewer would see as sped up is flagged."""
    for i, clip, segs in rep:
        for x0, x1, y0, y1, sm in segs:
            if sm > UI_MAX:
                print(f"FAST shot {i:2} {clip:4} film {x0:6.2f}-{x1:6.2f} clip {y0:6.2f}-{y1:6.2f} moving x{sm:.2f}")


# ---------------------------------------------------------------- compose
def mask(size: int) -> Path:
    from PIL import ImageDraw
    p = DD / f"mask{size}.png"
    k = 4
    im = Image.new("L", (size * k, size * k), 0)
    ImageDraw.Draw(im).ellipse((0, 0, size * k - 1, size * k - 1), fill=255)
    im.resize((size, size), Image.LANCZOS).save(p)
    return p


def compose(final: bool) -> None:
    S = shots()
    cuts = [t for t, *_ in S] + [TOTAL / FPS]
    rng = lambda kind: "+".join(f"between(t,{round(cuts[i] * FPS) / FPS:.4f},{round(cuts[i + 1] * FPS) / FPS - 0.001:.4f})"
                                for i, s in enumerate(S) if s[1] == kind) or "0"
    big, left = rng("big"), rng("L")
    total = TOTAL / FPS
    fc = [f"[0:v]pad=1920:1080:0:0:color=0x0b0b0c,format=yuv420p[scr]",
          f"[1:v]split[c1][c2]",
          f"[c1]scale={BIG}:{BIG}:flags=lanczos,format=yuva420p[b0];[b0][2:v]alphamerge[bigf]",
          f"[c2]scale={SMALL}:{SMALL}:flags=lanczos,format=yuva420p[s0];[s0][3:v]alphamerge,split[smallf][smalll]",
          f"[scr][bigf]overlay=(W-w)/2:(H-h)/2-30:enable='{big}'[v1]",
          f"[v1][smallf]overlay=W-w-24:H-h-10:enable='not({big}+{left})'[v1b]",
          f"[v1b][smalll]overlay=24:H-h-10:enable='{left}'[v2]",
          f"[1:a]aresample=48000,{VOICE},aresample=48000,aformat=channel_layouts=stereo[aout]"]
    if final:
        fc.append("[v2]format=yuv420p[vout]")
        out, enc = V / "out" / "demo_day.mp4", ["-crf", "18", "-preset", "slow"]
    else:
        fc.append("[v2]scale=1280:720:flags=lanczos,format=yuv420p[vout]")
        out, enc = V / "out" / "demo_day_preview.mp4", ["-crf", "23", "-preset", "veryfast"]
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", str(TMP / "screen.mkv"), "-i", str(TMP / "face.mkv"),
                    "-loop", "1", "-i", str(mask(BIG)), "-loop", "1", "-i", str(mask(SMALL)), "-filter_complex", ";".join(fc),
                    "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}", "-r", str(FPS), "-c:v", "libx264", *enc,
                    "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)], check=True)
    print("wrote", out, f"{total:.2f}s")


if __name__ == "__main__":
    cmd = sys.argv[1:2]
    if cmd == ["times"]:
        for u in UNITS:
            print(f"{u['kind']:6} {u['a']:7.2f}-{u['b']:7.2f}  film {u['f0']:7.2f}-{u['f1']:7.2f}  hold {u.get('hold', 0)}")
        for t, bub, spec in shots():
            print(f"cut {t:7.2f} {bub:3} {spec[0]} {spec[1]}")
        print("total", TOTAL / FPS)
    elif cmd == ["face"]:
        face()
    elif cmd == ["screen"]:
        screen()
    elif cmd == ["pace"]:  # the speed report without rendering
        rep = []
        for i, (t, bub, spec) in enumerate(shots()):
            if spec[0] == "clip":
                rep.append((i, spec[1], warp(spec[1], spec[2]).report))
            elif spec[0] == "s16":
                rep.append((i, "S16", warp("S16", spec[1]).report))
            elif spec[0] == "wk2":
                rep += [(i, spec[1], warp(spec[1], spec[2], 2).report), (i, spec[3], warp(spec[3], spec[4], 1).report)]
        speeds(rep)
    elif cmd in (["preview"], ["final"]):
        compose(cmd == ["final"])
    else:
        sys.exit(__doc__)
