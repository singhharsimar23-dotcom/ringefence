"""Run the pinned Metal CLI with the RPC secrets taken from the environment (or HKCU\\Environment), never argv.
Usage: python scripts/metal_cli.py <workdir> <metal-agent args...>   Output is redacted before printing."""
import os
import subprocess
import sys
from pathlib import Path

CLI = Path.home() / "metal_pkg" / "run" / "node_modules" / "@metalntwx" / "metal-agent" / "dist" / "index.js"
NAMES = ("METAL_RPC_URL", "METAL_RPC_SECRET")


def env_var(name):
    if os.environ.get(name):
        return os.environ[name]
    import winreg
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as k:
        return winreg.QueryValueEx(k, name)[0]


def run(workdir, args, timeout=90):
    env = {**os.environ, **{n: env_var(n) for n in NAMES}}
    p = subprocess.run(["node", str(CLI), *args], cwd=workdir, env=env, capture_output=True, text=True, timeout=timeout, encoding="utf-8")
    out = p.stdout + p.stderr
    for n in NAMES:
        out = out.replace(env[n], f"<{n}>")
    secret = env["METAL_RPC_SECRET"]
    return p.returncode, out.replace(secret, "<redacted>")


if __name__ == "__main__":
    Path(sys.argv[1]).mkdir(parents=True, exist_ok=True)
    rc, out = run(sys.argv[1], sys.argv[2:])
    print(out)
    print(f"exit {rc}")
