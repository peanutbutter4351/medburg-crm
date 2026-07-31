# ROI System (ARCH-2A Snapshot Accounting)

The most critical financial calculation in Medburg CRM is determining how much of a prepaid investment a doctor has returned via sales (Achieved ROI). 

Historically, this was calculated dynamically: `Quantity × Live Medicine Price`. This caused catastrophic data corruption when medicine prices were updated, as historical sales instantly changed in value, retroactively altering investment balances.

## The Solution: ARCH-2A Snapshot Accounting

To solve this, Medburg CRM implemented **ARCH-2A**, a snapshot-based accounting system that freezes financial values at the moment a transaction occurs.

### The Mechanism

When a `SalesEntry` is created, the model's `save()` method intercepts the creation (when `self._state.adding` is true) and triggers `_capture_snapshot()`:

1.  It reads the live `medicine.pts` (Price To Stockist).
2.  It saves this value into `pts_at_sale`.
3.  It calculates `quantity × pts_at_sale` and saves it into `value_at_sale`.
4.  These fields are marked `editable=False` and are never recalculated on subsequent saves.

### Aggregation Rule

> [!CAUTION]
> **All financial calculations, reports, and dashboards MUST use the `value_at_sale` field.** 
> Never join against the `medicines_medicine` table to calculate financial totals dynamically.

### Handling Legacy Data

When ARCH-2A was deployed, the database contained thousands of legacy sales entries without snapshots. A data migration backfilled these rows by calculating `quantity × current_medicine.pts` and saving the result into `value_at_sale`. 

These backfilled rows have `is_snapshot_legacy=True` set. This boolean flag exists purely to indicate that the snapshot value is a "best effort" approximation based on the price at the time of migration, not the exact price on the day the sale occurred years ago.

Because the backfill is complete, the application codebase relies entirely on `value_at_sale` being populated. There is a fallback property (`SalesEntry.value`) that calculates the live value dynamically, but it is effectively dead code, acting only as a failsafe against database corruption where a snapshot might somehow be null.
