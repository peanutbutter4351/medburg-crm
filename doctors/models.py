"""
Doctor models — profile, investments, and medicine mapping.

Relationships
─────────────
Doctor  ←  1:N  →  Investment       (multiple investments per doctor)
Doctor  ←  M:N  →  Medicine         (via DoctorMedicine through-table)

ROI logic (computed, NOT stored)
────────────────────────────────
ROI Amount   = Investment.amount × Investment.roi_ratio
Achieved ROI = Σ (SalesEntry.quantity × Medicine.ptr)  for that doctor
Balance ROI  = ROI Amount − Achieved ROI
"""

from django.conf import settings
from django.db import models

from core.constants import (
    DOCTOR_MODE_CHOICES,
    DOCTOR_MODE_PREPAID,
    DOCTOR_TYPE_CHOICES,
    DOCTOR_TYPE_TRADE,
)
from core.models import BaseModel


class Doctor(BaseModel):
    """A doctor / prescriber tracked in the CRM."""

    name = models.CharField(
        max_length=200,
        db_index=True,
    )
    hospital = models.CharField(
        max_length=300,
        blank=True,
        help_text="Hospital or clinic name.",
    )
    location = models.CharField(
        max_length=300,
        blank=True,
        help_text="City / area / region.",
    )
    mode = models.CharField(
        max_length=10,
        choices=DOCTOR_MODE_CHOICES,
        default=DOCTOR_MODE_PREPAID,
        db_index=True,
        help_text="Prepaid = has investment & ROI tracking. "
                  "Postpaid = track sales only.",
    )
    doctor_type = models.CharField(
        max_length=10,
        choices=DOCTOR_TYPE_CHOICES,
        default=DOCTOR_TYPE_TRADE,
        db_index=True,
    )
    assigned_rep = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_doctors",
        limit_choices_to={"role": "rep"},
        help_text="Sales representative assigned to this doctor.",
    )
    medicines = models.ManyToManyField(
        "medicines.Medicine",
        through="DoctorMedicine",
        related_name="doctors",
        blank=True,
    )
    is_active = models.BooleanField(default=True, db_index=True)

    class Meta(BaseModel.Meta):
        verbose_name = "Doctor"
        verbose_name_plural = "Doctors"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Investment(BaseModel):
    """
    An investment made for a specific doctor (prepaid mode).

    A doctor may have multiple investment records over time.
    ROI Amount is computed as:  amount × roi_ratio
    """

    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name="investments",
    )
    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        help_text="Investment amount in currency.",
    )
    roi_ratio = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="ROI multiplier (e.g. 2.5 means 2.5× return expected).",
    )
    start_date = models.DateField(
        help_text="Date from which this investment is active.",
    )
    notes = models.TextField(
        blank=True,
        help_text="Optional remarks about this investment.",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Investment"
        verbose_name_plural = "Investments"
        ordering = ["-start_date"]

    def __str__(self):
        return f"{self.doctor.name} – ₹{self.amount} (×{self.roi_ratio})"

    # ── computed property (not stored) ───────────────
    @property
    def roi_amount(self):
        """ROI Amount = investment × roi_ratio."""
        return self.amount * self.roi_ratio


class DoctorMedicine(BaseModel):
    """
    Through-table: maps which medicines are assigned to which doctor.

    Unique together on (doctor, medicine) to prevent duplicate mappings.
    """

    doctor = models.ForeignKey(
        Doctor,
        on_delete=models.CASCADE,
        related_name="doctor_medicines",
    )
    medicine = models.ForeignKey(
        "medicines.Medicine",
        on_delete=models.CASCADE,
        related_name="doctor_medicines",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Doctor–Medicine Mapping"
        verbose_name_plural = "Doctor–Medicine Mappings"
        constraints = [
            models.UniqueConstraint(
                fields=["doctor", "medicine"],
                name="unique_doctor_medicine",
            ),
        ]
        ordering = ["doctor__name", "medicine__name"]

    def __str__(self):
        return f"{self.doctor.name} ↔ {self.medicine.name}"
