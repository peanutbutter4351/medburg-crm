# Reports

Medburg CRM features a sophisticated reporting engine heavily reliant on Django ORM aggregations to prevent memory exhaustion and N+1 query problems.

## Report Types

1.  **Prepaid Doctors Report:** Aggregates all `Investment` and `SalesEntry` data grouped by Doctor. Shows total upfront investment vs total returns received via sales.
2.  **Postpaid Doctors Report:** Aggregates all `PostpaidCampaign` and `PostpaidSaleEntry` data grouped by Doctor. Shows total sales value generated vs total commission owed.
3.  **Settlement Ledger:** A specialized financial report showing the current outstanding balance for all Postpaid Campaigns across all statuses.

## Aggregation Architecture

Reports are generated using dedicated service layers (`reports/services/report_service.py` and `postpaid_report_service.py`). 

We strictly use `annotate()` and `Sum()` against the database, relying on `Coalesce()` to handle nulls.

Example from Prepaid Doctor Report:
```python
queryset = Doctor.objects.filter(mode=DOCTOR_MODE_PREPAID).annotate(
    total_investment=Coalesce(Sum('investments__amount'), Decimal('0.00')),
    total_returns_received=Coalesce(Sum('sales_entries__value_at_sale'), Decimal('0.00'))
)
```

## Filters and Re-calculation

Reports feature dynamic filters (Date Range, Location, Product, Status). 

**Important Rule:** When filters are applied, the aggregation scopes change. For instance, if a user filters the Prepaid Doctors Report by "Paracetamol", the `total_returns_received` will recalculate to only show returns generated *by that specific medicine*. However, the `total_investment` remains tied to the Doctor's overall portfolio, as investments are not product-specific.

## Excel Exports

All reports feature `.xlsx` exports.
- Exports are generated dynamically using `openpyxl`.
- They respect all active web UI filters.
- **Header Standard:** All Excel exports begin with a standardized Medburg header detailing the generation timestamp and explicitly listing the applied filters, ensuring the document remains understandable even after being emailed externally.
