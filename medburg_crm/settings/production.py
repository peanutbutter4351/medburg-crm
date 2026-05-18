"""
Medburg CRM — Production Settings

Activated on the VPS by setting:
    DJANGO_SETTINGS_MODULE=medburg_crm.settings.production

Requirements:
    - DJANGO_SECRET_KEY must be set (crashes on startup otherwise)
    - DJANGO_ALLOWED_HOSTS must include the real domain or IP
    - PostgreSQL credentials via POSTGRES_* env vars

Environment variables (all optional except SECRET_KEY & ALLOWED_HOSTS):
    DJANGO_MEDIA_ROOT       → absolute path for uploads   (default: /var/www/medburg_crm/media)
    DJANGO_LOG_DIR          → directory for rotating logs (default: /var/log/medburg)
    DJANGO_LOG_LEVEL        → root log level              (default: WARNING)
    DJANGO_APP_LOG_LEVEL    → medburg app log level       (default: INFO)
    DJANGO_SECURE_SSL_REDIRECT → enable SSL redirect      (default: True)
    DJANGO_HSTS_SECONDS     → HSTS max-age in seconds     (default: 31536000)
    POSTGRES_REQUIRE_SSL    → enforce SSL on PG connection (default: False)

Designed for:
    - Ubuntu VPS with Gunicorn + Nginx + PostgreSQL
    - Future Docker / AWS compatibility
    - Multi-project VPS hosting (each project gets its own systemd unit)
"""

import os
import logging
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401,F403


# ──────────────────────────────────────────────────────────────────
# Helper — fail loud on missing required env vars
# ──────────────────────────────────────────────────────────────────
def _require_env(name: str) -> str:
    """Return env var value or raise ImproperlyConfigured immediately."""
    value = os.environ.get(name, "").strip()
    if not value:
        raise ImproperlyConfigured(
            f"Required environment variable '{name}' is not set. "
            f"Add it to your systemd unit or .env.prod file."
        )
    return value


# ──────────────────────────────────────────────────────────────────
# Core security
# ──────────────────────────────────────────────────────────────────
DEBUG = False

SECRET_KEY = _require_env("DJANGO_SECRET_KEY")

ALLOWED_HOSTS = [
    h.strip()
    for h in _require_env("DJANGO_ALLOWED_HOSTS").split(",")
    if h.strip()
]

# ──────────────────────────────────────────────────────────────────
# Database — PostgreSQL
# ──────────────────────────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB"),
        "USER": os.environ.get("POSTGRES_USER"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD"),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        "OPTIONS": {
            "connect_timeout": 5,
        },
        # Connection pooling — reduces overhead per Gunicorn worker request
        "CONN_MAX_AGE": int(os.environ.get("DJANGO_CONN_MAX_AGE", "60")),
    }
}

# Enforce SSL for remote/managed PostgreSQL providers
if os.environ.get("POSTGRES_REQUIRE_SSL", "").lower() in ("true", "1", "yes"):
    DATABASES["default"]["OPTIONS"]["sslmode"] = "require"

# ──────────────────────────────────────────────────────────────────
# Static files — WhiteNoise with compression + manifest hashing
# ──────────────────────────────────────────────────────────────────
# WhiteNoise serves static files directly from Gunicorn (no Nginx needed
# for static).  CompressedManifestStaticFilesStorage adds content-hash
# fingerprinting so assets can be cached forever.
#
# To switch to pure Nginx static serving, remove the WhiteNoise middleware
# from MIDDLEWARE in base.py and point Nginx at STATIC_ROOT.
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# ──────────────────────────────────────────────────────────────────
# Media files — VPS path override
# ──────────────────────────────────────────────────────────────────
# In production, media lives outside the project directory so it
# survives re-deployments.  Nginx serves /media/ directly; Gunicorn
# never sees media requests.
#
# Recommended VPS path: /var/www/medburg_crm/media/
# Set DJANGO_MEDIA_ROOT in systemd unit or .env.prod.
_DEFAULT_MEDIA_ROOT = "/var/www/medburg_crm/media"
MEDIA_ROOT = Path(os.environ.get("DJANGO_MEDIA_ROOT", _DEFAULT_MEDIA_ROOT))

# ──────────────────────────────────────────────────────────────────
# Security headers & cookies
# ──────────────────────────────────────────────────────────────────
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"

# SSL redirect — disable during initial setup before Nginx TLS is live
SECURE_SSL_REDIRECT = os.environ.get(
    "DJANGO_SECURE_SSL_REDIRECT", "True"
).lower() in ("true", "1", "yes")

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

# HSTS — enable only after SSL is confirmed end-to-end
SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_HSTS_SECONDS", "31536000"))
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True

