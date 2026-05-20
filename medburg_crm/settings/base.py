"""
Medburg CRM — Base Settings

Contains every setting shared across ALL environments.
Environment-specific files (development.py, production.py) import from here
with `from .base import *` and then override only what differs.

This file should NEVER contain:
    - DEBUG value
    - Database configuration
    - SECRET_KEY value
    - Security header toggles
    - LOGGING configuration (handled per-environment)
"""

import os
from pathlib import Path

# ──────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────
# BASE_DIR points to the project root (one level above medburg_crm/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ──────────────────────────────────────────────
# Applications
# ──────────────────────────────────────────────
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # ── project apps ─────────────────────────
    "core.apps.CoreConfig",
    "accounts.apps.AccountsConfig",
    "doctors.apps.DoctorsConfig",
    "medicines.apps.MedicinesConfig",
    "sales.apps.SalesConfig",
    "reports.apps.ReportsConfig",
]

# ──────────────────────────────────────────────
# Middleware
# ──────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ──────────────────────────────────────────────
# URL / WSGI
# ──────────────────────────────────────────────
ROOT_URLCONF = "medburg_crm.urls"
WSGI_APPLICATION = "medburg_crm.wsgi.application"

# ──────────────────────────────────────────────
# Templates
# ──────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ──────────────────────────────────────────────
# Auth
# ──────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

LOGIN_URL = "/accounts/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/accounts/login/"

# ──────────────────────────────────────────────
# Password validation
# ──────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ──────────────────────────────────────────────
# Internationalization
# ──────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ──────────────────────────────────────────────
# Static files
# ──────────────────────────────────────────────
# WhiteNoise middleware (above) handles compression & caching for static files.
# NOTE: WhiteNoise does NOT serve MEDIA files. Nginx handles media in production.
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# ──────────────────────────────────────────────
# Media files  (user-uploaded content)
# ──────────────────────────────────────────────
# MEDIA_URL  : URL prefix for all uploaded files.
# MEDIA_ROOT : Absolute filesystem path where uploads are stored.
#
# Production: MEDIA_ROOT is overridden via DJANGO_MEDIA_ROOT env var
#             and Nginx serves /media/ directly (bypassing Django/Gunicorn).
# Development: files land in <project_root>/media/ and Django's
#              dev server serves them via urls.py static() helper.
MEDIA_URL = "/media/"
MEDIA_ROOT = Path(os.environ.get("DJANGO_MEDIA_ROOT", str(BASE_DIR / "media")))

# ──────────────────────────────────────────────
# Default primary key
# ──────────────────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
