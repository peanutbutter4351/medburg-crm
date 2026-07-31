# Troubleshooting Guide

This document covers common issues encountered while managing Medburg CRM in production.

---

## 1. The SQLite Trap (Data Appears Missing)

**Symptoms:**
- You deploy new code, restart Gunicorn, log in, and the database is completely empty (no doctors, no users, no sales).
- Alternatively, you run `python manage.py migrate` and see dozens of new tables being created, even though the app has been running for months.

**Cause:**
You ran a `manage.py` command (like `migrate` or `createsuperuser`) OR started Gunicorn without loading `.env.prod`. By default, Django falls back to `settings/development.py`, which creates a local `db.sqlite3` file in the source directory.

**Solution:**
1. Stop the application: `sudo systemctl stop medburg`.
2. Delete the accidentally created SQLite file: `rm /var/www/medburg_crm/source/db.sqlite3`
3. Load the environment: 
   ```bash
   cd /var/www/medburg_crm/source
   source ../venv/bin/activate
   set -a
   source .env.prod
   set +a
   ```
4. Restart the application: `sudo systemctl start medburg`.

---

## 2. Static Files Return 404 (WhiteNoise Manifest Issues)

**Symptoms:**
- The site loads but CSS/JS is missing (looks broken).
- Checking the browser console shows 404 errors for files like `style.css`.
- Server logs show `ValueError: Missing staticfiles manifest entry`.

**Cause:**
You deployed changes to CSS or JS files but forgot to run `collectstatic`. WhiteNoise uses a manifest file to map `style.css` to `style.abcdef123.css`. If the manifest is out of date, it throws errors.

**Solution:**
Run collectstatic (ensuring `.env.prod` is loaded first):
```bash
python manage.py collectstatic --no-input
sudo systemctl restart medburg
```

---

## 3. Gunicorn Startup Failures

**Symptoms:**
- `systemctl status medburg` shows `Active: failed`.
- Site returns `502 Bad Gateway` from Nginx.

**Cause:**
Usually a syntax error in Python code, a missing dependency in the virtual environment, or invalid database credentials in `.env.prod`.

**Solution:**
Check the journal logs for the exact Python traceback:
```bash
sudo journalctl -u medburg -f
```
Fix the code/config, then `sudo systemctl restart medburg`.

---

## 4. Nginx 502 Bad Gateway

**Symptoms:**
- Site returns 502 Bad Gateway.
- Gunicorn is running perfectly (`systemctl status medburg` is green).

**Cause:**
Nginx cannot communicate with Gunicorn. This usually means Gunicorn is bound to a different UNIX socket or IP/Port than Nginx is configured to proxy to.

**Solution:**
1. Check the Nginx config (`/etc/nginx/sites-available/medburg`).
2. Look at the `proxy_pass` directive (e.g., `proxy_pass http://127.0.0.1:8000;` or `proxy_pass http://unix:/run/medburg.sock;`).
3. Ensure Gunicorn's systemd file (`/etc/systemd/system/medburg.service`) has a matching `--bind` argument.
4. If you change either, reload the respective service.

---

## 5. Git fileMode Issue (Constant "Modified" Files)

**Symptoms:**
- `git status` on the VPS shows all files as modified, but you haven't touched them.
- Running `git diff` shows `old mode 100644 new mode 100755`.

**Cause:**
The VPS filesystem or an FTP transfer altered file execution permissions.

**Solution:**
Tell Git to ignore permission changes on the VPS:
```bash
git config core.fileMode false
```
