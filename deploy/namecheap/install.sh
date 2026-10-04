#!/usr/bin/env bash
# Install or update E-Rechnungsbote on Namecheap shared hosting (cPanel "Setup Python App").
#
# Run in the cPanel Terminal (or SSH) AFTER creating the Python app, inside its
# virtualenv – cPanel shows the exact "source .../activate" command at the top
# of the app's page. Example:
#   source ~/virtualenv/einvoice/3.11/bin/activate && cd ~/einvoice && bash deploy/namecheap/install.sh
# Re-running is safe: it updates dependencies and restarts the app.
set -euo pipefail

APP_ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
ENV_FILE="${EINVOICE_ENV_FILE:-$HOME/.einvoice-bridge.env}"
DATA_DIR="${EINVOICE_DATA_DIR:-$HOME/einvoice-data}"
DOMAIN="${DOMAIN:-erechnungsbote.de}"

if [ -z "${VIRTUAL_ENV:-}" ]; then
  echo "Please activate the app's virtualenv first (cPanel > Setup Python App shows the command)." >&2
  exit 1
fi
python - <<'PY'
import sys
if sys.version_info < (3, 11):
    sys.exit(f"Python {sys.version.split()[0]} is too old; create the app with Python 3.11 or newer.")
PY

cd "$APP_ROOT"
pip install --upgrade pip >/dev/null
# On older servers (glibc < 2.24) pip picks saxonche 12.5 automatically; it is tested.
pip install -e ".[shared-hosting]"

cp deploy/namecheap/passenger_wsgi.py "$APP_ROOT/passenger_wsgi.py"
mkdir -p "$DATA_DIR/legal" "$APP_ROOT/tmp"
chmod 700 "$DATA_DIR"

if [ ! -f "$ENV_FILE" ]; then
  umask 077
  secret="$(einvoice-bridge secret)"
  sed -e "s|^EINVOICE_SECRET_KEY=.*|EINVOICE_SECRET_KEY=$secret|" \
      -e "s|^EINVOICE_DATA_DIR=.*|EINVOICE_DATA_DIR=$DATA_DIR|" \
      -e "s|^EINVOICE_LEGAL_DIR=.*|EINVOICE_LEGAL_DIR=$DATA_DIR/legal|" \
      -e "s|^EINVOICE_WELL_KNOWN_DIR=.*|EINVOICE_WELL_KNOWN_DIR=$HOME/public_html/.well-known|" \
      -e "s|^EINVOICE_FORCE_HTTPS=.*|EINVOICE_FORCE_HTTPS=1|" \
      -e "s|erechnungsbote.de|$DOMAIN|g" \
      -e "s|^SMTP_HOST=.*|SMTP_HOST=mail.privateemail.com|" \
      -e "s|^SMTP_USER=.*|SMTP_USER=rechnung@$DOMAIN|" \
      deploy/einvoice-bridge.env.example > "$ENV_FILE"
  echo "Created $ENV_FILE (mode 600). Back up the EINVOICE_SECRET_KEY line somewhere safe."
  echo "Next: put the mailbox password into SMTP_PASSWORD in that file."
fi

# Passenger restarts the app when this file's timestamp changes.
touch "$APP_ROOT/tmp/restart.txt"

einvoice-bridge doctor --env-file "$ENV_FILE" || true
echo
echo "Done. Open https://$DOMAIN – the first request after a restart can take a few seconds."
