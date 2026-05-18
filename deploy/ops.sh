#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Medburg CRM — Service Operations & Maintenance Script
# File: deploy/ops.sh
#
# A single command-line interface for all day-to-day VPS operations.
# Run as the medburg user (or deploy user with sudo -u medburg).
#
# Usage:
#   bash /var/www/medburg_crm/deploy/ops.sh <command>
#
# Commands:
#   status      — Service health + recent log tail
#   logs        — Follow live journal logs (Ctrl+C to exit)
#   workers     — Show Gunicorn master + worker processes
#   socket      — Verify socket exists and test HTTP response
#   restart     — Graceful service restart (brief ~1-2s gap)
#   stop        — Stop the service
#   start       — Start the service
#   reset       — Reset failed state after restart loop exhaustion
#   rollback    — Rollback to previous git commit and restart
#   pgcheck     — Verify PostgreSQL connectivity
#   check       — Run Django production system checks
#   perms       — Audit critical file permissions
#   journal     — Show last 100 journal lines (no follow)
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

APP_DIR="/var/www/medburg_crm"
VENV="${APP_DIR}/venv"
PYTHON="${VENV}/bin/python"
SERVICE="medburg"

# Colors
GREEN='\033[0;32m'; YELLOW='\033[1;33m'; RED='\033[0;31m'; CYAN='\033[0;36m'; NC='\033[0m'
ok()    { echo -e "${GREEN}✓ $*${NC}"; }
warn()  { echo -e "${YELLOW}⚠ $*${NC}"; }
error() { echo -e "${RED}✗ $*${NC}"; }
head()  { echo -e "\n${CYAN}══ $* ══${NC}"; }

# Load env
_load_env() {
    if [[ -f "${APP_DIR}/.env.prod" ]]; then
        set -o allexport
        # shellcheck source=/dev/null
        source "${APP_DIR}/.env.prod"
        set +o allexport
        export DJANGO_SETTINGS_MODULE="medburg_crm.settings.production"
    else
        error ".env.prod not found at ${APP_DIR}/.env.prod"
        exit 1
    fi
}

CMD="${1:-help}"

case "$CMD" in

# ── status ────────────────────────────────────────────────────────────────────
status)
    head "Service Status"
    sudo systemctl status "$SERVICE" --no-pager --lines=10 || true

    head "Socket"
    if [[ -S "/run/gunicorn/${SERVICE}.sock" ]]; then
        ls -la "/run/gunicorn/${SERVICE}.sock"
        ok "Socket exists"
    else
        error "Socket missing at /run/gunicorn/${SERVICE}.sock"
    fi

    head "Workers"
    WORKER_COUNT=$(ps aux | grep "[g]unicorn.*${SERVICE}" | wc -l)
    echo "  ${WORKER_COUNT} Gunicorn processes (1 master + $(( WORKER_COUNT - 1 )) workers)"

    head "Last 10 Error Log Lines"
    sudo -u "$SERVICE" tail -10 "/var/log/${SERVICE}/error.log" 2>/dev/null || \
        warn "Error log empty or not yet created"
    ;;

# ── logs ──────────────────────────────────────────────────────────────────────
logs)
    echo -e "${CYAN}Following journal logs — Ctrl+C to exit${NC}"
    sudo journalctl -u "$SERVICE" -f
    ;;

# ── workers ───────────────────────────────────────────────────────────────────
workers)
    head "Gunicorn Process Tree"
    ps auxf | grep -A 50 "[g]unicorn.*${SERVICE}" | head -20 || \
        warn "No Gunicorn processes found. Is the service running?"
    ;;

# ── socket ────────────────────────────────────────────────────────────────────
socket)
    head "Unix Socket Verification"
    SOCK="/run/gunicorn/${SERVICE}.sock"
    if [[ ! -S "$SOCK" ]]; then
        error "Socket not found: $SOCK"
        exit 1
    fi
    ls -la "$SOCK"

    echo ""
    echo "Testing HTTP through socket..."
    HTTP_CODE=$(curl --silent --output /dev/null --write-out "%{http_code}" \
        --unix-socket "$SOCK" http://localhost/ 2>/dev/null || echo "000")

    if [[ "$HTTP_CODE" == "302" || "$HTTP_CODE" == "200" ]]; then
        ok "Django responded: HTTP $HTTP_CODE (expected: 302 → /accounts/login/)"
    elif [[ "$HTTP_CODE" == "000" ]]; then
        error "No response from socket — is Gunicorn running?"
    else
        warn "Unexpected HTTP code: $HTTP_CODE"
    fi
    ;;

# ── restart ───────────────────────────────────────────────────────────────────
restart)
    head "Graceful Restart"
    warn "Service will be briefly unavailable (~1-2s) during restart"
    sudo systemctl restart "$SERVICE"
    sleep 3
    if sudo systemctl is-active --quiet "$SERVICE"; then
        ok "Service restarted and is active"
        ps aux | grep "[g]unicorn.*${SERVICE}" | grep -v grep || true
    else
        error "Service failed to restart"
        sudo journalctl -u "$SERVICE" -n 20 --no-pager
        exit 1
    fi
    ;;

