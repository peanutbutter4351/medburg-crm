# Investment Lifecycle (ARCH-3B)

The lifecycle of a Prepaid `Investment` dictates how ROI balances are managed.

## The ARCH-3B "Manual Completion" Model

In older versions of Medburg CRM, an investment would automatically transition from `In Progress` to `Completed` the exact moment a `SalesEntry` pushed its balance below zero.

This auto-completion caused severe operational issues:
- Admins lost visibility into exactly when an investment was satisfied.
- Sales reps were blocked from adding final sales for the month if the investment auto-completed mid-month (completed investments reject new sales).
- Handling "overrun" (where a doctor sells more than required) was difficult.

**ARCH-3B** introduced a strict **Manual Completion** lifecycle.

### How it Works

1.  **No Auto-Completion:** The `Investment.refresh_status()` method, which used to contain the auto-completion logic, is now a no-op (`pass`). Investments will remain `In Progress` indefinitely, even if their balance drops deeply into the negative (representing over-achieved ROI).
2.  **Manual Admin Action:** When an investment reaches its target, a human Administrator must review the account and manually change the status to `Completed` via the Django Admin interface.
3.  **Strict Validation (`balance <= 0`):** The `Investment.clean()` method enforces a strict guardrail: an Admin cannot mark an investment as completed if its balance is still positive. The doctor must fulfill the ROI commitment before the system allows the investment to be closed.

### Handling Multiple Active Investments

Because investments no longer auto-close, a doctor might technically have multiple `In Progress` investments simultaneously if an Admin delays closing an old one before opening a new one.

The CRM handles this smoothly:
- `SalesEntry` forms require the sales representative to explicitly select which specific `Investment` the sale should be credited against.
- The system does not attempt to "auto-allocate" sales across multiple investments.

### The Role of `refresh_status()`

Historically, `refresh_status()` calculated the balance and toggled the state. While it is now a no-op in the prepaid lifecycle, the method signature is retained because `SalesEntry.save()` still calls it. This minimizes blast radius during the migration to manual completion and allows for future hooks if reporting caches need to be invalidated.
