"""
Admin configuration for the medicines app.

Phase R1-A additions
────────────────────
• Delete protection: medicines linked to sales entries cannot be deleted.
"""

from django.contrib import admin, messages

from core.admin_mixins import ExcelImportAdminMixin
from .importers import MedicineImporter
from .models import Medicine


@admin.register(Medicine)
class MedicineAdmin(ExcelImportAdminMixin, admin.ModelAdmin):
    """
    Medicine catalogue management.

    R1-A: Medicines with linked sales entries cannot be deleted.
    """

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
    list_editable = ("ptr", "mrp", "is_active")
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
                "description": (
                    "<strong style='color:#c62828;'>"
                    "⚠️ Note: "
                    "Changing PTS only affects NEW sales entries going forward. "
                    "All existing entries use the price at the time of their entry "
                    "and will NOT be recalculated."
                    "</strong><br>"
                    "PTR and MRP are for reference only."
                ),
            },
        ),
    )

    # ── Delete protection (R1-A) ──────────────────────

    def delete_model(self, request, obj):
        """Block deletion if any sales entry references this medicine."""
        # SalesEntry uses `medicine` FK with related_name='sales_entries'
        # on the Medicine model; we use the reverse manager via Django internals.
        from sales.models import SalesEntry
        if SalesEntry.objects.filter(medicine=obj).exists():
            self.message_user(
                request,
                f'Cannot delete medicine "{obj.name}": it is referenced by '
                "existing sales entries. Deactivate it instead.",
                level=messages.ERROR,
            )
            return
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Block bulk-deletion for medicines linked to sales."""
        from sales.models import SalesEntry
        linked_ids = (
            SalesEntry.objects
            .filter(medicine__in=queryset)
            .values_list("medicine_id", flat=True)
            .distinct()
        )
        protected = queryset.filter(pk__in=linked_ids)
        safe = queryset.exclude(pk__in=linked_ids)

        if protected.exists():
            names = ", ".join(protected.values_list("name", flat=True))
            self.message_user(
                request,
                f"Blocked deletion of {protected.count()} medicine(s) with linked "
                f"sales entries: {names}",
                level=messages.ERROR,
            )
        if safe.exists():
            count = safe.count()
            safe.delete()
            self.message_user(
                request,
                f"Deleted {count} medicine(s) successfully.",
            )
