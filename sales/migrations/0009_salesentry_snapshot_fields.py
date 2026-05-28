"""
ARCH-2A: Add snapshot accounting fields to SalesEntry.

Adds three new fields:
    pts_at_sale        – medicine.pts frozen at sale time (nullable)
    value_at_sale      – quantity × pts_at_sale frozen at sale time (nullable)
    is_snapshot_legacy – True for rows backfilled by the ARCH-2A data migration

All three fields are nullable so existing rows are unaffected by this schema
migration.  A separate data migration (0010) backfills existing rows.

Safety notes
────────────
• No existing fields are modified or removed.
• No default values are injected into existing rows by this migration.
• The migration is fully reversible (AlterField / RemoveField in reverse).
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0008_salesentry_investment"),
    ]

    operations = [
        migrations.AddField(
            model_name="salesentry",
            name="pts_at_sale",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                editable=False,
                help_text=(
                    "medicine.pts at the moment of this sale. "
                    "Frozen on creation — never recalculated. "
                    "All financial calculations must use this field, not medicine.pts."
                ),
                max_digits=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="salesentry",
            name="value_at_sale",
            field=models.DecimalField(
                blank=True,
                decimal_places=2,
                editable=False,
                help_text=(
                    "quantity × pts_at_sale, computed and frozen at creation. "
                    "This is the immutable financial value of the entry. "
                    "Never recalculated after the first save."
                ),
                max_digits=14,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="salesentry",
            name="is_snapshot_legacy",
            field=models.BooleanField(
                db_index=True,
                default=False,
                help_text=(
                    "True for entries whose pts_at_sale / value_at_sale were backfilled "
                    "by the ARCH-2A migration rather than captured at sale time. "
                    "These values are best-effort approximations of the original price."
                ),
            ),
        ),
    ]
