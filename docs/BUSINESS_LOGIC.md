# Business Logic

Medburg CRM orchestrates two fundamentally different operational models for doctors: **Prepaid** and **Postpaid**. The business logic ensures complete separation between these tracks while maintaining strict financial integrity.

## Why Two Workflows?

The medical sales industry operates on two primary engagement models:

1.  **Prepaid (The Investment Model):** The company provides an upfront financial investment to a doctor (e.g., equipment, sponsorships). In return, the doctor commits to prescribing a specific value of medicines over time to generate a "Return on Investment" (ROI). 
2.  **Postpaid (The Commission Model):** The doctor prescribes medicines without upfront investment. At the end of a predefined period (usually monthly), the company calculates a commission based on total sales and settles the balance.

## The Prepaid Workflow

The prepaid workflow tracks the repayment (ROI) of upfront investments through sales volume.

1.  **Investment Creation:** An Admin creates an `Investment` record for a `Doctor`. A multiplier (`roi_ratio`) determines the expected total return.
2.  **Sales Logging:** A Sales Representative logs a `SalesEntry`. The system calculates the `value_at_sale` based on the medicine's current price and freezes it.
3.  **ROI Calculation:** The `value_at_sale` is deducted from the investment's target ROI.
4.  **Completion:** Once the target ROI is achieved (balance ≤ 0), an Admin manually transitions the investment status to `Completed`. (See [Investment Lifecycle](INVESTMENT_LIFECYCLE.md)).

## The Postpaid Workflow (Ledger Architecture)

The postpaid workflow acts as a financial ledger for commission payouts, structured around the `PostpaidCampaign` model.

1.  **Campaign Initialization:** A `PostpaidCampaign` is created for a doctor for a specific month/year. Status is `Awaiting Commission`.
2.  **Sales Accumulation:** Sales reps log `PostpaidSaleEntry` records. If the campaign commission is set, the status becomes `Open`.
3.  **Settlement Phase:** The admin begins paying out commissions. Status moves to `Partial`. The `CampaignPayment` ledger records each transaction.
4.  **Completion:** Once fully paid, the campaign is marked `Settled`.
5.  **Locking and Auditing:** The campaign is eventually `Locked`. Any subsequent adjustments must be made via append-only `PostpaidCampaignCorrection` records.

## Design Philosophy: Append-Only Architecture

Medburg CRM treats financial tracking as accounting ledgers. 

*   **Immutable Snapshots:** When a sale occurs, the financial value is frozen immediately. If medicine prices change tomorrow, yesterday's sales values must remain unchanged. (See [ROI System](ROI_SYSTEM.md)).
*   **Append-Only Modifications:** In the postpaid track, you cannot edit a past payment. You must issue a new payment or a correction. If a campaign is locked, you cannot alter its sales; you must append an audit correction.

This architecture ensures that historical financial reports (like the Settlement Ledger) remain perfectly accurate regardless of future price fluctuations or operational changes.
