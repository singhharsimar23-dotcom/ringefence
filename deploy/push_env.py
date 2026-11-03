"""Copy the secrets the VM needs from this machine's env (or HKCU registry) straight into /etc/ringfence/env (root, 600).

    uv run python deploy/push_env.py rf@<host>

Nothing is printed or written locally: values go over ssh stdin. An AWX_WEBHOOK_SECRET line already on the VM is kept.
"""
from __future__ import annotations

import subprocess
import sys

from ringfence.config import env

REQUIRED = ["AWX_CLIENT_ID", "AWX_API_KEY", "AWX_BASE_URL", "AWX_PLATFORM_ACCOUNT",
            "AWX_EMPLOYER_A", "AWX_EMPLOYER_B", "AWX_EMPLOYER_C"]
OPTIONAL = ["ANTHROPIC_API_KEY", "RF_MODEL", "RF_NOW", "AWX_PLAYGROUND_ACCOUNT", "METAL_RPC_URL", "METAL_RPC_SECRET"]
REMOTE = ("{ cat; sudo grep -h '^AWX_WEBHOOK_SECRET=' /etc/ringfence/env 2>/dev/null || true; } "
          "| sudo install -m600 -o root -g root /dev/stdin /etc/ringfence/env.new "
          "&& sudo mv /etc/ringfence/env.new /etc/ringfence/env && sudo systemctl restart ringfence 2>/dev/null; "
          "sudo awk -F= '{print $1}' /etc/ringfence/env")


def lines() -> str:
    out = []
    for name in REQUIRED + OPTIONAL:
        try:
            v = env(name)
        except KeyError:
            if name in REQUIRED:
                sys.exit(f"missing required env var {name}")
            continue
        if not v or any(ch in v for ch in "\r\n\"'\\"):
            sys.exit(f"{name} is empty or has characters a systemd EnvironmentFile cannot hold")
        out.append(f"{name}={v}")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    r = subprocess.run(["ssh", sys.argv[1], REMOTE], input=lines().encode(), capture_output=True, check=False)
    print("keys now on the VM:", r.stdout.decode().split(), r.stderr.decode()[-300:] if r.returncode else "")
    sys.exit(r.returncode)
