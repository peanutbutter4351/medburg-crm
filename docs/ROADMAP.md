# Roadmap

This document outlines the historical sprints leading to the current release, and planned future initiatives.

## Completed

**Sprint 1: Lifecycle Hardening**
- Implemented ARCH-3B (Manual Investment Completion).
- Disabled automatic state transitions.
- Fixed dashboard tab persistence (URL routing).

**Sprint 2: Consolidated Reporting**
- Built Prepaid Doctors Report (Investment vs Returns aggregate).
- Built Postpaid Doctors Report (Sales vs Commission aggregate).
- Standardized Excel export headers and applied filters logic.

**Sprint 3: Dashboard Overhaul**
- Deployed 5 new KPI aggregation cards.
- Restyled Chart.js visualizations (Navy/Orange palette).
- Implemented "No Data Available" empty states to replace misleading flatline charts.

## Current Release

**v1.3.0-stable**
- Production-ready status.
- Comprehensive documentation suite added (the contents of this `docs/` folder).

## Future Initiatives

**Sprint 4+ Ideas**
- **Automated Settlement Emails:** Integrate SendGrid/SMTP to automatically email Postpaid doctors their settlement ledgers at the end of the month.
- **Inventory Tracking:** Expand the `Medicines` app to track warehouse stock levels, not just pricing.
- **API Layer:** Develop a Django REST Framework (DRF) layer to allow future mobile app integration for Sales Reps in the field.
- **Playwright E2E Tests:** Implement browser-based automated testing to augment the existing Django unit tests.
