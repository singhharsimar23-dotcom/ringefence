"""Teleprompter for the face take, pinned to the bottom edge of the screen, right above a keyboard camera.
Shows one phrase of docs/SPEAK_DEMO_DAY.md at a time.
  python demo/prompter.py           Space / click / wheel-down = next, Left / wheel-up = back, Esc = quit
  python demo/prompter.py --check   print the phrases, no window"""
import ctypes
import re
import sys
import tkinter as tk
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "docs" / "SPEAK_DEMO_DAY.md"


def phrases() -> list[str]:
    text = SCRIPT.read_text(encoding="utf-8").split("### 1.", 1)[1]
    out = []
    for line in text.splitlines()[1:]:
        if line.startswith("### "):
            out.append(f"— {line[3:].split('(')[0].strip()} —")
        elif line.strip() and not line.startswith("("):
            out.append(line.strip())
    chunks = []
    for ln in out:
        if ln.startswith("—"):
            chunks.append(ln)
            continue
        for part, mark in re.findall(r"\s*(.*?)\s*(//|/|$)", ln):
            if part:
                chunks.append(part + ("   ‖" if mark == "//" else ""))  # ‖ = long pause
    return chunks


def main() -> None:
    p = phrases()
    if "--check" in sys.argv:
        print("\n".join(p))
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)  # sharp text at 125% scaling
    except Exception:  # noqa: BLE001, S110 - not Windows
        pass
    r = tk.Tk()
    r.overrideredirect(True)
    r.attributes("-topmost", True)
    r.configure(bg="black")
    w, h = int(r.winfo_screenwidth() * 0.45), 120
    r.geometry(f"{w}x{h}+{(r.winfo_screenwidth() - w) // 2}+{r.winfo_screenheight() - h}")  # bottom centre, over the taskbar
    lab = tk.Label(r, fg="white", bg="black", font=("Segoe UI", 30), wraplength=w - 40, justify="center")
    lab.pack(expand=True, fill="both")
    i = [0]

    def show(d=0):
        i[0] = max(0, min(len(p) - 1, i[0] + d))
        lab.config(text=p[i[0]], fg="#888" if p[i[0]].startswith("—") else "white")

    for k in ("<space>", "<Right>", "<Down>", "<Button-1>"):
        r.bind(k, lambda e: show(1))
    for k in ("<Left>", "<Up>", "<BackSpace>"):
        r.bind(k, lambda e: show(-1))
    r.bind("<MouseWheel>", lambda e: show(1 if e.delta < 0 else -1))
    r.bind("<Escape>", lambda e: r.destroy())
    show()
    r.focus_force()
    r.mainloop()


if __name__ == "__main__":
    main()
