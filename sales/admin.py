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
        "get_total_sales",
        "get_amount",
        "get_paid_amount",
        "get_balance",
        "payment_status",
        "payment_date",
        "created_at",
    )
    list_filter = (
        "payment_status",
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
    list_editable = ("payment_status",)
    readonly_fields = ("amount", "total_sales_value", "get_balance_display")
    actions = ["recalculate_amounts", "mark_fully_paid"]

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
                "fields": ("total_sales_value", "amount"),
                "description": (
                    "Auto-computed on creation from scoped sales × ROI%. "
                    "Frozen after first save. Use the 'Recalculate amount' "
                    "action to refresh."
                ),
            },
        ),
        (
            "Payment",
            {
                "fields": (
                    "payment_status",
                    "paid_amount",
                    "get_balance_display",
                    "payment_date",
                ),
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

    @admin.display(description="Paid (₹)")
    def get_paid_amount(self, obj):
        return f"₹{obj.paid_amount:,.2f}"

    @admin.display(description="Balance (₹)")
    def get_balance(self, obj):
        return f"₹{obj.balance_amount:,.2f}"

    @admin.display(description="Balance")
    def get_balance_display(self, obj):
        """Read-only balance field for the detail form."""
        return f"₹{obj.balance_amount:,.2f}"

    @admin.display(description="Sales Total (₹)")
    def get_total_sales(self, obj):
        return f"₹{obj.total_sales_value:,.2f}"

    @admin.display(description="Scope")
    def get_scope(self, obj):
        return obj.scope_display

    @admin.action(description="Recalculate amount from current sales data")
    def recalculate_amounts(self, request, queryset):
        """Admin action to explicitly recompute amounts."""
        count = 0
        for entry in queryset:
            entry.recalculate_amount()
            count += 1
        self.message_user(
            request,
            f"Recalculated {count} entr{'y' if count == 1 else 'ies'}.",
        )

    @admin.action(description="Mark selected entries as fully paid")
    def mark_fully_paid(self, request, queryset):
        """Admin action to mark entries as fully paid."""
        from datetime import date
        from core.constants import PAYMENT_STATUS_PAID

        unpaid = queryset.exclude(payment_status=PAYMENT_STATUS_PAID)
        count = 0
        for entry in unpaid:
            PostpaidEntry.objects.filter(pk=entry.pk).update(
                payment_status=PAYMENT_STATUS_PAID,
                paid_amount=entry.amount,
                payment_date=date.today(),
            )
            count += 1
        self.message_user(
            request,
            f"Marked {count} entr{'y' if count == 1 else 'ies'} as fully paid.",
        )


