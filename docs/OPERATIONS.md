# Operations Runbook

This document details common day-to-day administrative tasks for maintaining the Medburg CRM production environment.

## Service Management

All primary services are managed by `systemd`.

**Check Application Health (Gunicorn):**
```bash
systemctl status medburg
```

**Restart Application (After code or config changes):**
```bash
sudo systemctl restart medburg
```

**Check Web Proxy Health (Nginx):**
```bash
systemctl status nginx
```

**Reload Web Proxy (After Nginx config changes or SSL renewal):**
```bash
sudo systemctl reload nginx
```

## Log Monitoring

Medburg CRM uses standard logging mechanisms.

### Application Logs

Django logs are routed to rotating files in `/var/log/medburg/`.
- `app.log`: Standard information and business events.
- `error.log`: Critical errors, 500s, and Python tracebacks.
- `security.log`: Failed logins, 403 Forbidden accesses.

To watch real-time application errors:
```bash
tail -f /var/log/medburg/error.log
```

### System Logs (journalctl)

Gunicorn's stdout/stderr is captured by the system journal. If the application crashes before Django's logging system initializes (e.g., bad `.env.prod` syntax), you will find the error here:

```bash
sudo journalctl -u medburg -f
```

### Nginx Logs

To monitor incoming web traffic and catch 502 Bad Gateway errors:

```bash
# Access log (all requests)
sudo tail -f /var/log/nginx/access.log

# Error log (Nginx-level failures)
sudo tail -f /var/log/nginx/error.log
```

## Database Operations

### Connect to Production Database Shell
If you need to inspect the database directly via SQL:

```bash
# Switch to postgres user
sudo -i -u postgres

# Connect to the database
psql medburg_crm
```

### Connect to Django Shell
To interact with the database using the Django ORM (highly recommended over raw SQL):

```bash
cd /var/www/medburg_crm/source
source ../venv/bin/activate
set -a
source .env.prod
set +a

python manage.py shell
```

## Common Administrative Tasks

### Creating a Superuser
```bash
# Ensure environment is loaded as per deployment guide
python manage.py createsuperuser
```

### Clearing Stale Sessions
Django stores session data in the database. Over time, expired sessions accumulate. Run this monthly:
```bash
python manage.py clearsessions
```
