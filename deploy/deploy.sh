#!/usr/bin/env bash
# Ship the committed tree to the VM and restart. Run from the repo root in Git Bash:
#   deploy/deploy.sh rf@<host>                    code + deps + service
#   deploy/deploy.sh rf@<host> --first            also copies var/cert_key.pem + var/registry.json (once)
set -euo pipefail
T=${1:?usage: deploy/deploy.sh user@host [--first]}
# shortcut: tar over the old tree never deletes removed files; fine for a demo VM, use a release dir if it lives on
git archive --format=tar HEAD | ssh "$T" 'sudo tar -x -C /opt/ringfence && sudo chown -R ringfence:ringfence /opt/ringfence'
if [[ "${2:-}" == "--first" ]]; then
  # the signing key must match the committed ringfence/cert_pub.pem, or live certificates verify as INVALID
  tar -c -C var cert_key.pem registry.json | ssh "$T" 'sudo -u ringfence tar -x -C /var/lib/ringfence/var && sudo chmod 600 /var/lib/ringfence/var/cert_key.pem'
fi
ssh "$T" 'set -e; cd /opt/ringfence
  sudo -u ringfence env UV_HTTP_TIMEOUT=180 UV_CACHE_DIR=/var/lib/ringfence/.cache/uv /usr/local/bin/uv sync --frozen --no-dev -q
  sudo install -m644 deploy/ringfence.service /etc/systemd/system/ringfence.service
  sudo systemctl daemon-reload && sudo systemctl enable -q ringfence && sudo systemctl restart ringfence
  sleep 4; systemctl is-active ringfence && curl -s -o /dev/null -w "local /api/state %{http_code}\n" http://127.0.0.1:8000/api/state'
