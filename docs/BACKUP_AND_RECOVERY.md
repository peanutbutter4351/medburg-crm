# Backup and Recovery

Protecting the PostgreSQL database and user-uploaded media is critical.

## PostgreSQL Backup (`pg_dump`)

The CRM database should be backed up regularly.

**Manual Full Backup:**
```bash
sudo -i -u postgres
pg_dump medburg_crm > /path/to/secure/storage/medburg_crm_$(date +%Y%m%d_%H%M).sql
```

This creates a complete SQL script capable of recreating the schema and inserting all data.

## Media Backup

Settlement attachments (PDFs, images) are stored outside the database in the media root.

**Backup Command:**
```bash
tar -czvf /path/to/secure/storage/media_backup_$(date +%Y%m%d).tar.gz /var/www/medburg_crm/media/
```

## Disaster Recovery Procedure

If the VPS is lost or the database is corrupted, follow this procedure on a fresh server.

1.  **Rebuild Infrastructure:** Install PostgreSQL, Nginx, Gunicorn, and Python as per standard deployment.
2.  **Clone Repository:** Clone the source code into `/var/www/medburg_crm/source`.
3.  **Restore Configuration:** Recreate `.env.prod` with identical `DJANGO_SECRET_KEY` and database credentials.
4.  **Create Empty Database:**
    ```bash
    sudo -u postgres psql -c "CREATE DATABASE medburg_crm;"
    sudo -u postgres psql -c "CREATE USER medburg_user WITH PASSWORD 'secure_password';"
    sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE medburg_crm TO medburg_user;"
    ```
5.  **Restore PostgreSQL Data:**
    ```bash
    sudo -u postgres psql medburg_crm < /path/to/backup.sql
    ```
6.  **Restore Media:**
    ```bash
    tar -xzvf /path/to/media_backup.tar.gz -C /
    ```
7.  **Finalize:** Activate the virtual environment, collect static files, and start Gunicorn.

> [!WARNING]
> Do NOT run `python manage.py migrate` during a disaster recovery *before* restoring the SQL dump. The `pg_dump` file contains all schema definitions. Running migrations first will cause table creation conflicts during the restore.
