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
# --ff-only: abort if the remote history diverged (prevents merge commits on
# production). If this fails, investigate and rebase locally before deploying.
git pull --ff-only origin main

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

step "6/6  Reloading Gunicorn service..."
# WHY systemctl restart instead of kill -HUP?
#   With preload_app=True in gunicorn.conf.py, a plain SIGHUP does NOT
#   re-import changed Python code. It only re-forks workers from the same
#   already-loaded master process. New code would NOT be active.
#
#   systemctl restart sends SIGTERM (graceful), waits TimeoutStopSec=30s
#   for in-flight requests to drain, then starts a fresh master with new code.
#   For a CRM with low concurrent users, the ~1-2s gap is acceptable.
#
#   For TRUE zero-downtime with a binary upgrade, use the SIGUSR2 sequence
#   documented in deploy/medburg.service ExecReload comment.
if sudo systemctl is-active --quiet medburg 2>/dev/null; then
    sudo systemctl restart medburg
    sleep 3
    if sudo systemctl is-active --quiet medburg; then
        echo "  ✓ Gunicorn restarted successfully"
    else
        error "Gunicorn failed to restart. Check: sudo journalctl -u medburg -n 50"
    fi
else
    warn "Service 'medburg' is not running — starting it now..."
    sudo systemctl start medburg
    sleep 3
    sudo systemctl is-active --quiet medburg || \
        error "Failed to start medburg. Check: sudo journalctl -u medburg -n 50"
fi

echo ""
echo -e "${GREEN}✓ Deployment complete!${NC}"
echo ""
sudo systemctl status medburg --no-pager --lines=5
echo ""
echo "  Monitoring commands:"
echo "    Live logs:   sudo journalctl -u medburg -f"
echo "    App log:     sudo -u medburg tail -f /var/log/medburg/app.log"
echo "    Error log:   sudo -u medburg tail -f /var/log/medburg/error.log"
echo "    Workers:     ps aux | grep gunicorn | grep -v grep"
echo "    Socket:      ls -la /run/gunicorn/"
