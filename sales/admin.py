"""
Admin configuration for the sales app.

Phase R1-A additions
────────────────────
• SalesEntry admin now shows linked investment and its status.
• Computed value column (quantity × PTS) displayed readonly.
• Delete protection blocks removal of sales entries (only superusers allowed).
• Medicine admin gains delete protection for medicines with linked sales.
"""

from django.contrib import admin, messages
from django.db.models import Sum, F
from django.utils.html import format_html

from .models import SalesEntry, PostpaidEntry


def _fmt_currency(value):
    try:
        return "₹{:,.2f}".format(float(value))
    except (TypeError, ValueError):
        return "—"


@admin.register(SalesEntry)
class SalesEntryAdmin(admin.ModelAdmin):
    """
    Sales entry management.

    R1-A additions:
    - investment column and status badge in list view.
    - Computed value readonly field in detail form.
    - Useful filters: investment status, doctor mode, rep, date.
    - Delete restricted to superusers.
    """

    list_display = (
        "entry_date",
        "doctor",
        "get_investment_label",
        "get_investment_status",
        "medicine",
        "rep",
        "quantity",
        "get_pts",
        "get_value",
        "created_at",
    )
    list_filter = (
        "entry_date",
        "investment__status",
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
    autocomplete_fields = ("rep", "doctor", "medicine", "investment")
    list_per_page = 30
    date_hierarchy = "entry_date"
    ordering = ("-entry_date", "-created_at")

    fieldsets = (
        (
            None,
            {
                "fields": ("rep", "doctor", "investment", "medicine", "quantity", "entry_date"),
            },
        ),
        (
            "Computed",
            {
                "fields": ("get_computed_value",),
                "description": "Auto-calculated from quantity × PTS. Cannot be edited.",
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
    readonly_fields = ("get_computed_value",)

    # ── Computed columns ─────────────────────────────

    @admin.display(description="Investment")
    def get_investment_label(self, obj):
        if obj.investment_id:
            return str(obj.investment)
        return format_html('<span style="color:#6c757d;">—</span>')

    @admin.display(description="Inv. Status")
    def get_investment_status(self, obj):
        if not obj.investment_id:
            return "—"
        if obj.investment.status == "completed":
            return format_html(
                '<span style="background:#28a745; color:#fff; '
                'padding:2px 6px; border-radius:4px; font-size:11px;">Completed</span>'
            )
        return format_html(
            '<span style="background:#17a2b8; color:#fff; '
            'padding:2px 6px; border-radius:4px; font-size:11px;">In Progress</span>'
        )

    @admin.display(description="PTS (₹)")
    def get_pts(self, obj):
        return f"₹{obj.medicine.pts:,.2f}"

    @admin.display(description="Value (₹)")
    def get_value(self, obj):
        return f"₹{obj.value:,.2f}"

    @admin.display(description="Computed Value (₹)")
    def get_computed_value(self, obj):
        if obj.pk:
            return format_html(
                '<strong style="font-size:1.05em;">{}</strong>',
                f"₹{obj.value:,.2f}",
            )
        return "—"

    # ── Permissions ───────────────────────────────────

    def has_change_permission(self, request, obj=None):
        if request.user.is_superuser:
            return True
        if hasattr(request.user, "is_admin_user") and request.user.is_admin_user:
            return True
        return False

    def has_delete_permission(self, request, obj=None):
        """Only superusers may delete sales entries."""
        return request.user.is_superuser

    def delete_model(self, request, obj):
        if not request.user.is_superuser:
            self.message_user(
                request,
                "Only superusers may delete sales entries.",
                level=messages.ERROR,
            )
            return
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        if not request.user.is_superuser:
            self.message_user(
                request,
                "Only superusers may delete sales entries.",
                level=messages.ERROR,
            )
            return
        super().delete_queryset(request, queryset)

    # ── select_related for N+1 prevention ────────────

    def get_queryset(self, request):
        return (
            super().get_queryset(request)
            .select_related("doctor", "medicine", "rep", "investment")
        )


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

    def save_model(self, request, obj, form, change):
        """
        Auto-sync paid_amount when payment_status is changed via admin.

        If an admin sets status to 'paid' in the detail form, we
        automatically set paid_amount = amount to keep them consistent.
        This prevents the data inconsistency where status='paid' but
        paid_amount is still 0.
        """
        from core.constants import PAYMENT_STATUS_PAID, PAYMENT_STATUS_UNPAID

        if change and "payment_status" in form.changed_data:
            if obj.payment_status == PAYMENT_STATUS_PAID:
                obj.paid_amount = obj.amount
                if not obj.payment_date:
                    from datetime import date
                    obj.payment_date = date.today()
            elif obj.payment_status == PAYMENT_STATUS_UNPAID:
                obj.paid_amount = 0
                obj.payment_date = None

        super().save_model(request, obj, form, change)

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
