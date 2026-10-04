#!/usr/bin/env bash
# One-time setup of a fresh Ubuntu 24.04 server (e.g. Hetzner Cloud CX23).
# Usage, as root:  bash setup-server.sh   (DOMAIN defaults to erechnungsbote.de)
# Private repository: REPO_URL=https://<token>@github.com/<owner>/<repo>.git (read-only token)
# Re-running is safe: it updates the code and restarts the service.
set -euo pipefail

DOMAIN="${DOMAIN:-erechnungsbote.de}"
REPO_URL="${REPO_URL:-https://github.com/satishkodidela/AgentEarning.git}"
# Until the work is merged, the code lives on this branch.
BRANCH="${BRANCH:-claude/determined-lovelace-gxddxl}"
APP_DIR=/opt/einvoice-bridge
DATA_DIR=/var/lib/einvoice
ENV_FILE=/etc/einvoice-bridge.env

apt-get update
apt-get install -y python3-venv git caddy ufw unattended-upgrades

# Firewall: SSH and web only.
ufw allow OpenSSH
ufw allow http
ufw allow https
ufw --force enable

id einvoice >/dev/null 2>&1 || useradd --system --home "$DATA_DIR" --shell /usr/sbin/nologin einvoice
install -d -o einvoice -g einvoice -m 750 "$DATA_DIR" "$DATA_DIR/legal"

if [ -d "$APP_DIR/.git" ]; then
  git -C "$APP_DIR" fetch origin "$BRANCH" && git -C "$APP_DIR" checkout -B "$BRANCH" "origin/$BRANCH"
else
  git clone --branch "$BRANCH" "$REPO_URL" "$APP_DIR"
fi
python3 -m venv "$APP_DIR/.venv"
"$APP_DIR/.venv/bin/pip" install --upgrade pip
"$APP_DIR/.venv/bin/pip" install "$APP_DIR"

if [ ! -f "$ENV_FILE" ]; then
  install -m 600 "$APP_DIR/deploy/einvoice-bridge.env.example" "$ENV_FILE"
  secret="$("$APP_DIR/.venv/bin/einvoice-bridge" secret)"
  sed -i "s|^EINVOICE_SECRET_KEY=.*|EINVOICE_SECRET_KEY=$secret|; s|erechnungsbote.de|$DOMAIN|g" "$ENV_FILE"
  echo "Created $ENV_FILE – add the SMTP credentials, then: systemctl restart einvoice-bridge"
fi

install -m 644 "$APP_DIR/deploy/einvoice-bridge.service" /etc/systemd/system/einvoice-bridge.service
install -m 644 "$APP_DIR/deploy/Caddyfile" /etc/caddy/Caddyfile
mkdir -p /etc/systemd/system/caddy.service.d
printf '[Service]\nEnvironment=EINVOICE_DOMAIN=%s\n' "$DOMAIN" > /etc/systemd/system/caddy.service.d/domain.conf

systemctl daemon-reload
systemctl enable --now einvoice-bridge
systemctl restart einvoice-bridge caddy
sleep 2
curl -fsS http://127.0.0.1:8000/health && echo " – app is up. Open https://$DOMAIN once DNS points here."
