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

from .models import SalesEntry, PostpaidCampaign, PostpaidSaleEntry, CampaignPayment, PostpaidCampaignCorrection


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

    ARCH-3B (W-1) hardening:
    - After creation, non-superusers cannot change: doctor, medicine,
      quantity, investment, rep, entry_date.
    - Snapshots are immutable at model level (editable=False);
      locking source fields prevents quantity/snapshot divergence.
    - Superusers retain full edit access for corrections.
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

    # Fields locked after creation for non-superusers (ARCH-3B W-1)
    _POST_CREATION_LOCKED = ("rep", "doctor", "investment", "medicine", "quantity", "entry_date")

    def get_readonly_fields(self, request, obj=None):
        """
        After an entry is saved (obj.pk exists), lock the source fields for
        non-superusers to prevent quantity/snapshot divergence.

        Superusers can still edit all fields for supervised corrections.
        During creation (obj is None) nothing extra is locked.
        """
        base = list(self.readonly_fields)
        if obj and obj.pk and not request.user.is_superuser:
            base = list(set(base) | set(self._POST_CREATION_LOCKED))
        return base

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

    @admin.display(description="PTS at Sale (₹)")
    def get_pts(self, obj):
        """
        Show the snapshotted PTS if available, otherwise show live PTS
        with a legacy marker to make the distinction clear in the admin.
        """
        if obj.pts_at_sale is not None:
            return f"₹{obj.pts_at_sale:,.2f}"
        # Fallback for pre-backfill rows (should only appear transiently)
        return format_html(
            '₹{} <span style="color:#e65100; font-size:10px;" title="Snapshot not yet available"'
            '>⚠ live</span>',
            f"{obj.medicine.pts:,.2f}",
        )

    @admin.display(description="Value at Sale (₹)")
    def get_value(self, obj):
        """
        Show the frozen value_at_sale snapshot.
        Falls back to live calculation with a legacy marker for pre-backfill rows.
        """
        if obj.value_at_sale is not None:
            marker = (
                format_html(
                    ' <span style="color:#e65100; font-size:10px;" '
                    'title="Best-effort backfill (ARCH-2A legacy)">· legacy</span>'
                )
                if obj.is_snapshot_legacy else ""
            )
            return format_html("₹{}{}", f"{obj.value_at_sale:,.2f}", marker)
        return format_html(
            '₹{} <span style="color:#e65100; font-size:10px;" title="No snapshot yet">'
            '⚠ live</span>',
            f"{obj.value:,.2f}",
        )

    @admin.display(description="Value (₹)")
    def get_computed_value(self, obj):
        """Read-only value field shown on the detail form."""
        if obj.pk:
            if obj.value_at_sale is not None:
                label = "Snapshot (frozen)" if not obj.is_snapshot_legacy else "Snapshot (legacy backfill)"
                return format_html(
                    '<strong style="font-size:1.05em;">{}</strong> '
                    '<span style="color:#6c757d; font-size:11px;">— {}</span>',
                    f"₹{obj.value_at_sale:,.2f}",
                    label,
                )
            return format_html(
                '<strong style="font-size:1.05em; color:#e65100;">{}</strong> '
                '<span style="font-size:11px; color:#e65100;">⚠ live (no snapshot)</span>',
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




class CampaignCorrectionInline(admin.TabularInline):
    """
    Read-only inline showing corrections applied to a campaign.
    Displayed on the PostpaidCampaign change view.
    """
    model = PostpaidCampaignCorrection
    extra = 0
    can_delete = False
    show_change_link = True
    readonly_fields = (
        "corrected_at",
        "corrected_by",
        "correction_reason",
        "amount_adjustment",
        "notes",
        "reference",
        "snapshot_total_commission",
        "snapshot_paid_amount",
        "snapshot_outstanding_balance",
    )
    fields = readonly_fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PostpaidCampaign)
class PostpaidCampaignAdmin(admin.ModelAdmin):
    list_display = (
        "doctor",
        "month",
        "year",
        "commission_percentage",
        "get_total_sales",
        "get_total_commission",
        "get_paid_amount",
        "get_outstanding_balance",
        "status",
        "settled_at",
    )
    list_filter = ("status", "month", "year", "doctor")
    search_fields = ("doctor__name",)
    readonly_fields = ("total_sales_value", "total_commission", "paid_amount", "locked_at", "settled_at")
    inlines = [CampaignCorrectionInline]

    @admin.display(description="Total Sales")
    def get_total_sales(self, obj):
        return _fmt_currency(obj.total_sales_value)

    @admin.display(description="Total Commission")
    def get_total_commission(self, obj):
        return _fmt_currency(obj.total_commission)

    @admin.display(description="Paid Amount")
    def get_paid_amount(self, obj):
        return _fmt_currency(obj.paid_amount)

    @admin.display(description="Outstanding Balance")
    def get_outstanding_balance(self, obj):
        return _fmt_currency(obj.outstanding_balance)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def has_delete_permission(self, request, obj=None):
        if obj:
            if obj.status == PostpaidCampaign.STATUS_OPEN:
                return super().has_delete_permission(request, obj)
            return False
        return super().has_delete_permission(request, obj)


