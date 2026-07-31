# Medburg CRM

Medburg CRM is a specialized Customer Relationship Management and financial ledger application built for the medical and pharmaceutical sales industry. It handles complex tracking of doctor engagement, prepaid investment ROI (Return on Investment), and postpaid commission settlements.

The application is built on Django and features immutable snapshot-based financial accounting, strict ledger trails, and a sophisticated reporting engine.

## Documentation Index

The source code and repository structure are extensively documented. For future developers, AI agents, and system administrators, please consult the complete documentation suite located in the `docs/` folder:

*   **[Documentation Home](docs/README.md)**

### Core Concepts

*   **[Architecture Overview](docs/ARCHITECTURE.md)**
*   **[Business Logic & Workflows](docs/BUSINESS_LOGIC.md)**
*   **[ROI System (Snapshot Accounting)](docs/ROI_SYSTEM.md)**
*   **[Investment Lifecycle](docs/INVESTMENT_LIFECYCLE.md)**
*   **[Database Schema](docs/DATABASE.md)**

### Operations & Deployment

*   **[Infrastructure & Environment](docs/INFRASTRUCTURE.md)**
*   **[Deployment Guide](docs/DEPLOYMENT.md)**
*   **[Operational Runbook](docs/OPERATIONS.md)**
*   **[Backup & Recovery](docs/BACKUP_AND_RECOVERY.md)**
*   **[Security](docs/SECURITY.md)**
*   **[Troubleshooting](docs/TROUBLESHOOTING.md)**

### Development & Maintenance

*   **[Testing Guide](docs/TESTING.md)**
*   **[Release Process](docs/RELEASE_PROCESS.md)**
*   **[Architectural Decisions (ADRs)](docs/DECISIONS.md)**
*   **[Project History](docs/PROJECT_HISTORY.md)**
*   **[Roadmap](docs/ROADMAP.md)**
*   **[Changelog](docs/CHANGELOG.md)**
*   **[Case Study](docs/CASE_STUDY.md)**
*   **[AI Agent Guide](docs/AI_AGENT_GUIDE.md)** (Critical reading for automated tools)

## Technology Stack

*   **Backend framework:** Django 4.2
*   **Database:** PostgreSQL
*   **Application Server:** Gunicorn
*   **Web Server / Reverse Proxy:** Nginx
*   **Static Asset Management:** WhiteNoise
*   **Host OS:** Ubuntu 24.04 LTS

## Quick Start

### Local Development

1.  Clone the repository.
2.  Set up a Python virtual environment: `python -m venv .venv`
3.  Activate the virtual environment.
4.  Install dependencies: `pip install -r requirements.txt`
5.  By default, `manage.py` will use `medburg_crm.settings.development` and connect to a local SQLite database.
6.  Apply migrations: `python manage.py migrate`
7.  Run the development server: `python manage.py runserver`

### Production Deployment

> [!WARNING]
> **CRITICAL DEPLOYMENT RULE**
> `manage.py` defaults to `development.py` unless `DJANGO_SETTINGS_MODULE` is exported. Production environment variables live in `.env.prod`.
> 
> Before running ANY `manage.py` command on the VPS, you MUST execute the following exact sequence to connect to PostgreSQL instead of SQLite:
> 
> ```bash
> cd /var/www/medburg_crm/source
> source ../venv/bin/activate
> set -a
> source .env.prod
> set +a
> ```
> Failure to do this will silently initialize a local SQLite database, resulting in data loss or extreme confusion.

See **[Deployment Guide](docs/DEPLOYMENT.md)** for full instructions.
