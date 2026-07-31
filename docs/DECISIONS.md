# Architectural Decision Records (ADRs)

This document tracks major architectural decisions made during the evolution of Medburg CRM.

---

## ADR-1: ARCH-2A Snapshot Accounting

**Problem:** 
Historically, the CRM calculated the financial value of a `SalesEntry` dynamically by multiplying `quantity` by the live `medicine.pts` (Price To Stockist). When the management updated medicine prices in the catalogue, the historical financial value of all past sales instantly changed, corrupting historical ROI balances and making past reports inaccurate.

**Alternatives Considered:**
1.  **Temporal Tables:** Creating a full historical ledger of price changes for medicines and joining against the price active at the time of the sale. (Deemed too complex and slow for reporting).
2.  **Snapshotting at Sale Time:** Freezing the price into the `SalesEntry` table when the record is created.

**Decision:**
Implemented Snapshotting (ARCH-2A). Added `pts_at_sale` and `value_at_sale` to `SalesEntry`. Created a massive data migration to backfill legacy rows.

**Reason:**
Financial ledgers must be immutable. This approach guarantees that a sale made today retains its exact monetary value forever, regardless of future catalogue changes. It simplifies reporting aggregations drastically.

**Trade-offs:**
Slight database denormalization (storing derived data). Requires strict enforcement to ensure `value_at_sale` is never bypassed by future developers.

---

## ADR-2: ARCH-3B Manual Investment Completion

**Problem:** 
Investments used to automatically transition to `Completed` status the moment a sales entry pushed their balance to zero or below. This resulted in investments closing mid-month, preventing sales reps from logging the rest of the month's sales against that investment.

**Alternatives Considered:**
1.  **End-of-Month Cron Job:** Automatically closing satisfied investments at 11:59 PM on the last day of the month.
2.  **Manual Admin Control:** Forcing a human administrator to review and close the investment.

**Decision:**
Implemented Manual Completion (ARCH-3B). The `refresh_status` method was gutted to a no-op, and strict validation was added to the Django Admin to prevent closing investments with a positive balance.

**Reason:**
Business reality is messy. Doctors often overachieve their targets (negative balance), and management needs discretion over when an investment is considered officially "closed" for accounting purposes.

**Trade-offs:**
Requires more administrative overhead. Admins must actively manage the CRM rather than relying on automation.

---

## ADR-3: Append-Only Postpaid Ledger (ARCH-4B)

**Problem:** 
The original postpaid implementation lacked an audit trail. If a commission was paid, the record was just overwritten. If a mistake was made, it was edited without a trace, leading to disputes over historical payouts.

**Alternatives Considered:**
1.  **Django Simple History:** Using a third-party library to track model changes.
2.  **Dedicated Ledger Tables:** Building a custom append-only accounting system.

**Decision:**
Built a custom ledger (ARCH-4B). Created `CampaignPayment` for recording payouts and `PostpaidCampaignCorrection` for handling post-lock adjustments.

**Reason:**
Financial systems require explicit intent. A generic history library tracks *what* changed, but an append-only ledger tracks *why* (e.g., "Dispute Resolution", "Write Off").

**Trade-offs:**
Increased UI complexity. Users cannot simply "edit" a typo in a locked campaign; they must issue a formal correction entry.
