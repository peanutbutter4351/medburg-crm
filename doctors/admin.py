"""
Admin configuration for the doctors app.

Doctor is the central entity — Investment and DoctorMedicine are
managed as inlines so the admin can see everything on one page.
"""

from django.contrib import admin
from django.db.models import Sum, F
from django.utils.html import format_html

from .models import Doctor, Investment, DoctorMedicine


def _fmt_currency(value):
    """Safely format a numeric value as ₹X,XX,XXX.XX"""
    try:
        return "₹{:,.2f}".format(float(value))
    except (TypeError, ValueError):
        return "—"


# ──────────────────────────────────────────────
# Inlines
# ──────────────────────────────────────────────

class InvestmentInline(admin.TabularInline):
    """Investments shown inline on the Doctor change page."""

    model = Investment
    extra = 1
    fields = (
        "amount",
        "roi_ratio",
        "start_date",
        "get_roi_amount",
        "notes",
    )
    readonly_fields = ("get_roi_amount",)
    ordering = ("-start_date",)

    @admin.display(description="ROI Amount")
    def get_roi_amount(self, obj):
        if obj.pk:
            return _fmt_currency(obj.roi_amount)
        return "—"


class DoctorMedicineInline(admin.TabularInline):
    """Assigned medicines shown inline on the Doctor change page."""

    model = DoctorMedicine
    extra = 1
    autocomplete_fields = ("medicine",)


# ──────────────────────────────────────────────
# Doctor Admin
# ──────────────────────────────────────────────

@admin.register(Doctor)
class DoctorAdmin(admin.ModelAdmin):
    """
    Central admin view — acts as the primary dashboard.

    Shows doctor profile, inline investments & medicine mappings,
    plus computed ROI columns in the list view.
    """

    list_display = (
        "name",
        "hospital",
        "location",
        "mode",
        "doctor_type",
        "assigned_rep",
        "get_total_investment",
        "get_total_roi_amount",
        "get_achieved_roi",
        "get_balance_roi",
        "get_status_badge",
        "is_active",
    )
    list_filter = ("mode", "doctor_type", "is_active", "location")
    search_fields = ("name", "hospital", "location", "assigned_rep__username")
    list_per_page = 25
    autocomplete_fields = ("assigned_rep",)
    inlines = [InvestmentInline, DoctorMedicineInline]

    fieldsets = (
        (
            "Doctor Profile",
            {
                "fields": ("name", "hospital", "location"),
            },
        ),
        (
            "Classification",
            {
                "fields": ("mode", "doctor_type", "is_active"),
            },
        ),
        (
            "Assignment",
            {
                "fields": ("assigned_rep",),
            },
        ),
    )

    # ── Computed columns ─────────────────────────────

    @admin.display(description="Investment", ordering="total_investment")
    def get_total_investment(self, obj):
        total = getattr(obj, "total_investment", None)
        if total is None:
            total = obj.investments.aggregate(t=Sum("amount"))["t"]
        if not total:
            return "—"
        return _fmt_currency(total)

    @admin.display(description="ROI Amount")
    def get_total_roi_amount(self, obj):
        rows = obj.investments.all()
        total = sum(float(inv.roi_amount) for inv in rows)
        if not total:
            return "—"
        return _fmt_currency(total)

    @admin.display(description="Achieved ROI")
    def get_achieved_roi(self, obj):
        achieved = obj.sales_entries.aggregate(
            total=Sum(F("quantity") * F("medicine__ptr"))
        )["total"]
        if not achieved:
            return "₹0.00"
        return _fmt_currency(achieved)

    @admin.display(description="Balance ROI")
    def get_balance_roi(self, obj):
        roi_amount = sum(float(inv.roi_amount) for inv in obj.investments.all())
        achieved = obj.sales_entries.aggregate(
            total=Sum(F("quantity") * F("medicine__ptr"))
        )["total"]
        achieved = float(achieved) if achieved else 0.0
        balance = roi_amount - achieved
        if roi_amount == 0:
            return "—"
        color = "#28a745" if balance <= 0 else "#dc3545"
        formatted = _fmt_currency(balance)
        return format_html(
            '<span style="color:{}; font-weight:600;">{}</span>',
            color,
            formatted,
        )

    @admin.display(description="Status")
    def get_status_badge(self, obj):
        if obj.mode == "postpaid":
            return format_html(
                '<span style="background:#6c757d; color:#fff; '
                'padding:2px 8px; border-radius:4px; font-size:11px;">'
                "Postpaid</span>"
            )
        roi_amount = sum(float(inv.roi_amount) for inv in obj.investments.all())
        achieved = obj.sales_entries.aggregate(
            total=Sum(F("quantity") * F("medicine__ptr"))
        )["total"]
        achieved = float(achieved) if achieved else 0.0

        if roi_amount == 0:
            label, bg = "No Investment", "#ffc107"
        elif achieved >= roi_amount:
            label, bg = "Completed", "#28a745"
        elif achieved > 0:
            label, bg = "In Progress", "#17a2b8"
        else:
            label, bg = "Pending", "#dc3545"

        return format_html(
            '<span style="background:{}; color:#fff; '
            'padding:2px 8px; border-radius:4px; font-size:11px;">'
            "{}</span>",
            bg,
            label,
        )

    def get_queryset(self, request):
        """Annotate total investment for sorting."""
        qs = super().get_queryset(request)
        return qs.annotate(total_investment=Sum("investments__amount"))


# ──────────────────────────────────────────────
# Investment standalone (optional secondary view)
# ──────────────────────────────────────────────

@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    """Standalone list of all investments across doctors."""

    list_display = (
        "doctor",
        "amount",
        "roi_ratio",
        "get_roi_amount",
        "start_date",
        "created_at",
    )
    list_filter = ("start_date", "doctor__mode")
    search_fields = ("doctor__name",)
    autocomplete_fields = ("doctor",)
    list_per_page = 25
    date_hierarchy = "start_date"

    @admin.display(description="ROI Amount")
    def get_roi_amount(self, obj):
        return _fmt_currency(obj.roi_amount)


# ──────────────────────────────────────────────
# DoctorMedicine standalone (optional secondary view)
# ──────────────────────────────────────────────

@admin.register(DoctorMedicine)
class DoctorMedicineAdmin(admin.ModelAdmin):
    """Standalone view of all doctor ↔ medicine mappings."""

    list_display = ("doctor", "medicine", "created_at")
    list_filter = ("doctor__mode", "doctor__doctor_type")
    search_fields = ("doctor__name", "medicine__name")
    autocomplete_fields = ("doctor", "medicine")
    list_per_page = 30
