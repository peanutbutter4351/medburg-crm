"""
Medburg CRM — Development Settings

Local development overrides.  Activated by default when you run:
    python manage.py runserver

Key differences from production:
    - DEBUG = True
    - SQLite database (no PostgreSQL dependency for local dev)
    - Insecure fallback SECRET_KEY
    - No SSL / secure-cookie enforcement
    - No WhiteNoise manifest storage (plain static serving)
    - Media files served by Django dev server via urls.py static() helper
    - Console-only logging at DEBUG level
"""

import os
from .base import *  # noqa: F401,F403

# ──────────────────────────────────────────────
# Security
# ──────────────────────────────────────────────
DEBUG = True

SECRET_KEY = os.environ.get(
    "DJANGO_SECRET_KEY",
    "django-insecure-change-me-in-production-!@#$%^&*()",
)

ALLOWED_HOSTS = os.environ.get(
    "DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1"
).split(",")

# ──────────────────────────────────────────────
# Database — SQLite for zero-config local dev
# ──────────────────────────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",
    }
}

# ──────────────────────────────────────────────
# Static files — simple serving for development
# ──────────────────────────────────────────────
# No manifest hashing in dev; avoids collectstatic requirement
STATICFILES_STORAGE = "django.contrib.staticfiles.storage.StaticFilesStorage"

# ──────────────────────────────────────────────
# Media files — served by Django dev server
# ──────────────────────────────────────────────
# MEDIA_ROOT is inherited from base.py (defaults to <project_root>/media/).
# Django's dev server serves /media/ via the static() URL helper in urls.py.
# No special override needed — just ensure urls.py has the media URL pattern.

# ──────────────────────────────────────────────
# Logging — verbose console logging for dev
# ──────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "dev": {
            "format": "%(levelname)-8s %(name)s: %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "dev",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "DEBUG",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        # Silence noisy DB query logging unless explicitly needed
        "django.db.backends": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "medburg": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}
