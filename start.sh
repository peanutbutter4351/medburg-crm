#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# Medburg CRM — Quick Gunicorn Start (development / manual testing only)
#
# For PRODUCTION: use systemd → `sudo systemctl start medburg`
# This script is for:
#   - Manual smoke-testing the WSGI application outside systemd
#   - Testing Gunicorn config changes before committing to systemd
#
# Usage: bash start.sh
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV="${SCRIPT_DIR}/venv"

if [[ ! -f "${VENV}/bin/gunicorn" ]]; then
    echo "ERROR: virtualenv not found at ${VENV}"
    echo "       Run: python -m venv venv && pip install -r requirements.txt"
    exit 1
fi

exec "${VENV}/bin/gunicorn" \
    --config "${SCRIPT_DIR}/deploy/gunicorn.conf.py" \
    medburg_crm.wsgi:application