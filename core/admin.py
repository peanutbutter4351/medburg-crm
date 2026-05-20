"""
core/admin.py
━━━━━━━━━━━━━
Django admin registrations for the core app.
"""

from django.contrib import admin
from django.utils.html import format_html

from core.models import ImportLog


@admin.register(ImportLog)
class ImportLogAdmin(admin.ModelAdmin):
    """
    Admin interface for import audit logs.

    Read-only by design — import logs are system-generated records
    and should never be manually edited.
    """

    # ── List view ─────────────────────────────────────────────────────────────

    list_display = (
        "file_name",
        "import_type",
        "status_badge",
        "total_rows",
        "success_rows",
        "failed_rows",
        "created_at",
    )
    list_filter  = ("import_type", "status", "created_at")
    search_fields = ("file_name",)
    date_hierarchy = "created_at"
    ordering = ("-created_at",)

    # ── Detail view ───────────────────────────────────────────────────────────

    readonly_fields = (
        "import_type",
        "file_name",
        "status",
        "total_rows",
        "success_rows",
        "failed_rows",
        "skipped_rows_display",
        "error_log",
        "created_at",
        "updated_at",
    )

    fieldsets = (
        ("Job", {
            "fields": ("import_type", "file_name", "status", "created_at", "updated_at"),
        }),
        ("Row Counts", {
            "fields": ("total_rows", "success_rows", "failed_rows", "skipped_rows_display"),
        }),
        ("Error Detail", {
            "fields": ("error_log",),
            "classes": ("collapse",),
            "description": (
                "Populated from ImportResult.summary() and per-row RowError strings. "
                "Expand to see per-row validation failures."
            ),
        }),
    )

    # ── Computed columns ──────────────────────────────────────────────────────

    @admin.display(description="Status")
    def status_badge(self, obj: ImportLog) -> str:
        """Colour-coded status chip in the list view."""
        colours = {
            ImportLog.STATUS_SUCCESS: "#2e7d32",   # green
            ImportLog.STATUS_PARTIAL: "#e65100",   # amber
            ImportLog.STATUS_FAILED:  "#c62828",   # red
            ImportLog.STATUS_PENDING: "#37474f",   # grey
        }
        colour = colours.get(obj.status, "#37474f")
        return format_html(
            '<span style="'
            "background:{colour};"
            "color:#fff;"
            "padding:2px 8px;"
            "border-radius:4px;"
            "font-size:0.8em;"
            "font-weight:600;"
            '">{label}</span>',
            colour=colour,
            label=obj.get_status_display(),
        )

    @admin.display(description="Skipped rows")
    def skipped_rows_display(self, obj: ImportLog) -> int:
        return obj.skipped_rows

    # ── Disable all write operations ──────────────────────────────────────────

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        # Superusers may purge old logs; staff cannot.
        return request.user.is_superuser
