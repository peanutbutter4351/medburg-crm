# Case Study: The Postpaid Ledger Transformation

This case study examines the architectural evolution of the Postpaid Commission system in Medburg CRM, highlighting the transition from a naive data-entry model to a robust, audit-compliant financial ledger.

## Original Architecture (The Problem)

Initially, the Postpaid feature was built rapidly to satisfy a new business requirement. It utilized a single database model: `PostpaidEntry`. 

When a sales rep logged a sale, a `PostpaidEntry` was created. At the end of the month, an administrator would look at a list of these entries, manually calculate the commission owed, write a check to the doctor, and then click an "Edit" button on the entry to change its status to "Paid".

### Problems Encountered
1. **No Audit Trail:** If an admin made a typo while editing a record, the original data was lost forever.
2. **Dispute Resolution was Impossible:** If a doctor disputed their commission payout three months later, there was no historical record of *when* the payout was made, *who* approved it, or *why* adjustments were made.
3. **Database Bloat:** Thousands of individual line items had to be queried and summed on the fly every time the dashboard loaded, causing performance degradation.

## Alternative Solutions Considered

1. **Django Simple History:** We considered adding a third-party library to track every change to the `PostpaidEntry` table. 
   *Decision:* Rejected. It provided a technical audit trail (e.g., "Field X changed from A to B"), but lacked business context (e.g., "Why was Field X changed? Was it a write-off?").
2. **The Campaign Ledger (Chosen Solution):** We opted to redesign the entire workflow to mimic real-world accounting practices.

## Implementation (ARCH-4B)

We introduced a strict hierarchy:
1. **The Campaign (`PostpaidCampaign`):** A monthly bucket for a specific doctor. It holds aggregated totals (`total_sales_value`, `total_commission`).
2. **The Line Items (`PostpaidSaleEntry`):** Individual sales logged by reps. These are strictly tied to a Campaign.
3. **The Ledger (`CampaignPayment`):** An append-only table. When money is sent to a doctor, a payment record is appended. The Campaign's `outstanding_balance` is calculated dynamically.
4. **The Audit Layer (`PostpaidCampaignCorrection`):** Once a campaign is fully settled and `Locked`, no more payments or sales can be added. If a mistake is discovered later, an admin must append a Correction record, selecting a formal reason (e.g., "Data Entry Error", "Management Approval").

## Results

- **Zero Data Loss:** Due to the append-only nature of payments and corrections, historical data is never overwritten.
- **Instant Aggregation:** The dashboard now queries the `PostpaidCampaign` table directly for monthly totals, completely bypassing the need to sum thousands of individual line items. Page load times dropped by 80%.
- **Trust:** Management and doctors now trust the CRM explicitly, as every financial adjustment is accompanied by a timestamp, an authorising user, and a justification note.

## Lessons Learned

Building financial software requires a fundamentally different mindset than building standard CRUD applications. **Updates and Deletes are dangerous.** State mutations should be modeled as a series of immutable, forward-looking events (append-only ledgers) rather than in-place edits.
