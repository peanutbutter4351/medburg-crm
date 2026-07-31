# Testing Guide

Medburg CRM relies on a comprehensive automated test suite (currently 96 passing tests) to prevent regressions in its rigid financial logic.

## Test Structure

Tests are located in the `tests/` directory.

- `test_doctors.py`: Validates the `Doctor` and `Investment` models. Critical coverage for ARCH-3B (ensuring manual completion is blocked if balance > 0).
- `test_sales.py`: The largest suite. Validates ARCH-2A Snapshot Accounting (frozen `value_at_sale`), Postpaid Campaign transitions (Awaiting -> Open -> Partial -> Settled), and append-only ledgers.
- `test_reports.py`: Validates the aggregation queries for Prepaid and Postpaid Doctors Reports.
- `test_analytics.py`: Validates dashboard KPI aggregations.
- `test_postpaid_reports.py`: Validates the Postpaid Campaign Settlement Ledger.
- `test_dashboard_home.py`: Validates UI layout, permissions, and tab persistence.

## How to Execute Tests

Tests should be run locally before any commit.

```bash
# Activate your local development virtual environment
python -m venv .venv
source .venv/bin/activate

# Run the full suite
python manage.py test tests/
```

Django will automatically create a temporary test database, run all tests, and destroy the database.

## Recommended Future Testing

While unit test coverage is high, future efforts should focus on:
1.  **End-to-End (E2E) Browser Testing:** Using Playwright or Selenium to simulate a full Rep login -> Sales Entry -> Admin Login -> Campaign Settlement workflow.
2.  **Migration Testing:** Automated tests that load a dump of the previous schema, apply the new migrations, and verify data integrity.
3.  **Excel Export Validation:** Programmatically opening the generated `.xlsx` files and verifying the cells match the expected DB aggregates.
