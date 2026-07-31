# Project History

Medburg CRM has evolved significantly from its initial MVP to the robust financial ledger it is today. 

## Evolution & Milestones

### Phase 1: The MVP
The initial CRM was a simple data-entry tool. It tracked Doctors, Medicines, and basic Sales Entries. It featured a rudimentary ROI calculation that was entirely dynamic. 

**Lessons Learned:** The dynamic calculation proved disastrous when the first medicine catalogue prices were updated, altering all historical investment balances.

### Phase 2: Technical Debt Resolution (ARCH-2A)
The team halted feature development to address the dynamic calculation bug. The ARCH-2A Snapshot Accounting system was designed and deployed. This required a complex data migration to backfill thousands of legacy sales entries to estimate their historical value.

**Lessons Learned:** Financial systems cannot rely on live, mutable reference data. Denormalization (snapshotting) is necessary for immutable ledgers.

### Phase 3: The Postpaid Expansion (ARCH-4B)
Management requested support for a secondary business model: Postpaid Commissions. Initially, this was implemented poorly with a single `PostpaidEntry` model that functioned like a spreadsheet. 

Realizing the lack of auditability, the team completely redesigned the postpaid track into a monthly campaign ledger (`PostpaidCampaign`), introducing strict state machines (Awaiting -> Open -> Partial -> Settled -> Locked) and an append-only correction layer. The legacy `PostpaidEntry` table was subsequently dropped in MR-8.0.

### Phase 4: UI/UX Modernization & Dashboarding (v1.2.3 to v1.3.0)
With the backend financial logic secured, focus shifted to presentation. The Admin Dashboard was overhauled to include live KPI aggregations, Chart.js visualizations, and dedicated consolidated reports (Prepaid Doctors Report, Postpaid Doctors Report). 

**Lessons Learned:** Raw data is insufficient; stakeholders require high-level aggregations (KPIs) alongside drill-down capabilities (Excel exports) to make business decisions.
