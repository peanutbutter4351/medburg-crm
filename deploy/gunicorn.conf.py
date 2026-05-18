# ─────────────────────────────────────────────────────────────────────────────
# Medburg CRM — Gunicorn Configuration
# File: deploy/gunicorn.conf.py
#
# Usage (systemd calls this automatically via --config flag):
#   gunicorn --config /var/www/medburg_crm/deploy/gunicorn.conf.py \
#            medburg_crm.wsgi:application
#
# Worker count formula: (2 × CPU cores) + 1
#   - 1 vCPU VPS  → 3 workers
#   - 2 vCPU VPS  → 5 workers
#   - 4 vCPU VPS  → 9 workers  (typical entry-level cloud instance)
#
# For a Django CRM (sync views, PostgreSQL, no long-poll):
#   - sync workers are correct (no need for gevent/eventlet)
#   - --threads 2 per worker adds concurrency for DB-wait overlap
#
# This config uses UNIX socket (not TCP port) because:
#   1. Faster — no TCP handshake overhead on loopback
#   2. Only Nginx (same server) can connect — no accidental exposure
#   3. Socket path is in /run/ (tmpfs) — survives app crashes, not reboots
#      systemd's RuntimeDirectory= recreates /run/gunicorn/ on each boot
# ─────────────────────────────────────────────────────────────────────────────

import multiprocessing
import os

# ── Binding ──────────────────────────────────────────────────────────────────
# Unix socket in tmpfs — fastest, safest, Nginx-compatible
# /run/gunicorn/ is created by systemd RuntimeDirectory= on each boot
bind = "unix:/run/gunicorn/medburg.sock"

# ── Worker processes ──────────────────────────────────────────────────────────
# Formula: (2 × cores) + 1  — auto-detected at startup
workers = (2 * multiprocessing.cpu_count()) + 1

# Worker class: sync is correct for standard Django CRM views
# Switch to "gevent" only if you add async views or WebSockets
worker_class = "sync"

# Threads per worker: provides concurrency during DB I/O without extra processes
# Each thread shares the worker's memory — safe for thread-safe Django
threads = 2

# Max requests per worker before graceful restart (prevents memory leaks)
# Jitter adds ±50% randomness so workers don't all restart simultaneously
max_requests = 1000
max_requests_jitter = 200

# ── Timeouts ─────────────────────────────────────────────────────────────────
# Worker timeout — kill a worker if it takes longer than this (seconds)
# 30s is conservative for a CRM; increase to 60 for heavy CSV exports
timeout = 30

# Graceful shutdown timeout — how long to wait for in-flight requests to finish
graceful_timeout = 30

# Keep-alive — seconds to wait for next HTTP request on a kept-alive connection
# Match Nginx's keepalive_timeout
keepalive = 5

# ── Process management ────────────────────────────────────────────────────────
# Preload app before forking workers — saves memory (copy-on-write)
# Downside: code changes require full restart (not reload) — acceptable for CRM
preload_app = True

# PID file — used by systemd and management scripts to track the master process
pidfile = "/run/gunicorn/medburg.pid"

# User/group to run workers as — must match systemd User= / Group=
# Set to the dedicated app user created during VPS setup
user = os.environ.get("GUNICORN_USER", "medburg")
group = os.environ.get("GUNICORN_GROUP", "www-data")

# ── File permissions ──────────────────────────────────────────────────────────
# Socket permissions — 0o660 allows Nginx (www-data group) to connect
# The medburg user owns the socket; Nginx connects via group membership
umask = 0o007  # socket gets 0o660 (rw-rw----)

# ── Logging ───────────────────────────────────────────────────────────────────
# "-" routes to stdout/stderr → captured by systemd journal
# Django's own LOGGING config (production.py) writes to /var/log/medburg/
# Gunicorn access/error logs go to journald via systemd
accesslog = "-"    # stdout → systemd journal
errorlog = "-"     # stderr → systemd journal
loglevel = "warning"

# Access log format — structured for parsing with tools like GoAccess / Loki
access_log_format = (
    '%(h)s %(l)s %(u)s %(t)s "%(r)s" %(s)s %(b)s '
    '"%(f)s" "%(a)s" %(D)sµs'
)

# ── Django WSGI application ────────────────────────────────────────────────────
# Redundant when invoked as `gunicorn medburg_crm.wsgi:application`
# but explicit for clarity and tooling compatibility
wsgi_app = "medburg_crm.wsgi:application"

# ── Reload (development note) ─────────────────────────────────────────────────
# Never enable reload=True in production — causes race conditions
# For rolling restarts: `systemctl reload medburg` (sends SIGHUP)
reload = False
