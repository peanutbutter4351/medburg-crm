"""
Sales models — SalesEntry, PostpaidCampaign engine, and Correction Layer.

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

Postpaid Engine (MR-5 / MR-6 / MR-7 / MR-8)
─────────────────────────────────────────────
• PostpaidCampaign    — per-doctor/month campaign ledger
• PostpaidSaleEntry   — frozen-snapshot sale line items
• CampaignPayment     — append-only payment ledger
• PostpaidCampaignCorrection — append-only audit adjustments on locked campaigns

NOTE: The legacy PostpaidEntry model has been fully removed in MR-8.0.
All postpaid commission tracking now uses the PostpaidCampaign engine.
"""

from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Sum
from django.utils import timezone

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
        verbose_name = "Prepaid Sale"
        verbose_name_plural = "Prepaid Sales"
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
        # ── Detect investment FK change before writing ──────────────────────
        # On creation, _state.adding is True and there is no old record.
        # On update, we fetch the current DB value of investment_id so we can
        # refresh the OLD investment's balance after a reassignment.
        old_investment_id = None
        if not self._state.adding and self.pk:
            try:
                old_investment_id = (
                    SalesEntry.objects
                    .filter(pk=self.pk)
                    .values_list("investment_id", flat=True)
                    .get()
                )
            except SalesEntry.DoesNotExist:
                old_investment_id = None

        if self._state.adding:
            self.full_clean()
            # Capture price snapshot before the first write.
            # This must come AFTER full_clean() so medicine is validated.
            self._capture_snapshot()

        super().save(*args, **kwargs)

        # ── Refresh investment balances after save ──────────────────────────
        # Always refresh the current (new) investment if set.
        if self.investment:
            self.investment.refresh_status()

        # ARCH-3B (W-5): also refresh the OLD investment when the FK changed.
        # Without this, the old investment's balance stays stale until the
        # next SalesEntry linked to it is saved.
        if (
            old_investment_id
            and old_investment_id != self.investment_id
        ):
            from doctors.models import Investment as Inv
            try:
                old_inv = Inv.objects.get(pk=old_investment_id)
                old_inv.refresh_status()
            except Inv.DoesNotExist:
                pass  # Investment was deleted concurrently — safe to ignore.


# ─────────────────────────────────────────────────────────────────────────────
# Legacy PostpaidEntry REMOVED in MR-8.0.
# All postpaid commission tracking now uses the PostpaidCampaign engine.
# The database table was dropped via migration 0014_drop_postpaid_entry.
# ─────────────────────────────────────────────────────────────────────────────


# ─────────────────────────────────────────────────────────────────────────────
# ARCH-4B: Postpaid Engine
# ─────────────────────────────────────────────────────────────────────────────

