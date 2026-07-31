# Dashboard

Medburg CRM provides role-specific dashboard experiences.

## Administrator Dashboard

The Admin Dashboard provides a company-wide overview of financial performance and operational health. It is strictly protected by the `@admin_required` decorator.

### KPI Cards

At the top of the dashboard are 5 live KPI cards calculated via `analytics_service.get_home_kpis()`:
- **Today's Revenue:** Sum of all Prepaid and Postpaid sales generated today.
- **Active Doctors:** Total count of active doctors.
- **Active Prepaid Investments:** Count of investments currently `In Progress`.
- **Active Postpaid Campaigns:** Count of campaigns not currently `Locked`.
- **Monthly Revenue:** Total sales generated in the current calendar month.

### Charting System

The dashboard relies on `Chart.js` for data visualization. 

**Theming:** 
To maintain a professional, premium aesthetic, charts strictly adhere to a centralized color palette defined in `templates/doctors/admin_dashboard.html`:
- **Prepaid Metrics:** Medburg Orange (`#EFA743`)
- **Postpaid Metrics:** Slate Navy (`#334155`)

**Empty States:**
If a chart lacks data (e.g., zero postpaid sales for the month), the UI dynamically replaces the `<canvas>` element with a "No Data Available" placeholder block. This prevents misleading "flatline" charts that confuse stakeholders.

## Representative Dashboard

Sales Representatives see a restricted dashboard focusing purely on their assigned doctors and personal sales targets. They do not have access to company-wide financial aggregations or the core reporting suite.
