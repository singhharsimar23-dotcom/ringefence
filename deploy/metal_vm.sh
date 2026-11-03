#!/usr/bin/env bash
# One-time Metal setup on the VM (the service unit already sets RF_METAL and the paths). Run from the repo root:
#   deploy/metal_vm.sh rfvm2
# Needs METAL_RPC_URL / METAL_RPC_SECRET already in /etc/ringfence/env (deploy/push_env.py). The faucet is per IP and slow:
# the setup step funds 100 USDZ about once a minute, 10 a day. One demo top-up pulls about 800 USDZ.
set -euo pipefail
T=${1:?usage: deploy/metal_vm.sh <ssh-alias>}
ssh "$T" 'set -e
  V=$(curl -fsSL https://nodejs.org/dist/index.json | python3 -c "import json,sys; print([r[\"version\"] for r in json.load(sys.stdin) if r[\"version\"].startswith(\"v22.\") and r[\"lts\"]][0])")
  cd /tmp && curl -fsSL https://nodejs.org/dist/$V/node-$V-linux-x64.tar.xz -o node.tar.xz
  curl -fsSL https://nodejs.org/dist/$V/SHASUMS256.txt | grep linux-x64.tar.xz | sed "s#node-.*#node.tar.xz#" | sha256sum -c -
  sudo mkdir -p /opt/node /opt/metal_pkg /var/lib/ringfence/metal && sudo tar -xJf node.tar.xz -C /opt/node --strip-components=1
  sudo chown ringfence:ringfence /opt/metal_pkg /var/lib/ringfence/metal
  sudo -u ringfence env PATH=/opt/node/bin:$PATH HOME=/var/lib/ringfence sh -c "cd /opt/metal_pkg && npm init -y >/dev/null && npm install --no-audit --no-fund @metalntwx/metal-agent@0.3.3"
  sudo systemd-run --unit=metal-setup --uid=ringfence --property=EnvironmentFile=/etc/ringfence/env \
    -E PATH=/opt/node/bin:/usr/local/bin:/usr/bin:/bin -E HOME=/var/lib/ringfence -E PYTHONUNBUFFERED=1 \
    -E RF_METAL_CLI=/opt/metal_pkg/node_modules/@metalntwx/metal-agent/dist/index.js -E RF_METAL_DIR=/var/lib/ringfence/metal \
    --working-directory=/opt/ringfence /opt/ringfence/.venv/bin/python scripts/metal_setup.py 1000
  echo "follow with: sudo journalctl -u metal-setup -f"'
