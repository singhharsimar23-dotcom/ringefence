#!/usr/bin/env bash
# Add /alta to a VM that already runs Ringfence (deploy/deploy.sh has shipped the code). Additive: the main service is not touched.
#   deploy/alta_vm.sh rfvm2
# Installs ringfence-alta.service (port 8010) and adds one /alta block to the Caddyfile, above the catch-all, if it is missing.
set -euo pipefail
T=${1:?usage: deploy/alta_vm.sh <ssh-alias>}
ssh "$T" 'set -e; cd /opt/ringfence
  sudo install -m644 deploy/ringfence-alta.service /etc/systemd/system/ringfence-alta.service
  sudo systemctl daemon-reload && sudo systemctl enable -q ringfence-alta && sudo systemctl restart ringfence-alta
  if ! grep -q "handle /alta" /etc/caddy/Caddyfile; then
    sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.bak
    sudo sed -i "0,/reverse_proxy 127.0.0.1:8000/s##handle /alta* {\n\t\treverse_proxy 127.0.0.1:8010\n\t}\n\treverse_proxy 127.0.0.1:8000#" /etc/caddy/Caddyfile
    sudo caddy validate --config /etc/caddy/Caddyfile --adapter caddyfile && sudo systemctl reload caddy
  fi
  sleep 3; systemctl is-active ringfence-alta && curl -s -o /dev/null -w "local /alta %{http_code}\n" http://127.0.0.1:8010/alta'