class PostpaidCampaign(BaseModel):
    STATUS_AWAITING_COMMISSION = 'awaiting_commission'
    STATUS_OPEN = 'open'
    STATUS_PARTIAL = 'partial'
    STATUS_SETTLED = 'settled'
    STATUS_LOCKED = 'locked'
    
    STATUS_CHOICES = [
        (STATUS_AWAITING_COMMISSION, 'Awaiting Commission'),
        (STATUS_OPEN, 'Open'),
        (STATUS_PARTIAL, 'Partial'),
        (STATUS_SETTLED, 'Settled'),
        (STATUS_LOCKED, 'Locked'),
    ]

    doctor = models.ForeignKey('doctors.Doctor', on_delete=models.CASCADE, related_name='postpaid_campaigns')
    month = models.PositiveSmallIntegerField()
    year = models.PositiveSmallIntegerField()
    
    commission_percentage = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_AWAITING_COMMISSION, db_index=True)
    
    total_sales_value = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    total_commission = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    paid_amount = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal('0.00'))
    
    locked_at = models.DateTimeField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    REASON_WRITE_OFF = "WRITE_OFF"
    REASON_DISPUTE = "DISPUTE"
    REASON_PROMOTIONAL_SUPPORT = "PROMOTIONAL_SUPPORT"
    REASON_MANAGEMENT_APPROVAL = "MANAGEMENT_APPROVAL"
    REASON_DATA_CORRECTION = "DATA_CORRECTION"
    REASON_OTHER = "OTHER"

    SETTLEMENT_REASON_CHOICES = [
        (REASON_WRITE_OFF, "Write-off (Approved deviation)"),
        (REASON_DISPUTE, "Resolved Dispute"),
        (REASON_PROMOTIONAL_SUPPORT, "Promotional Support"),
        (REASON_MANAGEMENT_APPROVAL, "Management Approval"),
        (REASON_DATA_CORRECTION, "Data Correction"),
        (REASON_OTHER, "Other (Reason in Notes)"),
    ]

    settled_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="settled_campaigns"
    )
    settlement_reason = models.CharField(
        max_length=50,
        choices=SETTLEMENT_REASON_CHOICES,
        null=True,
        blank=True
    )
    settlement_notes = models.TextField(null=True, blank=True)
    settlement_attachment = models.FileField(
        upload_to="settlements/",
        null=True,
        blank=True
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Postpaid Campaign"
        verbose_name_plural = "Postpaid Campaigns"
        ordering = ['-year', '-month', 'doctor__name']
        constraints = [
            models.UniqueConstraint(fields=['doctor', 'month', 'year'], name='unique_campaign_month_year')
        ]

    def __str__(self):
        return f"{self.doctor.name} - {self.month}/{self.year} ({self.get_status_display()})"

    @property
    def outstanding_balance(self):
        return self.total_commission - self.paid_amount

    def clean(self):
        super().clean()
        if self.pk:
            try:
                original = PostpaidCampaign.objects.get(pk=self.pk)
                # Locked campaigns: nothing is editable
                if original.status == self.STATUS_LOCKED:
                    raise ValidationError("Locked campaigns cannot be edited.")
                
                # If status transitions past open, block changing commission_percentage
                if original.status in (self.STATUS_PARTIAL, self.STATUS_SETTLED, self.STATUS_LOCKED):
                    if self.commission_percentage != original.commission_percentage:
                        raise ValidationError("Commission percentage is locked and cannot be edited once payments have started.")
            except PostpaidCampaign.DoesNotExist:
                pass

        # Manual settlement checklist validation
        if self.status == self.STATUS_SETTLED:
            if self.outstanding_balance > Decimal("0.00"):
                if not self.settlement_reason:
                    raise ValidationError({"settlement_reason": "Settlement reason is required when outstanding balance is greater than zero."})
                if not self.settlement_notes or not self.settlement_notes.strip():
                    raise ValidationError({"settlement_notes": "Settlement notes are required when outstanding balance is greater than zero."})

    def save(self, *args, **kwargs):
        # Auto-transition status from awaiting_commission to open if commission is set
        if self.status == self.STATUS_AWAITING_COMMISSION and self.commission_percentage is not None:
            self.status = self.STATUS_OPEN
            
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status in (self.STATUS_PARTIAL, self.STATUS_SETTLED, self.STATUS_LOCKED):
            raise ValidationError("Cannot delete a campaign that is partial, settled, or locked.")
        super().delete(*args, **kwargs)

    def calculate_totals(self):
        """
        Recalculate total_sales_value and total_commission from PostpaidSaleEntry.
        Must be called explicitly (e.g. by PostpaidSaleEntry.save).
        Does not save the model itself.
        """
        agg = self.sales_entries.aggregate(
            sales=Sum('value_at_sale'),
            comm=Sum('commission_at_sale')
        )
        self.total_sales_value = agg['sales'] or Decimal('0.00')
        self.total_commission = agg['comm'] or Decimal('0.00')

    def refresh_status(self):
        """
        Recalculate paid_amount from CampaignPayment ledger and advance status.
        """
        agg = self.payments.aggregate(total=Sum('amount'))
        self.paid_amount = agg['total'] or Decimal('0.00')

        self.calculate_totals()
        
        # Locked status is a final state set manually by admin; do not auto-demote or auto-promote from locked
        if self.status == self.STATUS_LOCKED:
            self.save(update_fields=['paid_amount', 'total_sales_value', 'total_commission', 'updated_at'])
            return

        # Settled status: do not auto-demote or auto-promote from settled
        if self.status == self.STATUS_SETTLED:
            self.save(update_fields=['paid_amount', 'total_sales_value', 'total_commission', 'updated_at'])
            return

        new_status = self.status
        
        if self.status == self.STATUS_AWAITING_COMMISSION:
            if self.commission_percentage is not None:
                new_status = self.STATUS_OPEN
        elif self.status == self.STATUS_OPEN:
            # Open stays open until manually advanced to Partial
            pass
        elif self.status == self.STATUS_PARTIAL:
            # Auto-settlement removed. Must remain Partial until manually settled.
            pass

        if self.status != new_status:
            self.status = new_status

        self.save(update_fields=['paid_amount', 'total_sales_value', 'total_commission', 'status', 'settled_at', 'updated_at'])

    def update_commission_percentage(self, new_percentage):
        """
        Update commission percentage for this campaign and recalculate all linked sales entries' commissions.
        Can only be done in awaiting_commission or open status.
        """
        if self.status not in (self.STATUS_AWAITING_COMMISSION, self.STATUS_OPEN):
            raise ValidationError("Commission percentage can only be edited when status is Awaiting Commission or Open.")
        
        self.commission_percentage = new_percentage
        if self.status == self.STATUS_AWAITING_COMMISSION and new_percentage is not None:
            self.status = self.STATUS_OPEN
            
        self.save(update_fields=['commission_percentage', 'status', 'updated_at'])
        
        # Update all linked sales entries' commissions
        for sale in self.sales_entries.all():
            sale.commission_percentage_at_sale = new_percentage or Decimal('0.00')
            sale.commission_at_sale = sale.value_at_sale * (sale.commission_percentage_at_sale / Decimal('100.0'))
            sale.save(update_fields=['commission_percentage_at_sale', 'commission_at_sale', 'updated_at'])
            
        self.calculate_totals()
        self.save(update_fields=['total_sales_value', 'total_commission', 'updated_at'])


class PostpaidSaleEntry(BaseModel):
    campaign = models.ForeignKey(PostpaidCampaign, on_delete=models.CASCADE, related_name='sales_entries')
    medicine = models.ForeignKey('medicines.Medicine', on_delete=models.CASCADE, related_name='postpaid_sales')
    quantity = models.PositiveIntegerField()
    
    pts_at_sale = models.DecimalField(max_digits=10, decimal_places=2, editable=False)
    value_at_sale = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    
    commission_percentage_at_sale = models.DecimalField(max_digits=6, decimal_places=2, editable=False)
    commission_at_sale = models.DecimalField(max_digits=12, decimal_places=2, editable=False)
    
    entry_date = models.DateField()
    rep = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Postpaid Sale"
        verbose_name_plural = "Postpaid Sales"
        ordering = ['-entry_date', '-created_at']

    def __str__(self):
        return f"{self.medicine.name} x {self.quantity} for {self.campaign.doctor.name}"

    def clean(self):
        super().clean()
        if self.campaign_id:
            # Check campaign status. Sales blocked if status is partial, settled, or locked
            if self.campaign.status in (
                PostpaidCampaign.STATUS_PARTIAL,
                PostpaidCampaign.STATUS_SETTLED,
                PostpaidCampaign.STATUS_LOCKED,
            ):
                raise ValidationError({"campaign": "Cannot add or modify sales for a campaign that is partial, settled, or locked."})

            # Check if this is a new attachment or reassignment to a campaign
            campaign_changed = True
            if self.pk:
                try:
                    old_campaign_id = PostpaidSaleEntry.objects.values_list('campaign_id', flat=True).get(pk=self.pk)
                    campaign_changed = (old_campaign_id != self.campaign_id)
                except PostpaidSaleEntry.DoesNotExist:
                    pass
            
            if (self._state.adding or campaign_changed) and self.campaign.status in (
                PostpaidCampaign.STATUS_PARTIAL,
                PostpaidCampaign.STATUS_SETTLED,
                PostpaidCampaign.STATUS_LOCKED,
            ):
                raise ValidationError({"campaign": "Cannot attach sales to a locked, partial, or settled campaign."})

    def _capture_snapshot(self):
        self.pts_at_sale = self.medicine.pts
        self.value_at_sale = Decimal(self.quantity) * self.pts_at_sale
        self.commission_percentage_at_sale = self.campaign.commission_percentage or Decimal('0.00')
        self.commission_at_sale = self.value_at_sale * (self.commission_percentage_at_sale / Decimal('100.0'))

    def save(self, *args, **kwargs):
        # 1. Capture snapshots on creation
        if self._state.adding:
            self.full_clean()
            self._capture_snapshot()
            
        super().save(*args, **kwargs)
        
        # 2. Update campaign totals
        if self.campaign_id:
            self.campaign.calculate_totals()
            self.campaign.save(update_fields=['total_sales_value', 'total_commission', 'updated_at'])

    def delete(self, *args, **kwargs):
        if self.campaign.status in (PostpaidCampaign.STATUS_PARTIAL, PostpaidCampaign.STATUS_SETTLED, PostpaidCampaign.STATUS_LOCKED):
            raise ValidationError("Cannot delete sales entries on a campaign that is partial, settled, or locked.")
        campaign = self.campaign
        super().delete(*args, **kwargs)
        if campaign:
            campaign.calculate_totals()
            campaign.save(update_fields=['total_sales_value', 'total_commission', 'updated_at'])


class CampaignPayment(BaseModel):
    campaign = models.ForeignKey(PostpaidCampaign, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    payment_date = models.DateField()
    reference = models.CharField(max_length=200, blank=True)
    notes = models.TextField(blank=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Campaign Payment"
        verbose_name_plural = "Campaign Payments"
        ordering = ['-payment_date', '-created_at']

    def __str__(self):
        return f"\u20b9{self.amount} for {self.campaign}"

    def clean(self):
        super().clean()
        if self.pk:
            raise ValidationError("Ledger entries are append-only and cannot be modified.")
        if self.amount is not None and self.amount <= Decimal('0'):
            raise ValidationError({"amount": "Payment amount must be positive."})
        
        if self.campaign_id:
            # Payments allowed only when campaign is partial.
            # Blocked when awaiting_commission, open, settled, or locked.
            if self.campaign.status != PostpaidCampaign.STATUS_PARTIAL:
                raise ValidationError({
                    "campaign": (
                        f"Payments can only be recorded for Partial campaigns. "
                        f"Current status: {self.campaign.get_status_display()}"
                    )
                })

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Ledger entries cannot be modified. Cancel and recreate instead.")
        
        self.full_clean()
        super().save(*args, **kwargs)
        
        # Must trigger refresh_status on the campaign
        self.campaign.refresh_status()

    def delete(self, *args, **kwargs):
        raise ValidationError("Ledger entries cannot be deleted.")


# ─────────────────────────────────────────────────────────────────────────────
# MR-8.0: Postpaid Correction Layer
# ─────────────────────────────────────────────────────────────────────────────


class PostpaidCampaignCorrection(BaseModel):
    """
    Append-only audit adjustment record for a Settled or Locked PostpaidCampaign.

    Design principles (MR-8.0)
    ──────────────────────────
    • Corrections are APPEND-ONLY. save() blocks updates. delete() is blocked
      entirely. Financial adjustments must always be forward-looking entries.
    • The campaign itself stays LOCKED. Corrections do NOT mutate the campaign.
    • Each correction snapshots the campaign's financial state at the time of
      the correction so the full adjustment history is self-contained.
    • amount_adjustment may be positive (increase owed) or negative (credit).
    • corrected_by is required and captured from the authenticated user at
      creation time in the view/admin layer.

    Typical use-cases
    ─────────────────
    • Post-lock write-off of a residual balance.
    • Addition of a missed payment recorded outside the system.
    • Correction of a data-entry error discovered after locking.
    """

    REASON_WRITE_OFF = "WRITE_OFF"
    REASON_PAYMENT_MISSED = "PAYMENT_MISSED"
    REASON_DATA_CORRECTION = "DATA_CORRECTION"
    REASON_DISPUTE_RESOLUTION = "DISPUTE_RESOLUTION"
    REASON_MANAGEMENT_APPROVAL = "MANAGEMENT_APPROVAL"
    REASON_OTHER = "OTHER"

    CORRECTION_REASON_CHOICES = [
        (REASON_WRITE_OFF, "Write-off (Approved Balance Waiver)"),
        (REASON_PAYMENT_MISSED, "Missed Payment (Recorded Outside System)"),
        (REASON_DATA_CORRECTION, "Data Correction (Entry Error)"),
        (REASON_DISPUTE_RESOLUTION, "Dispute Resolution"),
        (REASON_MANAGEMENT_APPROVAL, "Management Approval"),
        (REASON_OTHER, "Other (See Notes)"),
    ]

    # ── Campaign link ─────────────────────────────────────────────────────────
    # PROTECT prevents cascade-deleting corrections when a campaign is removed.
    campaign = models.ForeignKey(
        PostpaidCampaign,
        on_delete=models.PROTECT,
        related_name="corrections",
        help_text="The Settled or Locked campaign this correction applies to.",
    )

    # ── Audit identity ────────────────────────────────────────────────────────
    corrected_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="campaign_corrections",
        help_text="Admin user who authorised this correction.",
    )
    corrected_at = models.DateTimeField(
        default=timezone.now,
        help_text="Timestamp when the correction was recorded.",
    )

    # ── Correction detail ─────────────────────────────────────────────────────
    correction_reason = models.CharField(
        max_length=30,
        choices=CORRECTION_REASON_CHOICES,
        help_text="Predefined reason code for this correction.",
    )
    amount_adjustment = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text=(
            "Signed adjustment amount. Positive = additional amount owed. "
            "Negative = credit / write-off against the original balance."
        ),
    )
    notes = models.TextField(
        help_text="Mandatory narrative justification for this correction.",
    )
    reference = models.CharField(
        max_length=200,
        blank=True,
        help_text="Optional external reference (e.g. management approval email, ticket ID).",
    )

    # ── Campaign state snapshot at correction time ────────────────────────────
    # Frozen at creation so the correction log is self-contained.
    snapshot_total_commission = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False,
        help_text="Campaign total_commission at the time this correction was recorded.",
    )
    snapshot_paid_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False,
        help_text="Campaign paid_amount at the time this correction was recorded.",
    )
    snapshot_outstanding_balance = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        editable=False,
        help_text="Campaign outstanding balance at the time this correction was recorded.",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Campaign Correction"
        verbose_name_plural = "Campaign Corrections"
        ordering = ["-corrected_at", "-created_at"]

    def __str__(self):
        sign = "+" if self.amount_adjustment >= Decimal("0") else ""
        return (
            f"Correction {sign}₹{self.amount_adjustment} — "
            f"{self.campaign} — {self.get_correction_reason_display()}"
        )

    def _capture_campaign_snapshot(self):
        """Freeze campaign financial state at correction creation time."""
        campaign = self.campaign
        self.snapshot_total_commission = campaign.total_commission
        self.snapshot_paid_amount = campaign.paid_amount
        self.snapshot_outstanding_balance = campaign.outstanding_balance

    def clean(self):
        super().clean()
        errors = {}

        # Correction reason is required
        if not self.correction_reason:
            errors["correction_reason"] = "A correction reason is required."

        # Notes are mandatory
        if not self.notes or not self.notes.strip():
            errors["notes"] = "Justification notes are required for every correction."

        # amount_adjustment cannot be zero
        if self.amount_adjustment is not None and self.amount_adjustment == Decimal("0"):
            errors["amount_adjustment"] = "Adjustment amount cannot be zero."

        # Campaign must be Settled or Locked to receive corrections
        if self.campaign_id:
            if self.campaign.status not in (
                PostpaidCampaign.STATUS_SETTLED,
                PostpaidCampaign.STATUS_LOCKED,
            ):
                errors["campaign"] = (
                    "Corrections can only be applied to Settled or Locked campaigns. "
                    f"Current status: {self.campaign.get_status_display()}"
                )

        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        """Append-only: creation allowed, updates blocked."""
        if not self._state.adding:
            raise ValueError(
                "Campaign corrections are append-only and cannot be modified. "
                "Record a new correction to reverse or amend a previous one."
            )
        self._capture_campaign_snapshot()
        self.full_clean()
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        """Corrections cannot be deleted — they form an immutable audit trail."""
        raise ValidationError(
            "Campaign corrections cannot be deleted. "
            "They form a permanent audit trail."
        )
