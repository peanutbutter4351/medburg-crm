# Infrastructure

Medburg CRM runs on a standard monolithic VPS architecture designed for reliability, simplicity, and ease of deployment.

## Production Environment Layout

*   **Host OS:** Ubuntu 24.04 LTS
*   **Web Server:** Nginx (handles SSL termination and static/media routing)
*   **Application Server:** Gunicorn (managed by `systemd`)
*   **Database:** PostgreSQL 16
*   **Static Files:** WhiteNoise (served via Gunicorn)

## Folder Structure (VPS)

The application is deployed to `/var/www/medburg_crm/` to ensure separation between source code, virtual environments, and persistent assets.

```text
/var/www/medburg_crm/
├── source/               # The Git repository clone (d:\Dev\Production\medburg-crm locally)
│   ├── manage.py
│   ├── .env.prod         # Critical production environment variables
│   └── ...
├── venv/                 # Python virtual environment (isolated from OS)
└── media/                # Persistent user uploads (survives deployments)

/var/log/medburg/
├── app.log               # Application-level logs (INFO+)
├── error.log             # Unhandled exceptions and 500s (ERROR+)
└── security.log          # Failed logins, 403s, etc. (WARNING+)
```

## Service Configuration

### Gunicorn (`systemd`)

Gunicorn is run as a `systemd` service (`medburg.service`). It binds to a local UNIX socket or `localhost:8000` (depending on configuration) and serves the Django application. 

**Restart command:**
```bash
sudo systemctl restart medburg
```

### Nginx

Nginx acts as the reverse proxy. It terminates SSL (via Let's Encrypt / Certbot) and routes requests.

*   `location /media/` is routed directly to `/var/www/medburg_crm/media/` for high performance.
*   All other requests are forwarded to Gunicorn.
*   Note: Static files (`/static/`) are intentionally NOT routed directly by Nginx; they are handled by WhiteNoise within Django to leverage manifest hashing and compression automatically.

**Reload command:**
```bash
sudo systemctl reload nginx
```

### PostgreSQL

PostgreSQL is installed locally on the VPS. Access is strictly controlled via `pg_hba.conf`, relying on local socket or `127.0.0.1` trust for the `medburg_crm` database user. 

### Static Files (WhiteNoise)

Medburg CRM uses `whitenoise.storage.CompressedStaticFilesStorage` in production. During `collectstatic`, WhiteNoise bundles all static assets into `staticfiles/`, applies Gzip/Brotli compression, and adds unique hash fingerprints to filenames. This allows Nginx/browsers to cache static assets forever safely.

### Media Files

User-uploaded files (like settlement attachments) are stored outside the source directory in `/var/www/medburg_crm/media/` (configured via `DJANGO_MEDIA_ROOT` in `.env.prod`). This prevents them from being deleted during Git pulls or deployments.
