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
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

V = Path(__file__).resolve().parent
DD, MAN, TMP = V / "out" / "dd", V / "out" / "dd" / "manual", V / "out" / "dd" / "film"
FACE = DD / "face_cfr.mov"
FPS, SPEED = 30, 1.1
GAP_MAX = 0.42            # a pause longer than this (clip s) is trimmed to it
SRC0, SRC1 = 1.62, 200.25  # voice in/out: a breath before "Every", a beat after "Thank you."
CX, CY, R = 260, 582, 246
BIG, SMALL = 720, 170
VOICE = "highpass=f=80,afftdn=nf=-25,acompressor=threshold=-18dB:ratio=3:attack=5:release=80,loudnorm=I=-16:TP=-1.5:LRA=11"
H = 1020  # screen height after the taskbar crop

WORDS = json.load(open(DD / "words_merged.json"))
# extra film seconds in the pause that contains this clip time: the screen gets time, the speaker just waits
HOLDS = {35.5: 1.6, 44.0: 1.2, 86.3: 2.2, 88.3: 1.8, 89.5: 1.6, 92.7: 0.6, 108.3: 0.6, 114.5: 0.8,
         119.9: 1.0, 124.3: 0.8, 173.9: 1.2, 198.5: 6.0}
IDLE = {198.5: (192.3, 192.95)}  # a pause too short to loop smoothly borrows a longer idle stretch


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
    c = gap_end(18.5) - 0.12
    add(c, "R", ("clip", "S0", [(c, 5.3), (F(w("and", 30.0)) + 0.3, 5.3), (F(w("and", 30.0)) + 1.5, 6.45),
                                (F(w("connecting", 33.9)), 6.5), (gap_start(35.5) + 0.25, 10.4),
                                (gap_start(35.5) + 0.9, 11.8), (gap_end(35.5) - 0.2, 16.0)]))
    # the timesheet, then Ana's email, closed; the cursor ends on the right pane's prompt
    c = gap_end(35.5) - 0.12
    add(c, "R", ("s16", [(c, 0.3), (F(w("time", 37.2)) + 0.2, 3.0), (F(w("sheet", 37.5)) + 0.25, 4.1),
                         (F(38.3), 7.7), (F(w("email", 39.36)), 9.5), (F(w("asking", 40.3)), 10.6),
                         (F(w("bank", 41.96)), 13.6), (F(43.64), 15.1), (gap_start(44.0) + 0.55, 17.2),
                         (gap_end(44.0) - 0.05, 19.7)]))
    # the prompt, the work, the table with Ana flagged and the approval link
    c = gap_end(44.0)
    add(c, "R", ("clip", "S1", [(c, 94.95), (F(46.44), 99.0), (F(46.94) + 0.4, 103.0), (F(50.48) + 0.6, 111.0),
                                (F(54.24) + 0.6, 115.0), (F(62.74), 139.5), (F(63.68) + 0.3, 143.0),
                                (F(66.58), 147.5), (F(67.26), 150.1)]))
    # talk it into skipping the approval; it refuses
    c = F(77.7)
    add(c, "R", ("clip", "S2", [(c, 8.6), (F(80.8), 12.0), (F(81.27) + 0.3, 17.8), (F(86.0), 25.0)]))
    # open the link, reject Ana's email, approve with the passkey
    c = gap_start(86.3) + 0.08
    add(c, "R", ("clip", "S3", [(c, 12.2), (c + 0.8, 15.0), (gap_end(86.3) - 0.25, 23.0),
                                (F(w("reject", 86.78)) + 0.25, 24.3), (F(w("approve", 87.88)), 31.0),
                                (gap_end(88.3) - 0.25, 39.6)]))
    # send it; the transfers are scheduled
    c = gap_end(88.3) - 0.08
    add(c, "R", ("clip", "S4", [(c, 13.2), (F(w("it", 89.0)) + 0.15, 15.6), (gap_end(89.5) - 0.2, 28.0)]))
    # on Airwallex: Tom's payout, settled
    c = gap_end(89.5) - 0.08
    add(c, "L", ("clip", "S17", [(c, 0.4), (F(w("right", 91.6)) - 0.9, 3.0), (F(w("right", 91.6)) + 0.3, 5.3),
                                 (gap_end(92.7) - 0.1, 9.5)]))
    # Airwallex is secure; the agent in the middle is the risk; nine gaps
    c = gap_end(92.7) - 0.05
    add(c, "R", ("clip", "S11", [(c, 4.5), (F(w("found", 100.42)), 12.0)]))
    # week 2, live: both prompts
    c = F(w("here's", 103.84)) - 0.1
    nx = F(w("next", 105.9))
    add(c, "R", ("wk2", "S13", [(c, 9.6), (nx + 1.4, 36.9), (nx + 1.9, 38.1), (F(113.9), 55.0), (F(119.3), 76.0)],
                 "S5", [(c, 11.9), (nx + 0.1, 12.0), (nx + 0.5, 12.6), (nx + 0.9, 14.6), (F(108.44), 20.0),
                        (F(113.9), 40.0)]))
    # the standard agent's own approval prompt: just IDs
    c = gap_start(114.5) + 0.1
    add(c, "R", ("wk2", "S13", [(F(113.9), 55.0), (F(119.3), 76.0)],
                 "S8", [(c, 24.0), (F(w("approve", 116.2)) + 0.2, 37.6)]))
    # the right one: open the link, approve with the passkey
    c = gap_start(119.9) + 0.05
    add(c, "R", ("wk2", "S14", [(c, 5.6), (c + 0.55, 7.4)], "S8", [(c, 37.6)]))
    c2 = c + 0.55
    add(c2, "R", ("clip", "S14", [(c2, 7.5), (gap_end(119.9) + 0.2, 9.5), (F(w("approve", 120.6)) + 0.3, 12.2),
                                  (F(w("now", 122.6)), 18.3), (gap_start(124.3), 19.3)]))
    # someone changes Tom's account on Airwallex
    c = gap_start(124.3) + 0.05
    add(c, "L", ("clip", "S7", [(c, 5.3), (F(w("tom's", 125.36)) - 0.1, 11.7), (F(w("account", 126.34)), 13.4),
                                (F(w("on", 127.52)), 17.0)]))
    # the left one approves: paid to the new account, can't cancel, no admin key
    c = F(w("on", 127.52)) - 0.05
    add(c, "R", ("wk2", "S15", [(c, 8.0), (F(143.31), 8.0), (F(144.68), 12.4), (gap_end(144.9), 13.4),
                                (F(148.38), 21.0), (F(150.9), 23.0), (F(152.84), 25.5), (F(w("nothing", 153.5)), 27.4),
                                (F(154.34), 28.5)],
                 "S8", [(c, 37.6), (F(w("approve", 128.22)) + 0.2, 38.0), (F(128.52) + 0.3, 40.0),
                        (F(130.68), 50.5), (F(131.23), 52.0), (F(134.94), 68.0), (F(135.64), 72.0),
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
    add(c, "L", ("clip", "S18", [(c, 0.5), (F(w("both", 170.9)), 3.2), (gap_end(171.6) - 0.1, 5.3),
                                 (F(173.58), 10.0), (gap_start(173.9) + 0.3, 12.0), (gap_end(173.9) - 0.05, 16.9),
                                 (F(w("nothing", 175.28)), 18.2)]))
    # close: the face over the gauntlet
    c = gap_end(176.3) - 0.12
    add(c, "big", ("still", "S11", 27.0))
    # the call to action on the live playground: Ana's email, the run, the graph
    c = gap_end(192.6) - 0.1
    add(c, "R", ("clip", "S12", [(c, 6.0), (F(w("try", 196.3)), 10.5), (gap_end(198.5) - 0.15, 28.5)]))
    # thank you
    add(gap_end(198.5) - 0.1, "big", ("still", "S12", 28.5))
    return S


# ---------------------------------------------------------------- face + voice
def face(jobs: int = 8) -> None:
    TMP.mkdir(parents=True, exist_ok=True)
    crop = f"crop={2 * R}:{2 * R}:{CX - R}:{CY - R}"
    common = ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "10", "-pix_fmt", "yuv420p", "-c:a", "pcm_s16le", "-ar", "48000", "-ac", "2"]

    def run(i_u):
        i, u = i_u
        n = u["n1"] - u["n0"]
        out = TMP / f"f{i:03d}.mkv"
        if n <= 0:
            return None
        d = n / FPS
        if u["kind"] == "speech" or u["hold"] == 0:
            a, b = u["a"], u["a"] + (u["b"] - u["a"] if u["kind"] == "speech" else u["keep"])
            fc = (f"[0:v]{crop},setpts=(PTS-STARTPTS)/{SPEED},fps={FPS},tpad=stop_mode=clone:stop_duration=1,trim=end_frame={n}[v];"
                  f"[0:a]asetpts=PTS-STARTPTS,atempo={SPEED},apad,atrim=end={d:.6f},afade=t=in:d=0.006,afade=t=out:st={max(d - 0.006, 0):.6f}:d=0.006[a]")
            cmd = ["-ss", f"{a:.3f}", "-t", f"{b - a + 0.2:.3f}", "-i", str(FACE)]
        else:  # the real pause, then a slow ping-pong of it: an idle face and room tone
            a, b = next((v for k, v in IDLE.items() if u["a"] <= k <= u["b"]), (u["a"] + 0.03, u["b"] - 0.03))
            m = int(u["hold"] / (4 * (b - a))) + 2  # ping-pong passes (each is 2 x the idle stretch at half speed)
            vs, as_ = "".join(f"[pp{j}]" for j in range(m)), "".join(f"[ap{j}]" for j in range(m))
            fc = (f"[0:v]{crop},setpts=PTS-STARTPTS,trim=end={u['keep']:.4f},setpts=(PTS-STARTPTS)/{SPEED},fps={FPS}[k];"
                  f"[1:v]{crop},setpts=2*(PTS-STARTPTS),fps={FPS},split[p][q];[q]reverse[r];[p][r]concat=n=2:v=1:a=0,split={m}{vs};"
                  f"[k]{vs}concat=n={m + 1}:v=1:a=0,trim=end_frame={n}[v];"
                  f"[0:a]asetpts=PTS-STARTPTS,atrim=end={u['keep']:.4f},atempo={SPEED}[ak];"
                  f"[1:a]asetpts=PTS-STARTPTS,atempo=0.5,asplit[aa][aq];[aq]areverse[ar];[aa][ar]concat=n=2:v=0:a=1,asplit={m}{as_};"
                  f"[ak]{as_}concat=n={m + 1}:v=0:a=1,atrim=end={d:.6f},afade=t=in:d=0.006,afade=t=out:st={max(d - 0.006, 0):.6f}:d=0.006[a]")
            cmd = ["-ss", f"{u['a']:.3f}", "-t", f"{u['keep'] + 0.1:.3f}", "-i", str(FACE),
                   "-ss", f"{a:.3f}", "-t", f"{b - a:.3f}", "-i", str(FACE)]
        subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", *cmd, "-filter_complex", fc,
                        "-map", "[v]", "-map", "[a]", *common, str(out)], check=True)
        return out

    outs = list(ThreadPoolExecutor(jobs).map(run, enumerate(UNITS)))
    lst = TMP / "face.txt"
    lst.write_text("".join(f"file '{p.as_posix()}'\n" for p in outs if p))
    subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c", "copy", str(TMP / "face.mkv")], check=True)
    print("face", TOTAL / FPS)


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
    under = None
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
            an = spec[2]
            r = Reader(spec[1], interp(an, n0 / FPS))
            for n in range(n0, n1):
                enc.stdin.write(r.get(interp(an, n / FPS)).tobytes())
            r.close()
        elif kind == "s16":
            an = spec[1]
            if under is None:
                under = frame_at("S1", 94.9)
                under[795:845, 1078:1122] = frame_at("S0", 18.1)[795:845, 1078:1122]  # S1's own pointer, so only S16's shows
            bg = np.asarray(Image.open(MAN / "S16_bg.png").convert("RGB"))[:H].astype(np.int16)
            r = Reader("S16", interp(an, n0 / FPS))
            for n in range(n0, n1):
                f = r.get(interp(an, n / FPS))
                m = dilate(np.abs(f.astype(np.int16) - bg).max(2) > 14, 2)
                enc.stdin.write(np.where(m[..., None], f, under).tobytes())
            r.close()
        elif kind == "wk2":
            ab, ao = spec[2], spec[4]
            rb, ro = Reader(spec[1], interp(ab, n0 / FPS)), Reader(spec[3], interp(ao, n0 / FPS))
            for n in range(n0, n1):
                f = rb.get(interp(ab, n / FPS)).copy()
                f[NEW] = ro.get(interp(ao, n / FPS))[OLD]
                enc.stdin.write(f.tobytes())
            rb.close(), ro.close()
        print(f"{i:2} {n0 / FPS:7.2f}-{n1 / FPS:7.2f} {bub:3} {kind} {spec[1]}", flush=True)
    enc.stdin.close()
    enc.wait()


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
    elif cmd in (["preview"], ["final"]):
        compose(cmd == ["final"])
    else:
        sys.exit(__doc__)
