"""Cut the Loom's long pauses and re-time every word for the film.

Reads var/loom.mp4 and var/edit/words.json (faster-whisper word timings). Every gap between words longer than GAP is
cut down to GAP, cutting in the middle of the silence, so no word is touched. Writes:
  video/public/loom_cut.mp4   the Loom with the same cuts, 30 fps, voice cleaned and levelled
  video/public/words.json     every word with its new start/end in seconds
  python video/prep.py"""
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GAP, LEAD, END = 0.4, 0.35, 310.75  # END drops the closing "Bye"

segs = json.loads((ROOT / "var/edit/words.json").read_text(encoding="utf-8"))
words = [w for s in segs for w in s["words"] if w["e"] <= END]

# keep intervals in the original: from LEAD before the first word, through each word, cutting long gaps in the middle
keep, a = [], max(0.0, words[0]["s"] - LEAD)
for w, nxt in zip(words, words[1:]):
    gap = nxt["s"] - w["e"]
    if gap > GAP:
        keep.append((a, w["e"] + GAP / 2))
        a = nxt["s"] - GAP / 2
keep.append((a, words[-1]["e"] + 0.5))


def new_time(t: float) -> float:
    out = 0.0
    for a, b in keep:
        if t < a:
            return out
        if t <= b:
            return out + t - a
        out += b - a
    return out


total = new_time(keep[-1][1] + 1)
assert all(b > a for a, b in keep) and abs(total - sum(b - a for a, b in keep)) < 1e-6
sel = "+".join(f"between(t,{a:.3f},{b:.3f})" for a, b in keep)
pub = ROOT / "video/public"
pub.mkdir(parents=True, exist_ok=True)
graph = (f"[0:v]fps=30,select='{sel}',setpts=N/30/TB[v];"
         f"[0:a]aselect='{sel}',asetpts=N/SR/TB,highpass=f=80,afftdn=nf=-25,"
         "acompressor=threshold=-20dB:ratio=3:attack=10:release=200,loudnorm=I=-16:TP=-1.5:LRA=7,aresample=48000,aformat=channel_layouts=stereo[a]")
(ROOT / "var/edit/cut.graph").write_text(graph)
subprocess.run(["ffmpeg", "-v", "error", "-y", "-i", str(ROOT / "var/loom.mp4"), "-filter_complex_script", str(ROOT / "var/edit/cut.graph"),
                "-map", "[v]", "-map", "[a]", "-c:v", "libx264", "-crf", "18", "-g", "15", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", str(pub / "loom_cut.mp4")], check=True)
out = [{"w": w["w"], "s": round(new_time(w["s"]), 3), "e": round(new_time(w["e"]), 3), "o": w["s"]} for w in words]
(pub / "words.json").write_text(json.dumps({"total": round(total, 3), "words": out}), encoding="utf-8")
print(f"{len(keep)} pieces, {total:.1f} s (was {words[-1]['e']:.1f} s)")
