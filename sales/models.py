"""
Sales models — SalesEntry and PostpaidEntry.

Business rules
──────────────
• Reps enter **quantity** only — never raw value.
• Value is computed:  quantity × Medicine.ptr
• Achieved ROI = Σ value across all SalesEntry rows for a doctor.
• Balance ROI  = Investment.roi_amount − Achieved ROI

PostpaidEntry
─────────────
• Records ROI payments for doctors in postpaid mode.
• Linked to a Doctor and Medicine with roi_percentage.
• amount is auto-computed from scoped SalesEntry data on save().
• Supports three payout scopes: date range, monthly, campaign.
• Tracks payment status via is_paid / payment_date.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Sum
from django.db.models.functions import Coalesce

from core.constants import (
    PAYOUT_TYPE_CAMPAIGN,
    PAYOUT_TYPE_CHOICES,
    PAYOUT_TYPE_MONTHLY,
    PAYOUT_TYPE_RANGE,
)
from core.models import BaseModel


class SalesEntry(BaseModel):
    """
    A single sales entry recorded by a sales representative.

    Each row captures: who sold, for which doctor, which medicine,
    how many units, and on what date.
    """

    rep = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="sales_entries",
        limit_choices_to={"role": "rep"},
        help_text="Sales representative who recorded this entry.",
    )
    doctor = models.ForeignKey(
        "doctors.Doctor",
        on_delete=models.CASCADE,
        related_name="sales_entries",
    )
    medicine = models.ForeignKey(
        "medicines.Medicine",
        on_delete=models.CASCADE,
        related_name="sales_entries",
    )
    quantity = models.PositiveIntegerField(
        help_text="Number of units sold.",
    )
    entry_date = models.DateField(
        db_index=True,
        help_text="Date of the sales transaction.",
    )
    notes = models.TextField(
        blank=True,
        help_text="Optional remarks about this entry.",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Sales Entry"
        verbose_name_plural = "Sales Entries"
        ordering = ["-entry_date", "-created_at"]

    def __str__(self):
        return (
            f"{self.doctor.name} | {self.medicine.name} "
            f"× {self.quantity} ({self.entry_date})"
        )

    # ── computed property (not stored) ───────────────
    @property
    def value(self):
        """Calculated value = quantity × PTR of the medicine."""
        return self.quantity * self.medicine.ptr


class PostpaidEntry(BaseModel):
    """
    A postpaid ROI entry for a doctor.

    Payout scopes
    ─────────────
    range    → amount computed from SalesEntry within [start_date, end_date]
    monthly  → amount computed from SalesEntry in a specific month/year
    campaign → amount computed from all SalesEntry (no date filter)

    amount = Σ (SalesEntry.quantity × Medicine.ptr) × (roi_percentage / 100)
    """

    doctor = models.ForeignKey(
        "doctors.Doctor",
        on_delete=models.CASCADE,
        related_name="postpaid_entries",
    )
    medicine = models.ForeignKey(
        "medicines.Medicine",
        on_delete=models.CASCADE,
        related_name="postpaid_entries",
    )
    roi_percentage = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="ROI percentage for this postpaid entry.",
    )

    # ── Payout scope ────────────────────────────────
    payout_type = models.CharField(
        max_length=10,
        choices=PAYOUT_TYPE_CHOICES,
        default=PAYOUT_TYPE_CAMPAIGN,
        db_index=True,
        help_text="Scope used to compute the payout amount.",
    )
    start_date = models.DateField(
        null=True,
        blank=True,
        help_text="Start of date range (required for 'range' payout type).",
    )
    end_date = models.DateField(
        null=True,
        blank=True,
        help_text="End of date range (required for 'range' payout type).",
    )
    payout_month = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Month (1–12) for monthly payout type.",
    )
    payout_year = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Year for monthly payout type.",
    )

    # ── Computed on save ────────────────────────────
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        editable=False,
        help_text="Auto-calculated: scoped sales value × ROI%.",
    )

    # ── Payment tracking ────────────────────────────
    is_paid = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether this entry has been paid.",
    )
    payment_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of payment, if paid.",
    )
    remarks = models.TextField(
        blank=True,
        help_text="Optional remarks about this postpaid entry.",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Postpaid Entry"
        verbose_name_plural = "Postpaid Entries"
        ordering = ["-created_at"]

    def __str__(self):
        status = "Paid" if self.is_paid else "Unpaid"
        return (
            f"{self.doctor.name} | {self.medicine.name} "
            f"– ₹{self.amount} ({status})"
        )

    # ── Validation ──────────────────────────────────
    def clean(self):
        """Validate that required scope fields are present."""
        super().clean()
        errors = {}

        if self.payout_type == PAYOUT_TYPE_RANGE:
            if not self.start_date:
                errors["start_date"] = "Start date is required for date-range payout."
            if not self.end_date:
                errors["end_date"] = "End date is required for date-range payout."
            if self.start_date and self.end_date and self.start_date > self.end_date:
                errors["end_date"] = "End date must be on or after start date."

        elif self.payout_type == PAYOUT_TYPE_MONTHLY:
            if not self.payout_month:
                errors["payout_month"] = "Month is required for monthly payout."
            elif not (1 <= self.payout_month <= 12):
                errors["payout_month"] = "Month must be between 1 and 12."
            if not self.payout_year:
                errors["payout_year"] = "Year is required for monthly payout."

        if errors:
            raise ValidationError(errors)

    # ── Auto-compute amount on save ─────────────────
    def _get_scoped_sales_qs(self):
        """
        Return a SalesEntry queryset filtered by doctor + medicine
        and scoped by payout_type.
        """
        qs = SalesEntry.objects.filter(
            doctor_id=self.doctor_id,
            medicine_id=self.medicine_id,
        )

        if self.payout_type == PAYOUT_TYPE_RANGE:
            qs = qs.filter(
                entry_date__gte=self.start_date,
                entry_date__lte=self.end_date,
            )
        elif self.payout_type == PAYOUT_TYPE_MONTHLY:
            qs = qs.filter(
                entry_date__month=self.payout_month,
                entry_date__year=self.payout_year,
            )
        # campaign → no date filter

        return qs

    def save(self, *args, **kwargs):
        """Compute amount from scoped sales, then save."""
        self.full_clean()

        total_value = self._get_scoped_sales_qs().aggregate(
            total=Coalesce(
                Sum(F("quantity") * F("medicine__ptr")),
                Decimal("0"),
            ),
        )["total"]

        self.amount = total_value * (self.roi_percentage / Decimal("100"))
        super().save(*args, **kwargs)

    # ── Human-readable scope label ──────────────────
    @property
    def scope_display(self):
        """Return a short human-readable scope label."""
        if self.payout_type == PAYOUT_TYPE_RANGE and self.start_date and self.end_date:
            return f"{self.start_date.strftime('%d %b %Y')} – {self.end_date.strftime('%d %b %Y')}"
        elif self.payout_type == PAYOUT_TYPE_MONTHLY and self.payout_month and self.payout_year:
            import calendar
            month_name = calendar.month_abbr[self.payout_month]
            return f"{month_name} {self.payout_year}"
        return "All Time"

