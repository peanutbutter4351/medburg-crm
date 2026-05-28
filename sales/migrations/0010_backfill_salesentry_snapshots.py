"""
ARCH-2A: Backfill snapshot fields on all existing SalesEntry rows.

Strategy
────────
Uses a single SQL UPDATE (via queryset.update()) per batch so that:
  • model save() is never called → Investment.refresh_status() is never triggered
  • No Django signals are fired
  • No N+1 queries (one DB round-trip per batch of BATCH_SIZE rows)
  • The migration is idempotent — rows already backfilled are skipped

What is written
───────────────
  pts_at_sale        = current medicine.pts   (best-effort: reflects today's
                                               price, not the price at sale time)
  value_at_sale      = quantity × pts_at_sale
  is_snapshot_legacy = True                   (signals these are approximations)

Rows added AFTER this migration runs will have real snapshots captured by
SalesEntry._capture_snapshot() in save() and will have is_snapshot_legacy=False.

Reverse
───────
The reverse operation resets pts_at_sale, value_at_sale to NULL and
is_snapshot_legacy to False, restoring the pre-ARCH-2A state.

Safety guarantees
─────────────────
• No existing column is dropped or renamed.
• No existing data is deleted.
• The forward migration is safe to re-run (idempotent filter on value_at_sale IS NULL).
• refresh_status() is NOT called during backfill — investment statuses are unchanged.
"""

from decimal import Decimal

from django.db import migrations


BATCH_SIZE = 500


def _forward_backfill(apps, schema_editor):
    """
    Backfill pts_at_sale, value_at_sale, is_snapshot_legacy on all
    SalesEntry rows where value_at_sale is still NULL.

    Uses the historical model states provided by the migration framework
    (apps.get_model) to stay compatible with future schema changes.
    """
    SalesEntry = apps.get_model("sales", "SalesEntry")

    # Only process rows that haven't been snapshotted yet.
    qs = (
        SalesEntry.objects
        .filter(value_at_sale__isnull=True)
        .select_related("medicine")
        .only("id", "quantity", "medicine_id")
    )

    total = qs.count()
    if total == 0:
        return  # Nothing to backfill.

    processed = 0
    offset = 0

    while offset < total:
        batch = list(qs[offset : offset + BATCH_SIZE])
        if not batch:
            break

        for entry in batch:
            pts = entry.medicine.pts
            entry.pts_at_sale = pts
            entry.value_at_sale = Decimal(str(entry.quantity)) * pts
            entry.is_snapshot_legacy = True

        # bulk_update touches only the three snapshot fields.
        # save() is never called — no signals, no refresh_status().
        SalesEntry.objects.bulk_update(
            batch,
            ["pts_at_sale", "value_at_sale", "is_snapshot_legacy"],
        )
        processed += len(batch)
        offset += BATCH_SIZE


def _reverse_backfill(apps, schema_editor):
    """
    Undo the backfill: clear snapshot fields on legacy rows.
    This restores the pre-ARCH-2A state for rows that were backfilled
    (is_snapshot_legacy=True).  Rows with real snapshots are untouched.
    """
    SalesEntry = apps.get_model("sales", "SalesEntry")
    SalesEntry.objects.filter(is_snapshot_legacy=True).update(
        pts_at_sale=None,
        value_at_sale=None,
        is_snapshot_legacy=False,
    )


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0009_salesentry_snapshot_fields"),
    ]

    operations = [
        migrations.RunPython(
            _forward_backfill,
            reverse_code=_reverse_backfill,
        ),
    ]
