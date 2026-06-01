# MR-8.0: Create PostpaidCampaignCorrection model.
#
# Append-only audit adjustment records for Settled or Locked campaigns.
# Captures a snapshot of campaign financials at the time of each correction.

import django.db.models.deletion
import django.utils.timezone
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0014_drop_postpaid_entry"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="PostpaidCampaignCorrection",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "campaign",
                    models.ForeignKey(
                        help_text="The Settled or Locked campaign this correction applies to.",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="corrections",
                        to="sales.postpaidcampaign",
                    ),
                ),
                (
                    "corrected_by",
                    models.ForeignKey(
                        blank=True,
                        help_text="Admin user who authorised this correction.",
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="campaign_corrections",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "corrected_at",
                    models.DateTimeField(
                        default=django.utils.timezone.now,
                        help_text="Timestamp when the correction was recorded.",
                    ),
                ),
                (
                    "correction_reason",
                    models.CharField(
                        choices=[
                            ("WRITE_OFF", "Write-off (Approved Balance Waiver)"),
                            ("PAYMENT_MISSED", "Missed Payment (Recorded Outside System)"),
                            ("DATA_CORRECTION", "Data Correction (Entry Error)"),
                            ("DISPUTE_RESOLUTION", "Dispute Resolution"),
                            ("MANAGEMENT_APPROVAL", "Management Approval"),
                            ("OTHER", "Other (See Notes)"),
                        ],
                        help_text="Predefined reason code for this correction.",
                        max_length=30,
                    ),
                ),
                (
                    "amount_adjustment",
                    models.DecimalField(
                        decimal_places=2,
                        help_text=(
                            "Signed adjustment amount. Positive = additional amount owed. "
                            "Negative = credit / write-off against the original balance."
                        ),
                        max_digits=12,
                    ),
                ),
                (
                    "notes",
                    models.TextField(
                        help_text="Mandatory narrative justification for this correction.",
                    ),
                ),
                (
                    "reference",
                    models.CharField(
                        blank=True,
                        help_text=(
                            "Optional external reference (e.g. management approval email, ticket ID)."
                        ),
                        max_length=200,
                    ),
                ),
                (
                    "snapshot_total_commission",
                    models.DecimalField(
                        decimal_places=2,
                        editable=False,
                        help_text="Campaign total_commission at the time this correction was recorded.",
                        max_digits=12,
                    ),
                ),
                (
                    "snapshot_paid_amount",
                    models.DecimalField(
                        decimal_places=2,
                        editable=False,
                        help_text="Campaign paid_amount at the time this correction was recorded.",
                        max_digits=12,
                    ),
                ),
                (
                    "snapshot_outstanding_balance",
                    models.DecimalField(
                        decimal_places=2,
                        editable=False,
                        help_text="Campaign outstanding balance at the time this correction was recorded.",
                        max_digits=12,
                    ),
                ),
            ],
            options={
                "verbose_name": "Campaign Correction",
                "verbose_name_plural": "Campaign Corrections",
                "ordering": ["-corrected_at", "-created_at"],
                "abstract": False,
            },
        ),
    ]
