"""
Admin configuration for the sales app.
"""

from django.contrib import admin
from django.db.models import Sum, F

from .models import SalesEntry, PostpaidEntry


@admin.register(SalesEntry)
class SalesEntryAdmin(admin.ModelAdmin):
    """
    Sales entry management.

    Shows the computed value (quantity × PTR) as a read-only column.
    Reps cannot edit entries once submitted — controlled via
    has_change_permission for non-admin users.
    """

    list_display = (
        "entry_date",
        "doctor",
        "medicine",
        "rep",
        "quantity",
        "get_ptr",
        "get_value",
        "created_at",
    )
    list_filter = (
        "entry_date",
        "doctor__mode",
        "doctor__doctor_type",
        "rep",
    )
    search_fields = (
        "doctor__name",
        "medicine__name",
        "rep__username",
        "rep__first_name",
    )
    autocomplete_fields = ("rep", "doctor", "medicine")
    list_per_page = 30
    date_hierarchy = "entry_date"
    ordering = ("-entry_date", "-created_at")

    fieldsets = (
        (
            None,
            {
                "fields": ("rep", "doctor", "medicine", "quantity", "entry_date"),
            },
        ),
        (
            "Notes",
            {
                "fields": ("notes",),
                "classes": ("collapse",),
            },
        ),
    )

    # ── computed columns ─────────────────────────────

    @admin.display(description="PTR (₹)")
    def get_ptr(self, obj):
        return f"₹{obj.medicine.ptr:,.2f}"

    @admin.display(description="Value (₹)")
    def get_value(self, obj):
        return f"₹{obj.value:,.2f}"

    # ── permissions: reps cannot edit submitted entries ──

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if hasattr(request.user, "is_admin_user") and request.user.is_admin_user:
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if hasattr(request.user, "is_admin_user") and request.user.is_admin_user:
            return True
        return False


@admin.register(PostpaidEntry)
class PostpaidEntryAdmin(admin.ModelAdmin):
    """
    Postpaid entry management.

    Tracks ROI payments for doctors in postpaid mode.
    Amount is auto-computed from scoped SalesEntry data on save.
    """

    list_display = (
        "doctor",
        "medicine",
        "payout_type",
        "get_scope",
        "roi_percentage",
        "get_amount",
        "is_paid",
        "payment_date",
        "created_at",
    )
    list_filter = (
        "is_paid",
        "payout_type",
        "payment_date",
        "doctor__mode",
    )
    search_fields = (
        "doctor__name",
        "medicine__name",
        "remarks",
    )
    autocomplete_fields = ("doctor", "medicine")
    list_per_page = 30
    list_editable = ("is_paid",)
    readonly_fields = ("amount",)

    fieldsets = (
        (
            None,
            {
                "fields": ("doctor", "medicine", "roi_percentage"),
            },
        ),
        (
            "Payout Scope",
            {
                "fields": (
                    "payout_type",
                    "start_date",
                    "end_date",
                    "payout_month",
                    "payout_year",
                ),
                "description": (
                    "Choose the scope for amount calculation. "
                    "<strong>Range</strong> requires start/end dates. "
                    "<strong>Monthly</strong> requires month and year. "
                    "<strong>Campaign</strong> uses all sales data."
                ),
            },
        ),
        (
            "Calculated Amount",
            {
                "fields": ("amount",),
                "description": "Auto-computed on save from scoped sales × ROI%.",
            },
        ),
        (
            "Payment",
            {
                "fields": ("is_paid", "payment_date"),
            },
        ),
        (
            "Remarks",
            {
                "fields": ("remarks",),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Amount (₹)")
    def get_amount(self, obj):
        return f"₹{obj.amount:,.2f}"

    @admin.display(description="Scope")
    def get_scope(self, obj):
        return obj.scope_display


