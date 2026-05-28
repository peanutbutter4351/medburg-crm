"""
Sales models — SalesEntry and PostpaidEntry.

Business rules  (ARCH-2A Snapshot Accounting)
──────────────────────────────────────────────
• Reps enter **quantity** only — never raw value.
• On creation:  pts_at_sale  = medicine.pts   (immutable snapshot)
                value_at_sale = quantity × pts_at_sale  (immutable snapshot)
• ALL financial calculations use value_at_sale — NEVER live medicine.pts.
• Achieved ROI = Σ value_at_sale across all SalesEntry rows for an investment.
• Balance ROI  = Investment.roi_amount − Achieved ROI
• Negative balance is VALID (over-achieved ROI).

Snapshot fields
───────────────
• pts_at_sale       — price at time of sale (frozen forever after creation)
• value_at_sale     — quantity × pts_at_sale (frozen forever after creation)
• is_snapshot_legacy— True for rows backfilled before ARCH-2A (best-effort)

PostpaidEntry
─────────────
• Records ROI payments for doctors in postpaid mode.
• Linked to a Doctor and Medicine with roi_percentage.
• amount is auto-computed from scoped SalesEntry data on **first save only**.
• total_sales_value stores the sales snapshot used in calculation (audit trail).
• Supports three payout scopes: date range, monthly, campaign.
• Unique constraints prevent duplicate payouts for the same scope.
• payment_status tracks unpaid → partial → paid lifecycle.
• paid_amount tracks the actual amount disbursed (supports partial payments).
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import F, Sum
from django.db.models.functions import Coalesce

from core.constants import (
    PAYMENT_STATUS_CHOICES,
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PARTIAL,
    PAYMENT_STATUS_UNPAID,
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
    investment = models.ForeignKey(
        "doctors.Investment",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="sales_entries",
        help_text="Investment this sales entry belongs to.",
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

    # ── ARCH-2A Snapshot fields (frozen at creation, never updated) ───────────
    pts_at_sale = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        editable=False,
        help_text=(
            "medicine.pts at the moment of this sale. "
            "Frozen on creation — never recalculated. "
            "All financial calculations must use this field, not medicine.pts."
        ),
    )
    value_at_sale = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        null=True,
        blank=True,
        editable=False,
        help_text=(
            "quantity × pts_at_sale, computed and frozen at creation. "
            "This is the immutable financial value of the entry. "
            "Never recalculated after the first save."
        ),
    )
    is_snapshot_legacy = models.BooleanField(
        default=False,
        db_index=True,
        help_text=(
            "True for entries whose pts_at_sale / value_at_sale were backfilled "
            "by the ARCH-2A migration rather than captured at sale time. "
            "These values are best-effort approximations of the original price."
        ),
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

    # ── Value properties ─────────────────────────────────────────────────────
    @property
    def value(self):
        """
        The financial value of this entry.

        Returns value_at_sale (frozen snapshot) when available.
        Falls back to live quantity × medicine.pts ONLY for legacy rows
        that have not yet been backfilled (is_snapshot_legacy rows are
        always backfilled, so this path is only hit if snapshot is None).

        After ARCH-2A migration completes, value_at_sale will be non-null
        for every row and the fallback will never be reached.
        """
        if self.value_at_sale is not None:
            return self.value_at_sale
        # Fallback: legacy row without snapshot (should not occur after backfill)
        return self.quantity * self.medicine.pts

    @property
    def total_value(self):
        """Alias for value — used by template and service aggregation."""
        return self.value

    # ── Snapshot population ──────────────────────────────────────────────────
    def _capture_snapshot(self):
        """
        Capture the immutable price snapshot at sale time.

        Called ONLY during the first save (self._state.adding).
        Sets pts_at_sale and value_at_sale from medicine.pts.
        These fields are never overwritten by subsequent saves.
        """
        self.pts_at_sale = self.medicine.pts
        self.value_at_sale = Decimal(str(self.quantity)) * self.pts_at_sale

    def clean(self):
        super().clean()
        if self._state.adding:
            if self.doctor and self.doctor.mode == "prepaid" and not self.investment:
                raise ValidationError({"investment": "Investment is required for prepaid doctors."})

        if self.investment:
            # Cross-FK integrity: investment must belong to the selected doctor
            if self.doctor_id and self.investment.doctor_id != self.doctor_id:
                raise ValidationError({"investment": "Investment does not belong to the selected doctor."})
            if self._state.adding and self.investment.status == "completed":
                raise ValidationError({"investment": "Completed investments cannot accept new sales entries."})

    def save(self, *args, **kwargs):
        if self._state.adding:
            self.full_clean()
            # Capture price snapshot before the first write.
            # This must come AFTER full_clean() so medicine is validated.
            self._capture_snapshot()
        super().save(*args, **kwargs)
        if self.investment:
            self.investment.refresh_status()


class PostpaidEntry(BaseModel):
    """
    A postpaid ROI entry for a doctor.

    Financial integrity
    ───────────────────
    • amount is computed **once** on initial save and never recalculated.
    • total_sales_value stores the raw sales total used in the calculation
      as an auditable snapshot.
    • Unique constraints per payout type prevent duplicate payouts.

    Payment lifecycle
    ─────────────────
    unpaid → partial → paid
    • payment_status replaces the old is_paid boolean.
    • paid_amount tracks the actual disbursement (supports partial payments).
    • balance_amount = amount − paid_amount.

    Payout scopes
    ─────────────
    range    → amount computed from SalesEntry within [start_date, end_date]
    monthly  → amount computed from SalesEntry in a specific month/year
    campaign → amount computed from all SalesEntry (no date filter)

    amount = Σ SalesEntry.total_value × (roi_percentage / 100)
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

    # ── Computed on first save ──────────────────────
    is_legacy_calculation = models.BooleanField(
        default=False,
        help_text="Protects historical payouts from recalculation after PTR→PTS migration.",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        editable=False,
        help_text="Auto-calculated on creation: scoped sales value × ROI%. Frozen after first save.",
    )
    total_sales_value = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        editable=False,
        help_text="Snapshot of the total sales value used to compute amount.",
    )

    # ── Payment tracking ────────────────────────────
    payment_status = models.CharField(
        max_length=10,
        choices=PAYMENT_STATUS_CHOICES,
        default=PAYMENT_STATUS_UNPAID,
        db_index=True,
        help_text="Payment lifecycle: unpaid → partial → paid.",
    )
    paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=Decimal("0"),
        help_text="Actual amount paid so far. May be less than amount for partial payments.",
    )
    payment_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date of the most recent payment.",
    )
    remarks = models.TextField(
        blank=True,
        help_text="Optional remarks about this postpaid entry.",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Postpaid Entry"
        verbose_name_plural = "Postpaid Entries"
        ordering = ["-created_at"]
        constraints = [
            # Prevent duplicate payouts for the same doctor+medicine+scope.
            # One constraint per payout type using condition= to handle
            # the different nullable scope fields cleanly.
            models.UniqueConstraint(
                fields=["doctor", "medicine", "payout_type", "start_date", "end_date"],
                condition=models.Q(payout_type="range"),
                name="unique_postpaid_range",
            ),
            models.UniqueConstraint(
                fields=["doctor", "medicine", "payout_type", "payout_month", "payout_year"],
                condition=models.Q(payout_type="monthly"),
                name="unique_postpaid_monthly",
            ),
            models.UniqueConstraint(
                fields=["doctor", "medicine", "payout_type"],
                condition=models.Q(payout_type="campaign"),
                name="unique_postpaid_campaign",
            ),
        ]

    def __str__(self):
        return (
            f"{self.doctor.name} | {self.medicine.name} "
            f"– ₹{self.amount} ({self.get_payment_status_display()})"
        )

    # ── Backward-compatible properties ──────────────
    @property
    def is_paid(self):
        """Backward compat: True when fully paid."""
        return self.payment_status == PAYMENT_STATUS_PAID

    @property
    def is_partial(self):
        """True when partially paid."""
        return self.payment_status == PAYMENT_STATUS_PARTIAL

    @property
    def balance_amount(self):
        """Remaining amount to be paid."""
        return self.amount - self.paid_amount

    # ── Validation ──────────────────────────────────
    def clean(self):
        """Validate scope fields and payment consistency."""
        super().clean()
        errors = {}

        # Payout scope validation
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

        # Payment validation
        if self.paid_amount < Decimal("0"):
            errors["paid_amount"] = "Paid amount cannot be negative."
        elif self.amount and self.paid_amount > self.amount:
            errors["paid_amount"] = "Paid amount cannot exceed the entry amount."

        if self.payment_status == PAYMENT_STATUS_PAID and self.paid_amount <= Decimal("0"):
            errors["paid_amount"] = "Paid amount is required when status is fully paid."

        if errors:
            raise ValidationError(errors)

    # ── Auto-compute amount on first save ───────────
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

    def _compute_amount(self):
        """
        Aggregate scoped SalesEntry.total_value and apply ROI%.

        Uses the annotation  quantity × medicine__pts  which mirrors
        the SalesEntry.total_value property at the DB level.

        Sets both total_sales_value (snapshot) and amount.
        """
        self.total_sales_value = self._get_scoped_sales_qs().aggregate(
            total=Coalesce(
                Sum(F("quantity") * F("medicine__pts")),
                Decimal("0"),
            ),
        )["total"]

        self.amount = self.total_sales_value * (
            self.roi_percentage / Decimal("100")
        )

    def save(self, *args, **kwargs):
        """
        Compute amount from scoped sales on **first save only**, then persist.

        Subsequent saves (e.g. marking as paid) skip recalculation so the
        payout amount is never silently altered by changed PTR or new sales.
        Use recalculate_amount() if an explicit recomputation is needed.
        """
        # Only run full validation on creation — subsequent updates
        # (e.g. payment status changes) go through admin or service
        # methods that handle their own consistency checks.
        if self._state.adding:
            self.full_clean()
            self._compute_amount()

        super().save(*args, **kwargs)

    def recalculate_amount(self):
        """
        Explicitly recompute and save the amount.

        Call this when an admin intentionally wants to refresh the
        payout based on current sales data.  This is the only path
        that recalculates after initial save.
        """
        if getattr(self, "is_legacy_calculation", False):
            raise ValidationError(
                "Historical payouts created before the PTR→PTS migration cannot be recalculated."
            )
            
        self._compute_amount()
        super().save(update_fields=["amount", "total_sales_value", "updated_at"])

    def record_payment(self, payment_amount):
        """
        Record a payment against this entry.

        Automatically sets payment_status to 'partial' or 'paid'
        based on the cumulative paid_amount vs amount.
        Uses queryset.update() to avoid triggering save() override.

        Returns self (refreshed from DB).

        Raises ValidationError for invalid input, negative amounts,
        or overpayments.
        """
        from datetime import date
        import decimal

        try:
            payment_amount = Decimal(str(payment_amount))
        except (decimal.InvalidOperation, ValueError):
            raise ValidationError(
                {"paid_amount": "Invalid payment amount. Please enter a valid number."}
            )

        if payment_amount <= Decimal("0"):
            raise ValidationError({"paid_amount": "Payment amount must be positive."})

        new_paid = self.paid_amount + payment_amount
        if new_paid > self.amount:
            raise ValidationError(
                {"paid_amount": f"Payment of \u20b9{payment_amount} would exceed balance of \u20b9{self.balance_amount}."}
            )

        if new_paid >= self.amount:
            new_status = PAYMENT_STATUS_PAID
        else:
            new_status = PAYMENT_STATUS_PARTIAL

        PostpaidEntry.objects.filter(pk=self.pk).update(
            paid_amount=new_paid,
            payment_status=new_status,
            payment_date=date.today(),
        )
        self.refresh_from_db()
        return self

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