# ── stop ──────────────────────────────────────────────────────────────────────
stop)
    head "Stopping Service"
    warn "This will take the CRM offline"
    read -r -p "  Are you sure? [y/N] " CONFIRM
    [[ "${CONFIRM:-N}" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }
    sudo systemctl stop "$SERVICE"
    ok "Service stopped"
    ;;

# ── start ─────────────────────────────────────────────────────────────────────
start)
    head "Starting Service"
    sudo systemctl start "$SERVICE"
    sleep 3
    sudo systemctl is-active --quiet "$SERVICE" && ok "Service started" || \
        { error "Service failed to start"; sudo journalctl -u "$SERVICE" -n 20 --no-pager; exit 1; }
    ;;

# ── reset ─────────────────────────────────────────────────────────────────────
reset)
    head "Resetting Failed State"
    echo "  This clears the StartLimitBurst failure counter so systemd will"
    echo "  attempt to restart the service again."
    sudo systemctl reset-failed "$SERVICE"
    ok "Failed state cleared. Now run: bash ops.sh start"
    ;;

# ── rollback ──────────────────────────────────────────────────────────────────
rollback)
    head "Rollback to Previous Commit"
    cd "$APP_DIR"

    CURRENT=$(git rev-parse --short HEAD)
    PREVIOUS=$(git rev-parse --short HEAD~1)
    echo "  Current commit:  $CURRENT"
    echo "  Rollback target: $PREVIOUS"
    echo ""
    warn "This will revert code to the previous commit and restart Gunicorn."
    read -r -p "  Proceed? [y/N] " CONFIRM
    [[ "${CONFIRM:-N}" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

    # Stash any uncommitted changes (shouldn't be any on prod, but safety first)
    git stash --quiet 2>/dev/null || true

    git checkout HEAD~1

    _load_env
    "$MANAGE" migrate --no-input 2>&1 | tail -5
    "$MANAGE" collectstatic --no-input 2>&1 | tail -3

    sudo systemctl restart "$SERVICE"
    sleep 3
    sudo systemctl is-active --quiet "$SERVICE" && \
        ok "Rolled back to $PREVIOUS and service restarted" || \
        error "Rollback applied but service failed to start — check journalctl"
    echo ""
    echo "  To return to latest: git checkout main && bash deploy.sh"
    ;;

# ── pgcheck ───────────────────────────────────────────────────────────────────
pgcheck)
    head "PostgreSQL Connectivity Check"
    _load_env
    cd "$APP_DIR"
    "$PYTHON" -c "
import django, os
django.setup()
from django.db import connection
try:
    with connection.cursor() as c:
        c.execute('SELECT version()')
        print('  ✓ Connected:', c.fetchone()[0][:60])
except Exception as e:
    print('  ✗ Failed:', e)
    exit(1)
"
    ;;

# ── check ─────────────────────────────────────────────────────────────────────
check)
    head "Django Production System Check"
    _load_env
    cd "$APP_DIR"
    "$PYTHON" manage.py check --deploy 2>&1
    ;;

# ── perms ─────────────────────────────────────────────────────────────────────
perms)
    head "Critical Permission Audit"

    _check() {
        local path="$1" expected_mode="$2" expected_owner="$3"
        if [[ ! -e "$path" ]]; then
            error "Missing: $path"
            return
        fi
        local mode owner
        mode=$(stat -c "%a" "$path")
        owner=$(stat -c "%U:%G" "$path")
        if [[ "$mode" == "$expected_mode" && "$owner" == "$expected_owner" ]]; then
            ok "$path  mode=$mode  owner=$owner"
        else
            warn "$path  mode=$mode (expected $expected_mode)  owner=$owner (expected $expected_owner)"
        fi
    }

    _check "${APP_DIR}/.env.prod"     "600" "medburg:medburg"
    _check "${APP_DIR}"               "755" "medburg:www-data"
    _check "${APP_DIR}/media"         "775" "medburg:www-data"
    _check "${APP_DIR}/staticfiles"   "755" "medburg:www-data"
    _check "/var/log/medburg"         "750" "medburg:medburg"
    _check "/etc/sudoers.d/medburg"   "440" "root:root"
    _check "/etc/systemd/system/medburg.service" "644" "root:root"
    ;;

# ── journal ───────────────────────────────────────────────────────────────────
journal)
    head "Last 100 Journal Lines"
    sudo journalctl -u "$SERVICE" -n 100 --no-pager
    ;;

# ── help ──────────────────────────────────────────────────────────────────────
help|*)
    echo ""
    echo "  Medburg CRM — Operations Script"
    echo ""
    echo "  Usage: bash /var/www/medburg_crm/deploy/ops.sh <command>"
    echo ""
    echo "  Commands:"
    echo "    status    Service health + socket + recent errors"
    echo "    logs      Follow live journal logs"
    echo "    workers   Gunicorn process tree"
    echo "    socket    Verify socket + test HTTP response"
    echo "    restart   Graceful service restart (~1-2s gap)"
    echo "    stop      Stop the service (prompts for confirmation)"
    echo "    start     Start the service"
    echo "    reset     Clear failed-state after restart loop exhaustion"
    echo "    rollback  Revert to previous git commit"
    echo "    pgcheck   Verify PostgreSQL connectivity"
    echo "    check     Run Django production system checks"
    echo "    perms     Audit critical file permissions"
    echo "    journal   Last 100 journal log lines"
    echo ""
    ;;

esac
