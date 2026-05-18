#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Medburg CRM — Rolling Deployment Script
# File: deploy/deploy.sh
#
# Run from the VPS as the app user (medburg) or via SSH:
#   sudo -u medburg bash /var/www/medburg_crm/deploy/deploy.sh
#
# What this does (zero-downtime rolling deploy):
#   1. Pull latest code from git
#   2. Install/upgrade Python dependencies
#   3. Run Django migrations
#   4. Collect static files
#   5. Gracefully reload Gunicorn (SIGHUP — workers drain before reloading)
#      → In-flight requests are NOT dropped during reload
#
# Gunicorn reload vs restart:
#   reload  (SIGHUP)  → Workers finish current requests, then reload code
#                       ZERO downtime. Use for routine deploys.
#   restart (systemctl restart) → Brief downtime. Use only after:
#                       - Changing the systemd unit file
#                       - Changing gunicorn.conf.py worker count/type
#                       - Major dependency changes (e.g. psycopg2 upgrade)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

APP_DIR="/var/www/medburg_crm"
VENV="${APP_DIR}/venv"
PYTHON="${VENV}/bin/python"
PIP="${VENV}/bin/pip"

# Explicitly set settings module — never rely on wsgi.py default during CLI ops
export DJANGO_SETTINGS_MODULE="medburg_crm.settings.production"

# Load env vars from .env.prod so manage.py commands can reach PostgreSQL
# shellcheck source=/dev/null
if [[ -f "${APP_DIR}/.env.prod" ]]; then
    set -o allexport
    source "${APP_DIR}/.env.prod"
    set +o allexport
else
    echo "ERROR: ${APP_DIR}/.env.prod not found. Aborting."
    exit 1
fi

MANAGE="${PYTHON} ${APP_DIR}/manage.py"
PIDFILE="/run/gunicorn/medburg.pid"

# ── Colors ──────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; NC='\033[0m'
step() { echo -e "\n${GREEN}▶ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠ $*${NC}"; }
error() { echo -e "${RED}✗ $*${NC}"; exit 1; }

cd "$APP_DIR"

step "1/6  Pulling latest code from git..."
git pull origin main

step "2/6  Installing Python dependencies..."
"$PIP" install --upgrade pip --quiet
"$PIP" install -r requirements.txt --quiet

step "3/6  Running database migrations..."
"$MANAGE" migrate --no-input

step "4/6  Collecting static files (atomic — no downtime window)..."
# ⚠ Do NOT use --clear here. It deletes static files then regenerates them,
# creating a window where users get 404s on CSS/JS on a live server.
# The manifest storage already handles cache-busting via content hashes.
"$MANAGE" collectstatic --no-input

step "5/6  Running Django system checks..."
"$MANAGE" check --deploy 2>&1 | grep -v "^System check" || true

step "6/6  Reloading Gunicorn (zero-downtime SIGHUP)..."
# We send SIGHUP directly to the master PID rather than using 'sudo systemctl
# reload' because the medburg service user cannot run sudo without explicit
# sudoers configuration. The medburg user owns the PID file and can signal
# its own process. systemd monitors the master and will restart it if needed.
if [[ -f "$PIDFILE" ]]; then
    MASTER_PID=$(cat "$PIDFILE")
    if kill -0 "$MASTER_PID" 2>/dev/null; then
        kill -HUP "$MASTER_PID"
        echo "  Sent SIGHUP to Gunicorn master PID ${MASTER_PID} — workers draining"
    else
        warn "PID ${MASTER_PID} not alive. Is the service running? Try: sudo systemctl start medburg"
    fi
else
    warn "PID file not found at $PIDFILE. Is the service running?"
    warn "Start it with: sudo systemctl start medburg"
fi

echo ""
echo -e "${GREEN}✓ Deployment complete!${NC}"
echo ""
echo "  Useful commands:"
echo "    Status:   sudo systemctl status medburg"
echo "    Logs:     sudo journalctl -u medburg -f"
echo "    App log:  tail -f /var/log/medburg/app.log"
echo "    Err log:  tail -f /var/log/medburg/error.log"
