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
MANAGE="${PYTHON} ${APP_DIR}/manage.py"

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'
step() { echo -e "\n${GREEN}▶ $*${NC}"; }
warn() { echo -e "${YELLOW}⚠ $*${NC}"; }

cd "$APP_DIR"

step "1/6  Pulling latest code from git..."
git pull origin main

step "2/6  Installing Python dependencies..."
"$PIP" install --upgrade pip --quiet
"$PIP" install -r requirements.txt --quiet

step "3/6  Running database migrations..."
DJANGO_SETTINGS_MODULE=medburg_crm.settings.production \
    "$MANAGE" migrate --no-input

step "4/6  Collecting static files..."
DJANGO_SETTINGS_MODULE=medburg_crm.settings.production \
    "$MANAGE" collectstatic --no-input --clear

step "5/6  Running Django system checks..."
DJANGO_SETTINGS_MODULE=medburg_crm.settings.production \
    "$MANAGE" check --deploy 2>&1 | grep -v "^System check" || true

step "6/6  Reloading Gunicorn (zero-downtime)..."
# systemctl reload sends SIGHUP to the Gunicorn master process.
# The master forks new workers with the updated code, then gracefully
# shuts down the old workers after they finish current requests.
if systemctl is-active --quiet medburg; then
    sudo systemctl reload medburg
    echo "  Gunicorn reloaded successfully"
else
    warn "Service 'medburg' is not running — starting it now..."
    sudo systemctl start medburg
fi

echo ""
echo -e "${GREEN}✓ Deployment complete!${NC}"
echo ""
echo "  Useful commands:"
echo "    Status:   sudo systemctl status medburg"
echo "    Logs:     sudo journalctl -u medburg -f"
echo "    App log:  tail -f /var/log/medburg/app.log"
echo "    Err log:  tail -f /var/log/medburg/error.log"
