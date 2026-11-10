"""v11 voice + cut: clean the Loom's voice, cut its pauses and fillers, speed it 5 %, and re-time every word.

Reads var/loom_v10.mp4 (the raw Loom) and var/v11/words.json (faster-whisper word timings). Writes
  video/public/loom_cut.mp4   the Loom with the same cuts, 30 fps, cleaned voice (stereo, -14 LUFS, -1.5 dBTP)
  video/public/words.json     every word with its new start/end in seconds
  python video/prep11.py

Voice chain: train horns removed by time-gated spectral repair (only the horn's steady lines, only while it sounds),
gentle stationary denoise (~8 dB), cuts at the middle of silences with 8 ms fades, then high-pass, mud cut, presence
lift, 3:1 compression, 1.035x tempo, two-pass loudness."""
import json
import subprocess
from pathlib import Path

import noisereduce as nr
import numpy as np
import soundfile as sf
from scipy.ndimage import percentile_filter
from scipy.signal import istft, stft

ROOT = Path(__file__).resolve().parent.parent
V = ROOT / "var/v11"
SRC = ROOT / "var/loom_v10.mp4"
GAP, LEAD, TEMPO, SR = 0.35, 0.3, 1.035, 48000
# spoken fillers that aren't in the script, and the closing "Bye" (raw seconds, cut at word edges)
DROP = [(44.20, 45.80), (285.00, 287.30), (317.50, 320.47), (333.40, 336.2)]
# train horns, verified on the spectrogram (raw seconds): repair only inside these windows
HORNS = [(59.3, 62.8), (71.3, 74.9), (76.3, 78.2), (84.7, 87.8)]
REF = (40.0, 55.0)  # clean speech: what the spectrum looks like without a horn


def extract() -> np.ndarray:
    wav = V / "raw48.wav"
    if not wav.exists():
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(SRC), "-ac", "1", "-ar", str(SR), str(wav)], check=True)
    a, sr = sf.read(wav)
    assert sr == SR
    return a


def dehorn(a: np.ndarray) -> np.ndarray:
    """Subtract the horn's steady part. A horn holds its partials for seconds while speech keeps moving, so inside a horn
    window a sliding 20th-percentile level of each frequency is the horn (plus room tone); whatever it adds over clean speech's
    25th percentile is subtracted, 250 Hz to 4 kHz only (the voice's fundamental lives below)."""
    n, hop = 4096, 256
    f, t, Z = stft(a, SR, nperseg=n, noverlap=n - hop)
    mag, ph = np.abs(Z), np.angle(Z)
    ref = np.percentile(mag[:, (t >= REF[0]) & (t < REF[1])], 25, axis=1)
    band = (f > 250) & (f < 4000)
    for a0, a1 in HORNS:
        sel = (t >= a0 - 0.5) & (t < a1 + 0.5)
        m = mag[band][:, sel]
        # the horn's level right now: a 20th percentile over the surrounding 0.8 s, which speech (always moving) can't hold up
        steady = percentile_filter(m, 20, size=(1, int(0.8 * SR / hop)), mode="nearest")
        excess = np.clip(steady - 1.6 * ref[band][:, None], 0, None)  # under 4 dB over clean speech's floor is not a horn
        tt = t[sel]
        w = np.clip(np.minimum(tt - a0, a1 - tt) / 0.15, 0, 1)  # 150 ms ramps at the window edges
        fixed = np.maximum(m - 3.0 * excess, 0.05 * m)
        mag[np.ix_(band, sel)] = m * (1 - w) + fixed * w
        print(f"horn {a0:.1f}-{a1:.1f}s: {100 * (excess > 0).mean():.0f}% of cells cleaned")
    _, out = istft(mag * np.exp(1j * ph), SR, nperseg=n, noverlap=n - hop)
    return out[: len(a)]


