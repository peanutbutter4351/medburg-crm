"""
Medicine catalogue.

Pricing
───────
PTR  (Price To Retailer) → used for value calculations in SalesEntry
PTS  (Price To Stockist)  → reference only
MRP  (Maximum Retail Price) → reference only
"""

from django.db import models

from core.models import BaseModel


class Medicine(BaseModel):
    """A single medicine product in the catalogue."""

    name = models.CharField(
        max_length=200,
        db_index=True,
        help_text="Generic / trade name of the medicine.",
    )
    brand = models.CharField(
        max_length=200,
        blank=True,
        help_text="Brand / manufacturer label.",
    )
    ptr = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="PTR",
        help_text="Price To Retailer — used for sales value calculation.",
    )
    pts = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="PTS",
        help_text="Price To Stockist (reference).",
    )
    mrp = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        verbose_name="MRP",
        help_text="Maximum Retail Price (reference).",
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Inactive medicines are hidden from new entries.",
    )

    class Meta(BaseModel.Meta):
        verbose_name = "Medicine"
        verbose_name_plural = "Medicines"
        ordering = ["name"]

    def __str__(self):
        label = f"{self.name}"
        if self.brand:
            label += f" ({self.brand})"
        return label