@admin.register(PostpaidSaleEntry)
class PostpaidSaleEntryAdmin(admin.ModelAdmin):
    list_display = (
        "entry_date",
        "campaign",
        "medicine",
        "quantity",
        "get_pts",
        "get_value",
        "rep",
    )
    list_filter = ("entry_date", "campaign__status", "rep", "medicine")
    search_fields = ("campaign__doctor__name", "medicine__name", "rep__username")
    readonly_fields = ("pts_at_sale", "value_at_sale", "commission_percentage_at_sale", "commission_at_sale")

    @admin.display(description="PTS at Sale")
    def get_pts(self, obj):
        return _fmt_currency(obj.pts_at_sale)

    @admin.display(description="Value at Sale")
    def get_value(self, obj):
        return _fmt_currency(obj.value_at_sale)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions

    def has_delete_permission(self, request, obj=None):
        if obj and obj.campaign.status in (
            PostpaidCampaign.STATUS_PARTIAL,
            PostpaidCampaign.STATUS_SETTLED,
            PostpaidCampaign.STATUS_LOCKED,
        ):
            return False
        return super().has_delete_permission(request, obj)


@admin.register(CampaignPayment)
class CampaignPaymentAdmin(admin.ModelAdmin):
    list_display = (
        "campaign",
        "get_amount",
        "payment_date",
        "reference",
    )
    list_filter = ("payment_date", "campaign__doctor")
    search_fields = ("campaign__doctor__name", "reference")

    @admin.display(description="Amount")
    def get_amount(self, obj):
        return _fmt_currency(obj.amount)

    def get_readonly_fields(self, request, obj=None):
        if obj:
            return [field.name for field in self.model._meta.fields]
        return self.readonly_fields

    def has_delete_permission(self, request, obj=None):
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions


@admin.register(PostpaidCampaignCorrection)
class PostpaidCampaignCorrectionAdmin(admin.ModelAdmin):
    """
    Read-only audit view for campaign corrections.

    MR-8.0: Corrections are append-only. No delete, no bulk-delete.
    New corrections may be created here for Settled or Locked campaigns.
    """

    list_display = (
        "campaign",
        "corrected_at",
        "corrected_by",
        "correction_reason",
        "get_adjustment",
        "reference",
        "created_at",
    )
    list_filter = (
        "correction_reason",
        "corrected_at",
        "campaign__status",
    )
    search_fields = (
        "campaign__doctor__name",
        "notes",
        "reference",
        "corrected_by__username",
    )
    readonly_fields = (
        "corrected_at",
        "snapshot_total_commission",
        "snapshot_paid_amount",
        "snapshot_outstanding_balance",
        "created_at",
        "updated_at",
    )
    autocomplete_fields = ("campaign",)
    date_hierarchy = "corrected_at"

    fieldsets = (
        (
            "Campaign",
            {
                "fields": ("campaign",),
            },
        ),
        (
            "Correction Details",
            {
                "fields": (
                    "correction_reason",
                    "amount_adjustment",
                    "notes",
                    "reference",
                ),
            },
        ),
        (
            "Authorisation",
            {
                "fields": ("corrected_by", "corrected_at"),
            },
        ),
        (
            "Campaign Snapshot at Correction Time",
            {
                "fields": (
                    "snapshot_total_commission",
                    "snapshot_paid_amount",
                    "snapshot_outstanding_balance",
                ),
                "description": (
                    "These values were frozen from the campaign at the moment this "
                    "correction was recorded. They cannot be changed."
                ),
            },
        ),
        (
            "System",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="Adjustment (\u20b9)")
    def get_adjustment(self, obj):
        sign = "+" if obj.amount_adjustment >= 0 else ""
        return f"{sign}\u20b9{obj.amount_adjustment:,.2f}"

    def save_model(self, request, obj, form, change):
        """Capture corrected_by from the logged-in admin on creation."""
        if not change and not obj.corrected_by_id:
            obj.corrected_by = request.user
        super().save_model(request, obj, form, change)

    def has_delete_permission(self, request, obj=None):
        """Corrections cannot be deleted from the admin."""
        return False

    def has_change_permission(self, request, obj=None):
        """Corrections cannot be edited after creation."""
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)
        if 'delete_selected' in actions:
            del actions['delete_selected']
        return actions
