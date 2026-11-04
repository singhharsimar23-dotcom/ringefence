"""Writes static/build.json (tests, commit sha, video url) for the landing footer. Run before deploy: uv run python scripts/build_info.py [VIDEO_URL]"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def run(*a: str) -> str:
    return subprocess.run(a, cwd=ROOT, capture_output=True, text=True, check=False).stdout.strip()


def main() -> None:
    m = re.search(r"(\d+) tests? collected", run("uv", "run", "pytest", "--collect-only", "-q"))
    out = {"tests": int(m.group(1)) if m else None, "sha": run("git", "rev-parse", "--short", "HEAD") or None,
           "video": sys.argv[1] if len(sys.argv) > 1 else None}
    (ROOT / "static" / "build.json").write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8")
    print(out)


if __name__ == "__main__":
    main()
