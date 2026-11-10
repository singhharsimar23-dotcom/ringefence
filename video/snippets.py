"""Pull the real code the film shows straight from the source, so the engineers section never drifts from the repo.
  python video/snippets.py  ->  video/src/data/snippets.json"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# key: (file, first line, last line, lines to highlight)
PICK = {
    "login": ("ringfence/awx.py", 84, 91, [88]),
    "decimal": ("ringfence/executor.py", 43, 45, [44]),
    "stamp": ("ringfence/executor.py", 207, 216, [211, 212, 214, 215, 216]),
    "webhook": ("ringfence/executor.py", 366, 373, [367, 372]),
    "lookup": ("ringfence/awx.py", 170, 173, [172, 173]),
    "late": ("ringfence/executor.py", 312, 317, [313, 314]),
    "mcp": ("ringfence/mcp_server.py", 82, 104, [83, 88, 93, 98, 103]),
    "mcp_doc": ("ringfence/mcp_server.py", 1, 5, [4]),
}


def main():
    out = {}
    for k, (f, a, b, hl) in PICK.items():
        src = (ROOT / f).read_text(encoding="utf-8").splitlines()
        assert b <= len(src), f"{f} is shorter than line {b}"
        out[k] = {"file": f, "start": a, "lines": src[a - 1:b], "hl": hl}
    (ROOT / "video/src/data/snippets.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print("\n".join(f"{k}: {v['file']}:{v['start']}  {v['lines'][0].strip()[:70]}" for k, v in out.items()))


if __name__ == "__main__":
    main()
