"""
Admin configuration for the medicines app.
"""

from django.contrib import admin

from core.admin_mixins import ExcelImportAdminMixin
from .importers import MedicineImporter
from .models import Medicine


@admin.register(Medicine)
class MedicineAdmin(ExcelImportAdminMixin, admin.ModelAdmin):
    """Medicine catalogue management."""

    importer_class = MedicineImporter

    list_display = (
        "name",
        "brand",
        "ptr",
        "pts",
        "mrp",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active", "brand")
    search_fields = ("name", "brand")
    list_editable = ("ptr", "pts", "mrp", "is_active")
    list_per_page = 30
    ordering = ("name",)

    fieldsets = (
        (
            None,
            {
                "fields": ("name", "brand", "is_active"),
            },
        ),
        (
            "Pricing",
            {
                "fields": ("ptr", "pts", "mrp"),
                "description": "PTS is used for sales value calculation. "
                               "PTR and MRP are for reference only.",
            },
        ),
    )
