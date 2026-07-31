# Deployment Guide

Deploying Medburg CRM requires strict adherence to environmental configuration. 

> [!WARNING]
> **THE SQLITE TRAP: READ BEFORE DEPLOYING**
> 
> By default, Django's `manage.py` will load `medburg_crm.settings.development`. This causes Django to silently create and connect to a local `db.sqlite3` file instead of the production PostgreSQL database.
> 
> If you run `python manage.py migrate` without loading the production environment first, you will apply migrations to an empty SQLite file. If you restart Gunicorn in this state, the application will boot against the empty database, causing apparent catastrophic data loss.
> 
> **You MUST execute the environment loading block exactly as written below.**

## Standard Production Deployment

Execute these steps via SSH on the production VPS.

### 1. Enter the Deployment Directory
```bash
cd /var/www/medburg_crm/source
```

### 2. Activate the Virtual Environment
```bash
source ../venv/bin/activate
```

### 3. Load Production Environment Variables (CRITICAL)
This block ensures `DJANGO_SETTINGS_MODULE=medburg_crm.settings.production` and all PostgreSQL credentials are exported to the shell session.

```bash
set -a
source .env.prod
set +a
```

### 4. Fetch and Checkout Code
Always deploy specific tags (e.g., `v1.3.0-stable`) rather than deploying `main` directly.

```bash
git fetch --tags
git checkout v1.3.0-stable
```

### 5. Install Dependencies
```bash
pip install -r requirements.txt
```

### 6. Verify and Apply Migrations
First, verify what migrations are pending.
```bash
python manage.py showmigrations --plan
```

Apply migrations to PostgreSQL:
```bash
python manage.py migrate
```

### 7. Collect Static Files
Generate hashed static assets for WhiteNoise.
```bash
python manage.py collectstatic --no-input
```

### 8. Restart Services
```bash
sudo systemctl restart medburg
sudo systemctl reload nginx
```

---

## Post-Deployment Verification (Smoke Testing)

Immediately after restarting services, verify the deployment:

1.  Navigate to the CRM URL in a browser.
2.  Log in as an Administrator.
3.  Check the **Admin Dashboard**. Ensure KPI cards and charts render without errors.
4.  Navigate to **Settlement Ledger** and ensure data populates correctly.
5.  Generate a **Prepaid Doctors Report** and perform an Excel Export.

## Rollback Procedure

If a critical failure occurs during smoke testing, roll back immediately.

> [!NOTE]
> Database rollbacks are complex. If the deployment included destructive database migrations, you must restore the PostgreSQL database from the pre-deployment `pg_dump` backup before reverting code.

If the deployment **did not** include migrations, or migrations were strictly additive:

```bash
# 1. Stop the application
sudo systemctl stop medburg

# 2. Revert code to previous stable tag
cd /var/www/medburg_crm/source
git checkout v1.2.3-rc1  # Replace with actual previous tag

# 3. Re-collect static assets for the old version
source ../venv/bin/activate
set -a
source .env.prod
set +a
python manage.py collectstatic --no-input

# 4. Restart services
sudo systemctl start medburg
sudo systemctl reload nginx
```
