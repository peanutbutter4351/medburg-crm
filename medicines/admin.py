"""
Admin configuration for the medicines app.
"""

from django.contrib import admin

from .models import Medicine


@admin.register(Medicine)
class MedicineAdmin(admin.ModelAdmin):
    """Medicine catalogue management."""

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
                "description": "PTR is used for sales value calculation. "
                               "PTS and MRP are for reference only.",
            },
        ),
    )