def keep_intervals(words):
    keep, a = [], max(0.0, words[0]["s"] - LEAD)
    for w, nxt in zip(words, words[1:]):
        if nxt["s"] - w["e"] > GAP:
            keep.append((a, w["e"] + GAP / 2))
            a = nxt["s"] - GAP / 2
    keep.append((a, words[-1]["e"] + 0.45))
    # remove the dropped spans: split any interval they touch
    for d0, d1 in DROP:
        nk = []
        for a, b in keep:
            if b <= d0 or a >= d1:
                nk.append((a, b))
                continue
            if a < d0:
                nk.append((a, d0))
            if b > d1:
                nk.append((d1, b))
        keep = nk
    return [(a, b) for a, b in keep if b - a > 0.05]


def main():
    segs = json.loads((V / "words.json").read_text(encoding="utf-8"))
    words = [w for s in segs for w in s["words"] if not any(d0 <= w["s"] < d1 for d0, d1 in DROP)]
    keep = keep_intervals(words)

    a = extract()
    a = dehorn(a)
    noise = a[int(69.0 * SR):int(70.3 * SR)]  # a silent gap: room tone only
    a = nr.reduce_noise(y=a, sr=SR, y_noise=noise, stationary=True, prop_decrease=0.6)
    fade = int(0.008 * SR)
    ramp = np.linspace(0, 1, fade)
    parts = []
    for s, e in keep:
        p = a[int(s * SR):int(e * SR)].copy()
        p[:fade] *= ramp
        p[-fade:] *= ramp[::-1]
        parts.append(p)
    cut = np.concatenate(parts).astype(np.float32)
    sf.write(V / "voice_cut.wav", cut, SR)

    chain = ("highpass=f=80,equalizer=f=250:width_type=o:width=1.2:g=-2.5,equalizer=f=4500:width_type=o:width=1.5:g=2.5,"
             "acompressor=threshold=-22dB:ratio=3:attack=8:release=160:makeup=2,"
             f"atempo={TEMPO}")
    m = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(V / "voice_cut.wav"), "-af",
                        chain + ",loudnorm=I=-14:TP=-1.5:LRA=7:print_format=json", "-f", "null", "-"],
                       capture_output=True, text=True, encoding="utf-8", errors="replace").stderr
    j = json.loads(m[m.rindex("{"):m.rindex("}") + 1])
    ln = (f"loudnorm=I=-14:TP=-1.5:LRA=7:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
          f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true")
    sel = "+".join(f"between(t,{s:.3f},{e:.3f})" for s, e in keep)
    # each kept frame goes to its piece's exact audio offset; renumbering frames (N/30) drifted ~1 frame per 20 cuts
    off, shift = 0.0, []
    for s, e in keep:
        shift.append(f"between(T,{s:.3f},{e:.3f})*{off - s:.4f}")
        off += e - s
    graph = (f"[0:v]fps=30,select='{sel}',setpts='(T+{'+'.join(shift)})/{TEMPO}/TB',fps=30[v];"
             f"[1:a]{chain},{ln},aresample=48000,aformat=channel_layouts=stereo[a]")
    (V / "cut.graph").write_text(graph)
    pub = ROOT / "video/public"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(SRC), "-i", str(V / "voice_cut.wav"), "-filter_complex_script", str(V / "cut.graph"),
                    "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "16", "-g", "15", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "256k", "-shortest", str(pub / "loom_cut.mp4")], check=True)

    def new_time(t: float) -> float:
        out = 0.0
        for s, e in keep:
            if t < s:
                return out / TEMPO
            if t <= e:
                return (out + t - s) / TEMPO
            out += e - s
        return out / TEMPO

    total = sum(e - s for s, e in keep) / TEMPO
    out = [{"w": w["w"], "s": round(new_time(w["s"]), 3), "e": round(new_time(w["e"]), 3), "o": w["s"]} for w in words]
    assert all(x["e"] >= x["s"] for x in out) and abs(new_time(keep[-1][1]) - total) < 1e-6
    # where Loom switches from the full camera to the bubble, in film time
    (pub / "words.json").write_text(json.dumps({"total": round(total, 3), "switch": round(new_time(21.0), 3), "words": out}), encoding="utf-8")
    print(f"{len(keep)} pieces, {total:.1f} s (was {words[-1]['e']:.1f} s); measured in {j['input_i']} LUFS")


if __name__ == "__main__":
    main()
