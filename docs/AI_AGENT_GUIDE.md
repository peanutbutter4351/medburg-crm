# Guide for AI Agents

> [!CAUTION]
> **READ THIS BEFORE MODIFYING CODE**
> If you are an AI coding assistant (e.g., Antigravity, GitHub Copilot, Claude), you must adhere to these strict architectural rules. Medburg CRM is a financial ledger system running in production; mistakes will cause irrecoverable data corruption.

## 1. Respect the Append-Only Architecture
Do **not** write code that modifies existing financial records.
- In the Postpaid workflow, `CampaignPayment` and `PostpaidCampaignCorrection` are append-only. Never add an `update()` or `delete()` view for these models.
- If a user needs to fix a mistake on a Locked campaign, build a UI to append a new `PostpaidCampaignCorrection` (credit or debit), rather than unlocking the campaign.

## 2. Respect ARCH-2A Snapshot Accounting
- Never use `quantity * medicine.pts` to calculate historical sales value. 
- ALWAYS use the frozen `value_at_sale` field on the `SalesEntry` / `PostpaidSaleEntry` models.
- Never modify the `save()` method of these models in a way that allows `value_at_sale` to be recalculated after creation.

## 3. Never Bypass the Django ORM
- Do not write raw SQL (`.raw()`, `cursor.execute()`).
- All reporting aggregations must use Django's `annotate()`, `Sum()`, and `Coalesce()` to ensure database portability and prevent injection.

## 4. Operational Awareness (The `.env.prod` Trap)
If a user asks you to write a deployment script, a cron job, or a management command:
- You MUST ensure `cd /var/www/medburg_crm/source && source ../venv/bin/activate && set -a && source .env.prod && set +a` is executed before running `manage.py`.
- If you forget this, the system will execute against a local SQLite file instead of the production PostgreSQL database.

## 5. Architectural Integrity
- Read [DECISIONS.md](DECISIONS.md) before proposing major refactors. We have intentionally chosen slightly denormalized snapshots and manual completion lifecycles over heavily automated, heavily normalized approaches.
- Do not attempt to "optimize" the proxy models (`PrepaidDoctor`, `PostpaidDoctor`) by merging them; they are intentionally separated to provide distinct Django Admin views without table duplication.

## 6. Pre-Commit Checklist for AI
Before providing code to the user:
- [ ] Did I modify a business logic rule in `models.py`? If so, did I warn the user about historical data impact?
- [ ] Did I ensure my new views are protected with `@admin_required` if they expose financial data?
- [ ] Did I write automated tests for my changes?
- [ ] Will my changes require a database migration? If so, is it non-destructive?
