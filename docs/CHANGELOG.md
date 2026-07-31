# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.3.0-stable] - 2026-07-31

### Added
- Comprehensive Markdown documentation suite in the `docs/` folder.
- `ARCHITECTURE.md`, `DEPLOYMENT.md`, `BUSINESS_LOGIC.md`, and 14 other operational guides.

## [1.2.3-rc1] - 2026-07-30

### Added
- 5 new KPI summary cards to the Admin Dashboard (Today's Revenue, Active Doctors, Active Investments, Active Campaigns, Monthly Revenue).
- `Prepaid Doctors Report` with dynamic Excel exports.
- `Postpaid Doctors Report` with dynamic Excel exports.

### Changed
- Dashboard charts updated to a unified Navy/Orange color scheme.
- Dashboard empty states now display a "No Data Available" message instead of a flatline chart.
- `refresh_status()` on `Investment` is now a no-op to support manual completion.

### Fixed
- Fixed a bug where applying filters on the dashboard would reset the active tab view (now persists via URL parameter).
- Fixed a bug where multiple sidebar navigation links would highlight simultaneously.

## [1.2.0-stable] - 2026-07-15

### Added
- `PostpaidCampaignCorrection` model to serve as an append-only audit trail for locked campaigns.
- `CampaignPayment` model to act as a strict settlement ledger.

### Changed
- Transitioned Postpaid architecture to a strict month/year campaign ledger system.

### Removed
- Legacy `PostpaidEntry` model entirely dropped from the database (Migration 0014).

## [1.1.0-stable] - 2026-06-01

### Added
- ARCH-2A Snapshot Accounting implementation.
- `pts_at_sale` and `value_at_sale` fields added to `SalesEntry`.

### Changed
- Data migration executed to backfill legacy sales entries with approximate historical values.
