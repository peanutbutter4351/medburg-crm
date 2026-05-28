"""
Admin configuration for the doctors app.

Doctor is the central entity — Investment and DoctorMedicine are
managed as inlines so the admin can see everything on one page.

Phase R1-A additions
────────────────────
• Completed investments are readonly for non-superusers.
• Delete protection blocks dangerous deletes on Doctor/Investment.
• InvestmentAdmin shows balance, status, and remaining ROI.
"""

from decimal import Decimal

from django.contrib import admin, messages
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils.html import format_html

from core.admin_mixins import ExcelImportAdminMixin
from .importers.doctor_importer import DoctorImporter
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
    """
    Investments shown inline on the Doctor change page.

    Protection rules (R1-A):
    - Completed investments are fully readonly for non-superusers.
    - Superusers can edit everything.
    """

    model = Investment
    extra = 1
    fields = (
        "amount",
        "roi_ratio",
        "start_date",
        "status",
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

    def get_readonly_fields(self, request, obj=None):
        """
        Make all investment fields readonly for non-superusers when the
        investment is completed.  Superusers can always edit.
        """
        base = list(self.readonly_fields)
        return base

    def get_formset(self, request, obj=None, **kwargs):
        """
        We need per-instance readonly logic; we patch the formset so that
        the fields of completed-investment rows are disabled for non-superusers.
        This is the safest approach when the protected object is an inline row.
        """
        formset = super().get_formset(request, obj, **kwargs)
        if request.user.is_superuser:
            return formset

        # Patch: mark the formset class so the template/view knows to lock
        # completed rows.  We achieve this by overriding full_clean at the
        # form level inside the formset.
        original_init = formset.__init__

        def patched_init(self_fs, *args, **kwargs_fs):
            original_init(self_fs, *args, **kwargs_fs)
            for form in self_fs.forms:
                instance = getattr(form, "instance", None)
                if instance and instance.pk and instance.status == Investment.STATUS_COMPLETED:
                    for field in form.fields.values():
                        field.disabled = True

        formset.__init__ = patched_init
        return formset


class DoctorMedicineInline(admin.TabularInline):
    """Assigned medicines shown inline on the Doctor change page."""

    model = DoctorMedicine
    extra = 1
    autocomplete_fields = ("medicine",)


# ──────────────────────────────────────────────
# Doctor Admin
# ──────────────────────────────────────────────

@admin.register(Doctor)
class DoctorAdmin(ExcelImportAdminMixin, admin.ModelAdmin):
    """
    Central admin view — acts as the primary dashboard.

    Shows doctor profile, inline investments & medicine mappings,
    plus computed ROI columns in the list view.

    Delete protection (R1-A):
    - Doctors linked to investments or sales entries cannot be deleted.
    """

    importer_class = DoctorImporter

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
        """
        Total sales value achieved against this doctor's investments.
        ARCH-2A: Uses Sum('value_at_sale') — the frozen snapshot field.
        """
        from django.db.models import Sum
        achieved = obj.sales_entries.aggregate(
            total=Coalesce(Sum("value_at_sale"), Decimal("0"), output_field=models.DecimalField())
        )["total"]
        if not achieved:
            return "₹0.00"
        return _fmt_currency(achieved)

    @admin.display(description="Balance ROI")
    def get_balance_roi(self, obj):
        """
        Balance = total_roi_amount − achieved_roi (snapshot-based).
        ARCH-2A: Uses Sum('value_at_sale') — never live medicine.pts.
        """
        from django.db.models import Sum
        roi_amount = sum(float(inv.roi_amount) for inv in obj.investments.all())
        achieved = obj.sales_entries.aggregate(
            total=Coalesce(Sum("value_at_sale"), Decimal("0"), output_field=models.DecimalField())
        )["total"]
        achieved = float(achieved)
        balance = roi_amount - achieved
        if roi_amount == 0:
            return "—"
        color = "#28a745" if balance <= 0 else "#dc3545"
        return format_html(
            '<span style="color:{}; font-weight:600;">{}</span>',
            color,
            _fmt_currency(balance),
        )

    @admin.display(description="Status")
    def get_status_badge(self, obj):
        """
        Status badge derived from snapshot-based balance.
        ARCH-2A: Aggregates value_at_sale instead of live medicine.pts.
        """
        from django.db.models import Sum
        if obj.mode == "postpaid":
            return format_html(
                '<span style="background:#6c757d; color:#fff; '
                'padding:2px 8px; border-radius:4px; font-size:11px;">'
                "Postpaid</span>"
            )
        roi_amount = sum(float(inv.roi_amount) for inv in obj.investments.all())
        achieved = obj.sales_entries.aggregate(
            total=Coalesce(Sum("value_at_sale"), Decimal("0"), output_field=models.DecimalField())
        )["total"]
        achieved = float(achieved)

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
        """
        Annotate total investment for ordering and prefetch related sets
        to eliminate N+1 queries in the computed columns.
        """
        qs = super().get_queryset(request)
        return (
            qs
            .prefetch_related("investments", "sales_entries")
            .annotate(total_investment=Sum("investments__amount"))
        )

    # ── Delete protection (R1-A) ──────────────────────

    def delete_model(self, request, obj):
        """Block deletion if doctor has investments or sales entries."""
        if obj.investments.exists():
            messages.set_level(request, messages.ERROR)
            self.message_user(
                request,
                f'Cannot delete "{obj.name}": doctor has linked investments. '
                "Remove all investments first.",
                level=messages.ERROR,
            )
            return
        if obj.sales_entries.exists():
            messages.set_level(request, messages.ERROR)
            self.message_user(
                request,
                f'Cannot delete "{obj.name}": doctor has linked sales entries.',
                level=messages.ERROR,
            )
            return
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Block bulk deletion if any doctor has investments or sales."""
        protected = []
        safe = []
        for doctor in queryset:
            if doctor.investments.exists() or doctor.sales_entries.exists():
                protected.append(doctor.name)
            else:
                safe.append(doctor)

        if protected:
            self.message_user(
                request,
                f"Blocked deletion of {len(protected)} doctor(s) with linked data: "
                + ", ".join(protected),
                level=messages.ERROR,
            )
        if safe:
            for doctor in safe:
                doctor.delete()
            self.message_user(
                request,
                f"Deleted {len(safe)} doctor(s) successfully.",
            )


# ──────────────────────────────────────────────
# Investment Admin (R1-A enhanced)
# ──────────────────────────────────────────────

@admin.register(Investment)
class InvestmentAdmin(admin.ModelAdmin):
    """
    Standalone list of all investments across doctors.

    R1-A enhancements:
    - Status filter and badge display.
    - Computed balance and remaining ROI columns.
    - Completed investments are readonly for non-superusers.
    - Delete protection for investments linked to sales entries.
    """

    list_display = (
        "doctor",
        "amount",
        "roi_ratio",
        "get_roi_amount",
        "get_balance_display",
        "get_remaining_roi",
        "start_date",
        "get_status_badge",
        "created_at",
    )
    list_filter = ("status", "start_date", "doctor__mode")
    search_fields = ("doctor__name",)
    autocomplete_fields = ("doctor",)
    list_per_page = 25
    date_hierarchy = "start_date"

    fieldsets = (
        (
            "Investment Details",
            {
                "fields": ("doctor", "amount", "roi_ratio", "start_date", "status"),
            },
        ),
        (
            "Computed (read-only)",
            {
                "fields": ("get_roi_amount_field", "get_balance_field"),
                "description": "Automatically calculated. Cannot be edited.",
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
    readonly_fields = ("get_roi_amount_field", "get_balance_field")

    # ── Computed display methods ──────────────────────

    @admin.display(description="ROI Amount")
    def get_roi_amount(self, obj):
        return _fmt_currency(obj.roi_amount)

    @admin.display(description="ROI Amount (₹)")
    def get_roi_amount_field(self, obj):
        if obj.pk:
            return _fmt_currency(obj.roi_amount)
        return "—"

    @admin.display(description="Balance (₹)")
    def get_balance_field(self, obj):
        if obj.pk:
            val = obj.balance
            color = "#28a745" if val <= 0 else "#dc3545"
            return format_html(
                '<span style="color:{}; font-weight:600;">{}</span>',
                color,
                _fmt_currency(val),
            )
        return "—"

    @admin.display(description="Balance")
    def get_balance_display(self, obj):
        val = obj.balance
        color = "#28a745" if val <= 0 else "#dc3545"
        return format_html(
            '<span style="color:{}; font-weight:600;">{}</span>',
            color,
            _fmt_currency(val),
        )

    @admin.display(description="Remaining ROI")
    def get_remaining_roi(self, obj):
        """Remaining = balance clamped for display (shows overshoot as negative)."""
        val = obj.balance
        if val <= 0:
            return format_html(
                '<span style="color:#28a745; font-weight:600;">✓ Achieved</span>'
            )
        return _fmt_currency(val)

    @admin.display(description="Status")
    def get_status_badge(self, obj):
        if obj.status == Investment.STATUS_COMPLETED:
            return format_html(
                '<span style="background:#28a745; color:#fff; '
                'padding:2px 8px; border-radius:4px; font-size:11px;">Completed</span>'
            )
        return format_html(
            '<span style="background:#17a2b8; color:#fff; '
            'padding:2px 8px; border-radius:4px; font-size:11px;">In Progress</span>'
        )

    # ── Completed investment protection (R1-A) ────────

    _PROTECTED_FIELDS = ("amount", "roi_ratio", "start_date", "status", "doctor", "notes")

    def get_readonly_fields(self, request, obj=None):
        """
        Non-superusers cannot edit any meaningful field on a completed investment.
        Superusers retain full edit access for corrections.
        """
        base = list(self.readonly_fields)
        if obj and obj.pk and obj.status == Investment.STATUS_COMPLETED:
            if not request.user.is_superuser:
                base = list(set(base) | set(self._PROTECTED_FIELDS))
        return base

    def has_change_permission(self, request, obj=None):
        """
        Non-superusers can VIEW completed investments but the form renders
        readonly (enforced by get_readonly_fields above).
        We still return True so the detail page is accessible.
        """
        return True

    def get_queryset(self, request):
        """select_related on doctor prevents N+1 in list-view columns."""
        return super().get_queryset(request).select_related("doctor")

    # ── Delete protection (R1-A) ──────────────────────

    def delete_model(self, request, obj):
        if obj.status == Investment.STATUS_COMPLETED:
            if not request.user.is_superuser:
                self.message_user(
                    request,
                    f'Cannot delete completed investment for "{obj.doctor.name}". '
                    "Only superusers may delete completed investments.",
                    level=messages.ERROR,
                )
                return
        if obj.sales_entries.exists():
            self.message_user(
                request,
                f'Cannot delete investment for "{obj.doctor.name}": '
                f"{obj.sales_entries.count()} linked sales entr(ies) exist. "
                "Remove all linked sales entries first.",
                level=messages.ERROR,
            )
            return
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        """Block bulk-deletion for completed or sales-linked investments."""
        protected = []
        safe = []
        for inv in queryset:
            blocked = False
            if inv.status == Investment.STATUS_COMPLETED and not request.user.is_superuser:
                protected.append(f"{inv.doctor.name} (completed)")
                blocked = True
            elif inv.sales_entries.exists():
                protected.append(f"{inv.doctor.name} (has sales)")
                blocked = True
            if not blocked:
                safe.append(inv)

        if protected:
            self.message_user(
                request,
                f"Blocked deletion of {len(protected)} investment(s): "
                + ", ".join(protected),
                level=messages.ERROR,
            )
        if safe:
            for inv in safe:
                inv.delete()
            self.message_user(
                request,
                f"Deleted {len(safe)} investment(s) successfully.",
            )


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
