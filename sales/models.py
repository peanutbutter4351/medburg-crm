"""
Sales Entry model.

Business rules
──────────────
• Reps enter **quantity** only — never raw value.
• Value is computed:  quantity × Medicine.ptr
• Achieved ROI = Σ value across all SalesEntry rows for a doctor.
• Balance ROI  = Investment.roi_amount − Achieved ROI
"""

from django.conf import settings
from django.db import models

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
