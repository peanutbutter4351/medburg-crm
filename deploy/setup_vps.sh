#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Medburg CRM — One-Time VPS Setup Script
# File: deploy/setup_vps.sh
#
# Run ONCE on a fresh Ubuntu VPS as root (or sudo):
#   sudo bash deploy/setup_vps.sh
#
# What this does:
#   1. Creates the dedicated service user (medburg)
#   2. Creates all required VPS directories with correct ownership
#   3. Installs the systemd service unit
#   4. Installs the Nginx vhost config
#   5. Prints next steps
#
# Compatible with: Ubuntu 20.04 / 22.04 / 24.04
# Future-safe for: second project (Lordtip CRM) — just duplicate with new names
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Configuration ─────────────────────────────────────────────────────────────
APP_NAME="medburg"
APP_DIR="/var/www/medburg_crm"
LOG_DIR="/var/log/medburg"
BACKUP_DIR="/var/backups/medburg"
APP_USER="medburg"
APP_GROUP="www-data"   # Nginx runs as www-data; shared group for socket access
DEPLOY_DIR="${APP_DIR}/deploy"

# ── Colors ────────────────────────────────────────────────────────────────────
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

info()    { echo -e "${GREEN}[INFO]${NC}  $*"; }
warn()    { echo -e "${YELLOW}[WARN]${NC}  $*"; }
error()   { echo -e "${RED}[ERROR]${NC} $*"; exit 1; }

# ── Guard ─────────────────────────────────────────────────────────────────────
[[ $EUID -ne 0 ]] && error "Run this script as root (sudo bash deploy/setup_vps.sh)"

info "=== Medburg CRM VPS Setup ==="

# ── 1. Create service user ─────────────────────────────────────────────────────
if id "$APP_USER" &>/dev/null; then
    warn "User '$APP_USER' already exists — skipping creation"
else
    info "Creating service user: $APP_USER"
    useradd \
        --system \
        --no-create-home \
        --shell /usr/sbin/nologin \
        --comment "Medburg CRM service account" \
        "$APP_USER"
    info "User '$APP_USER' created"
fi

# Add app user to www-data group so it can write to Nginx-readable paths
usermod -aG "$APP_GROUP" "$APP_USER"

# ── 2. Create application directories ─────────────────────────────────────────
info "Creating application directories..."

# Application root — code, venv, .env.prod
mkdir -p "${APP_DIR}"
chown "${APP_USER}:${APP_GROUP}" "${APP_DIR}"
chmod 755 "${APP_DIR}"

# Media uploads — Nginx reads, Django writes
mkdir -p "${APP_DIR}/media"
chown "${APP_USER}:${APP_GROUP}" "${APP_DIR}/media"
chmod 775 "${APP_DIR}/media"

# Static files — collectstatic output
mkdir -p "${APP_DIR}/staticfiles"
chown "${APP_USER}:${APP_GROUP}" "${APP_DIR}/staticfiles"
chmod 755 "${APP_DIR}/staticfiles"

# ── 3. Create log directory ────────────────────────────────────────────────────
info "Creating log directory: $LOG_DIR"
mkdir -p "$LOG_DIR"
chown "${APP_USER}:${APP_USER}" "$LOG_DIR"
chmod 750 "$LOG_DIR"

# ── 4. Create backup directory ─────────────────────────────────────────────────
info "Creating backup directory: $BACKUP_DIR"
mkdir -p "$BACKUP_DIR"
chown root:root "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

# ── 5. /run/gunicorn — handled by systemd RuntimeDirectory ────────────────────
# systemd creates /run/gunicorn on each boot via RuntimeDirectory=gunicorn
# in the service unit. We do NOT create it here — systemd owns it.
info "/run/gunicorn will be created by systemd at service start (RuntimeDirectory)"

# ── 6. Install systemd service ────────────────────────────────────────────────
info "Installing systemd service unit..."
if [[ -f "${DEPLOY_DIR}/medburg.service" ]]; then
    cp "${DEPLOY_DIR}/medburg.service" /etc/systemd/system/medburg.service
    chmod 644 /etc/systemd/system/medburg.service
    systemctl daemon-reload
    info "systemd unit installed: /etc/systemd/system/medburg.service"
else
    warn "Service file not found at ${DEPLOY_DIR}/medburg.service — install manually"
fi

# ── 7. Install Nginx vhost ────────────────────────────────────────────────────
info "Installing Nginx virtual host config..."
if [[ -f "${DEPLOY_DIR}/nginx/medburg_crm.conf" ]]; then
    cp "${DEPLOY_DIR}/nginx/medburg_crm.conf" /etc/nginx/sites-available/medburg_crm
    # Enable if not already linked
    if [[ ! -L "/etc/nginx/sites-enabled/medburg_crm" ]]; then
        ln -sf /etc/nginx/sites-available/medburg_crm \
                /etc/nginx/sites-enabled/medburg_crm
    fi
    # Disable default site if it exists
    if [[ -L "/etc/nginx/sites-enabled/default" ]]; then
        rm /etc/nginx/sites-enabled/default
        warn "Removed default Nginx site (replace with your own if needed)"
    fi
    nginx -t && systemctl reload nginx
    info "Nginx vhost installed and reloaded"
else
    warn "Nginx config not found at ${DEPLOY_DIR}/nginx/medburg_crm.conf — install manually"
fi

# ── 8. .env.prod permissions ───────────────────────────────────────────────────
if [[ -f "${APP_DIR}/.env.prod" ]]; then
    chown "${APP_USER}:${APP_USER}" "${APP_DIR}/.env.prod"
    chmod 600 "${APP_DIR}/.env.prod"
    info ".env.prod permissions hardened (600)"
else
    warn ".env.prod not found at ${APP_DIR}/.env.prod"
    warn "Copy it manually: sudo cp .env.prod ${APP_DIR}/.env.prod && sudo chmod 600 ${APP_DIR}/.env.prod"
fi

# ── Summary ───────────────────────────────────────────────────────────────────
echo ""
info "=== Setup Complete ==="
echo ""
echo "  Directory layout:"
echo "    ${APP_DIR}/            ← Application root"
echo "    ${APP_DIR}/media/      ← User uploads (Nginx serves)"
echo "    ${APP_DIR}/staticfiles/ ← collectstatic output"
echo "    ${LOG_DIR}/            ← Django rotating logs"
echo "    ${BACKUP_DIR}/         ← Database / media backups"
echo "    /run/gunicorn/         ← Socket + PID (systemd tmpfs, recreated on boot)"
echo ""
echo "  Next steps:"
echo "    1. Deploy code:      sudo -u medburg git pull"
echo "    2. Install deps:     sudo -u medburg ./venv/bin/pip install -r requirements.txt"
echo "    3. Run migrations:   sudo -u medburg ./venv/bin/python manage.py migrate"
echo "    4. Collect static:   sudo -u medburg ./venv/bin/python manage.py collectstatic --no-input"
echo "    5. Start service:    sudo systemctl enable --now medburg"
echo "    6. Install SSL:      sudo certbot --nginx -d yourdomain.com"
echo "    7. Verify:           sudo systemctl status medburg"
echo "                         sudo journalctl -u medburg -f"