# Trust Nginx's X-Forwarded-Proto header so Django knows requests arrive over HTTPS
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# ──────────────────────────────────────────────────────────────────
# Logging — production-grade rotating file logs
# ──────────────────────────────────────────────────────────────────
# Directory layout on VPS:
#   /var/log/medburg/
#       app.log        → INFO+  application events  (10 MB × 5 backups)
#       error.log      → ERROR+ critical failures   (10 MB × 5 backups)
#       security.log   → WARNING+ security events   (10 MB × 3 backups)
#
# Console handler (stderr) is intentionally kept active so Gunicorn's
# systemd journal also captures log lines without duplicating to files.
#
# To adjust log level set DJANGO_LOG_LEVEL / DJANGO_APP_LOG_LEVEL in .env.prod.
_LOG_DIR = Path(os.environ.get("DJANGO_LOG_DIR", "/var/log/medburg"))
_LOG_LEVEL = os.environ.get("DJANGO_LOG_LEVEL", "WARNING").upper()
_APP_LOG_LEVEL = os.environ.get("DJANGO_APP_LOG_LEVEL", "INFO").upper()

# Ensure log directory exists at startup (VPS: created by server-setup script)
# This is a no-op if the directory already exists.
try:
    _LOG_DIR.mkdir(parents=True, exist_ok=True)
except OSError:
    # Fallback: log directory may not be writable yet (e.g. first deploy).
    # Logging will still work via console handler.
    logging.warning(
        "Could not create log directory %s. File logging will be unavailable "
        "until the directory exists and is writable by the app user.",
        _LOG_DIR,
    )

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,

    # ── Formatters ───────────────────────────────────────────────
    "formatters": {
        # Rich format for file logs — timestamp, level, logger, PID, message
        "verbose": {
            "format": "[{asctime}] {levelname:<8} pid={process:d} {name} — {message}",
            "style": "{",
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        # Compact format for console / Gunicorn journal
        "console": {
            "format": "{levelname:<8} {name}: {message}",
            "style": "{",
        },
        # JSON-friendly format for future log-shipping (e.g. Loki, CloudWatch)
        "json_ready": {
            "format": (
                '{{"time": "{asctime}", "level": "{levelname}", '
                '"logger": "{name}", "pid": {process:d}, "message": "{message}"}}'
            ),
            "style": "{",
            "datefmt": "%Y-%m-%dT%H:%M:%S",
        },
    },

    # ── Filters ──────────────────────────────────────────────────
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
    },

    # ── Handlers ─────────────────────────────────────────────────
    "handlers": {
        # Console → captured by Gunicorn/systemd journal
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "console",
            "level": "WARNING",
        },

        # Application log — INFO+ (access patterns, business events)
        "app_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(_LOG_DIR / "app.log"),
            "maxBytes": 10 * 1024 * 1024,   # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
            "encoding": "utf-8",
            "level": "INFO",
        },

        # Error log — ERROR+ only (operational alerts, PagerDuty-ready)
        "error_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(_LOG_DIR / "error.log"),
            "maxBytes": 10 * 1024 * 1024,   # 10 MB
            "backupCount": 5,
            "formatter": "verbose",
            "encoding": "utf-8",
            "level": "ERROR",
        },

        # Security log — suspicious requests, permission denials
        "security_file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": str(_LOG_DIR / "security.log"),
            "maxBytes": 10 * 1024 * 1024,   # 10 MB
            "backupCount": 3,
            "formatter": "verbose",
            "encoding": "utf-8",
            "level": "WARNING",
        },
    },

    # ── Root logger ───────────────────────────────────────────────
    "root": {
        "handlers": ["console", "app_file", "error_file"],
        "level": _LOG_LEVEL,
    },

    # ── Named loggers ─────────────────────────────────────────────
    "loggers": {
        # Django internals — warnings + errors only
        "django": {
            "handlers": ["console", "app_file", "error_file"],
            "level": "WARNING",
            "propagate": False,
        },

        # HTTP request/response cycle — errors routed to error.log
        "django.request": {
            "handlers": ["error_file", "console"],
            "level": "ERROR",
            "propagate": False,
        },

        # Database query logging — disabled in prod (enable for debugging only)
        "django.db.backends": {
            "handlers": ["error_file"],
            "level": "ERROR",
            "propagate": False,
        },

        # Security events — CSRF failures, permission denials, etc.
        "django.security": {
            "handlers": ["security_file", "console"],
            "level": "WARNING",
            "propagate": False,
        },

        # ── Application loggers ───────────────────────────────────
        # Usage: import logging; logger = logging.getLogger("medburg.sales")
        "medburg": {
            "handlers": ["app_file", "error_file", "console"],
            "level": _APP_LOG_LEVEL,
            "propagate": False,
        },
    },
}

# ──────────────────────────────────────────────────────────────────
# Production deployment safety check
# ──────────────────────────────────────────────────────────────────
# Validate critical PostgreSQL variables are present.
# These will be caught at startup rather than at the first DB query.
_REQUIRED_PG_VARS = ["POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD"]
_missing_pg = [v for v in _REQUIRED_PG_VARS if not os.environ.get(v, "").strip()]
if _missing_pg:
    raise ImproperlyConfigured(
        f"Missing required PostgreSQL environment variables: {', '.join(_missing_pg)}. "
        f"Add them to your systemd unit or .env.prod file."
    )
