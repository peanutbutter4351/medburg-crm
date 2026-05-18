"""
Medburg CRM — Settings Package

This package splits Django settings into environment-specific modules:

    base.py         → Shared settings (apps, middleware, templates, auth, i18n)
    development.py  → Local dev overrides (SQLite, DEBUG=True, relaxed security)
    production.py   → VPS / Gunicorn / Nginx / PostgreSQL / SSL hardening

Selection logic:
    1. If DJANGO_SETTINGS_MODULE is explicitly set, Django uses that.
    2. Otherwise, manage.py / wsgi.py / asgi.py default to
       "medburg_crm.settings.development" for local work.
    3. On the VPS, set DJANGO_SETTINGS_MODULE=medburg_crm.settings.production
       in your systemd unit / .env file.
"""
