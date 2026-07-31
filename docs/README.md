# Medburg CRM Documentation

This folder contains the complete, professional documentation suite for Medburg CRM. 

These documents serve as the definitive source of truth for the project's architecture, deployment operations, business logic, and historical decisions.

## Table of Contents

### System & Architecture
1. **[Architecture Overview](ARCHITECTURE.md)** — High-level system design, app boundaries, and request lifecycles.
2. **[Database Schema](DATABASE.md)** — ER diagrams, relationships, proxy models, and constraints.
3. **[Infrastructure](INFRASTRUCTURE.md)** — Server layout, Gunicorn/Nginx setup, and static files.

### Business Logic
4. **[Business Logic Overview](BUSINESS_LOGIC.md)** — Core workflows (Prepaid vs Postpaid).
5. **[ROI System](ROI_SYSTEM.md)** — The ARCH-2A Snapshot Accounting engine.
6. **[Investment Lifecycle](INVESTMENT_LIFECYCLE.md)** — The ARCH-3B manual completion model.
7. **[Reports](REPORTS.md)** — Aggregation methodology, filters, and Excel exports.
8. **[Dashboard](DASHBOARD.md)** — KPI metrics, chart themes, and roles.

### Operations & Deployment
9. **[Deployment Guide](DEPLOYMENT.md)** — Step-by-step production upgrades (and the SQLite trap).
10. **[Operations Runbook](OPERATIONS.md)** — Service health, log monitoring, and administration.
11. **[Troubleshooting](TROUBLESHOOTING.md)** — Solutions for common deployment and runtime errors.
12. **[Backup & Recovery](BACKUP_AND_RECOVERY.md)** — PostgreSQL `pg_dump` and media asset restoration.
13. **[Security](SECURITY.md)** — Access control, environment variables, and safe production defaults.

### Engineering Practices
14. **[Release Process](RELEASE_PROCESS.md)** — Versioning, tagging, and branch management.
15. **[Testing](TESTING.md)** — Test suite execution and coverage philosophy.
16. **[Architectural Decisions](DECISIONS.md)** — Records of major architectural shifts (ADRs).
17. **[Project History](PROJECT_HISTORY.md)** — Evolution of the codebase and technical debt removal.
18. **[Roadmap](ROADMAP.md)** — Past sprints and future directions.
19. **[Changelog](CHANGELOG.md)** — Keep-A-Changelog formatted version history.
20. **[Case Study](CASE_STUDY.md)** — Technical retrospective of the ledger transformation.

### AI & Automation
21. **[AI Agent Guide](AI_AGENT_GUIDE.md)** — Mandatory reading for AI coding assistants.
