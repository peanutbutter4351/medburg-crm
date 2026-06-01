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
from .models import Doctor, Investment, DoctorMedicine, PrepaidDoctor, PostpaidDoctor
from sales.models import PostpaidCampaign


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

    def has_module_permission(self, request):
        """Hide the base Doctor model from the admin sidebar navigation index."""
        return False

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

    @admin.display(description="Achieved ROI", ordering="achieved_roi")
    def get_achieved_roi(self, obj):
        """
        Reads the achieved_roi annotation injected by get_queryset().
        ARCH-3B: No per-row DB query — annotation pre-computed for the whole page.
        """
        val = getattr(obj, "achieved_roi", None)
        if not val:
            return "₹0.00"
        return _fmt_currency(val)

    @admin.display(description="Balance ROI", ordering="balance_roi")
    def get_balance_roi(self, obj):
        """
        Reads balance_roi annotation injected by get_queryset().
        ARCH-3B: No per-row DB query.
        """
        roi_amount = getattr(obj, "total_roi_amount_admin", None)
        if roi_amount is None:
            # Fallback for objects loaded outside the annotated queryset
            roi_amount = sum(float(inv.roi_amount) for inv in obj.investments.all())
        else:
            roi_amount = float(roi_amount)
        balance = getattr(obj, "balance_roi", None)
        if balance is None or roi_amount == 0:
            return "—"
        color = "#28a745" if float(balance) <= 0 else "#dc3545"
        return format_html(
            '<span style="color:{}; font-weight:600;">{}</span>',
            color,
            _fmt_currency(balance),
        )

    @admin.display(description="Status", ordering="roi_status")
    def get_status_badge(self, obj):
        """
        Reads roi_status annotation injected by get_queryset().
        ARCH-3B: No per-row DB query.
        """
        if obj.mode == "postpaid":
            return format_html(
                '<span style="background:#6c757d; color:#fff; '
                'padding:2px 8px; border-radius:4px; font-size:11px;">'
                "Postpaid</span>"
            )
        status = getattr(obj, "roi_status", None)
        BADGE = {
            "Completed":     ("#28a745", "Completed"),
            "In Progress":   ("#17a2b8", "In Progress"),
            "Pending":       ("#dc3545", "Pending"),
            "No Investment": ("#ffc107", "No Investment"),
        }
        bg, label = BADGE.get(status, ("#6c757d", status or "Unknown"))
        return format_html(
            '<span style="background:{}; color:{}; '
            'padding:2px 8px; border-radius:4px; font-size:11px;">'
            "{}</span>",
            bg,
            "#fff" if bg != "#ffc107" else "#212529",
            label,
        )

    def get_queryset(self, request):
        """
        Annotate all financial columns at the queryset level to eliminate
        N+1 queries from the computed display columns.

        ARCH-3B: Injects the same Subquery pattern as doctor_service.py:
          • total_investment      — active (in_progress) investment amount sum
          • total_roi_amount_admin — active ROI target sum
          • achieved_roi          — Sum(value_at_sale) for prepaid entries
          • balance_roi           — total_roi_amount_admin − achieved_roi
          • roi_status            — Completed / In Progress / Pending / No Investment

        Each annotation is one correlated Subquery — O(1) queries regardless
        of how many doctors appear on the page.
        """
        from django.db.models import (
            Case, CharField, F, IntegerField, OuterRef,
            Subquery, Value, When, DecimalField,
        )
        from doctors.models import Investment
        from sales.models import SalesEntry

        # Subquery: total active investment amount per doctor
        inv_amount_sq = (
            Investment.objects
            .filter(doctor_id=OuterRef("pk"), status=Investment.STATUS_IN_PROGRESS)
            .values("doctor_id")
            .annotate(t=Sum("amount"))
            .values("t")[:1]
        )

        # Subquery: total active ROI target per doctor
        inv_roi_sq = (
            Investment.objects
            .filter(doctor_id=OuterRef("pk"), status=Investment.STATUS_IN_PROGRESS)
            .values("doctor_id")
            .annotate(t=Sum(F("amount") * F("roi_ratio")))
            .values("t")[:1]
        )

        # Subquery: sum of value_at_sale (snapshot) per doctor for prepaid entries
        achieved_sq = (
            SalesEntry.objects
            .filter(doctor_id=OuterRef("pk"), investment__isnull=False)
            .values("doctor_id")
            .annotate(t=Sum("value_at_sale"))
            .values("t")[:1]
        )

        qs = (
            super().get_queryset(request)
            .annotate(
                total_investment=Coalesce(
                    Subquery(inv_amount_sq, output_field=DecimalField()),
                    Value(Decimal("0")), output_field=DecimalField(),
                ),
                total_roi_amount_admin=Coalesce(
                    Subquery(inv_roi_sq, output_field=DecimalField()),
                    Value(Decimal("0")), output_field=DecimalField(),
                ),
                achieved_roi=Coalesce(
                    Subquery(achieved_sq, output_field=DecimalField()),
                    Value(Decimal("0")), output_field=DecimalField(),
                ),
            )
            .annotate(
                balance_roi=F("total_roi_amount_admin") - F("achieved_roi"),
            )
            .annotate(
                roi_status=Case(
                    When(mode="postpaid", then=Value("Postpaid")),
                    When(total_roi_amount_admin=Decimal("0"), then=Value("No Investment")),
                    When(achieved_roi__gte=F("total_roi_amount_admin"), then=Value("Completed")),
                    When(achieved_roi__gt=Decimal("0"), then=Value("In Progress")),
                    default=Value("Pending"),
                    output_field=CharField(),
                ),
            )
        )
        return qs

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


class PostpaidCampaignInline(admin.TabularInline):
    model = PostpaidCampaign
    extra = 0
    fields = (
        "month",
        "year",
        "commission_percentage",
        "total_sales_value",
        "total_commission",
        "paid_amount",
        "status",
    )
    readonly_fields = ("total_sales_value", "total_commission", "paid_amount")
    ordering = ("-year", "-month")

    def has_add_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PrepaidDoctor)
class PrepaidDoctorAdmin(DoctorAdmin):
    """Admin configuration for Prepaid Doctors."""

    def has_module_permission(self, request):
        return admin.ModelAdmin.has_module_permission(self, request)

    def get_queryset(self, request):
        return super().get_queryset(request).filter(mode="prepaid")

    def save_model(self, request, obj, form, change):
        if not change:
            obj.mode = "prepaid"
        super().save_model(request, obj, form, change)


@admin.register(PostpaidDoctor)
class PostpaidDoctorAdmin(DoctorAdmin):
    """Admin configuration for Postpaid Doctors."""

    def has_module_permission(self, request):
        return admin.ModelAdmin.has_module_permission(self, request)

    list_display = (
        "name",
        "hospital",
        "location",
        "doctor_type",
        "assigned_rep",
        "get_active_campaigns_count",
        "is_active",
    )
    list_filter = ("doctor_type", "is_active", "location")
    inlines = [PostpaidCampaignInline, DoctorMedicineInline]

    def get_queryset(self, request):
        from django.db.models import Count, Q
        return (
            admin.ModelAdmin.get_queryset(self, request)
            .filter(mode="postpaid")
            .annotate(
                active_campaigns_count=Count(
                    "postpaid_campaigns",
                    filter=~Q(postpaid_campaigns__status="locked")
                )
            )
            .select_related("assigned_rep")
        )

    @admin.display(description="Active Campaigns")
    def get_active_campaigns_count(self, obj):
        return getattr(obj, "active_campaigns_count", 0)

    def save_model(self, request, obj, form, change):
        if not change:
            obj.mode = "postpaid"
        super().save_model(request, obj, form, change)


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
    # ARCH-3B (W-3): also lock financial fields once sales exist

    # Fields locked for completed investments (non-superusers)
    _PROTECTED_FIELDS = ("amount", "roi_ratio", "start_date", "status", "doctor", "notes")
    # Fields locked once any sales entry is linked (non-superusers)
    _FINANCIAL_FIELDS = ("amount", "roi_ratio")

    def get_readonly_fields(self, request, obj=None):
        """
        Two-tier readonly protection for non-superusers:

        Tier 1 (R1-A) — completed investments:
          All meaningful fields are readonly once status = completed.

        Tier 2 (ARCH-3B W-3) — investments with linked sales entries:
          amount and roi_ratio become readonly once any SalesEntry is linked.
          Changing these would retroactively alter roi_amount and therefore
          balance with no audit trail.

        Superusers retain full edit access for supervised corrections.
        """
        base = list(self.readonly_fields)
        if not obj or not obj.pk:
            return base
        if not request.user.is_superuser:
            # Tier 1: all fields locked for completed investments
            if obj.status == Investment.STATUS_COMPLETED:
                base = list(set(base) | set(self._PROTECTED_FIELDS))
            # Tier 2: financial fields locked once sales exist
            elif obj.sales_entries.exists():
                base = list(set(base) | set(self._FINANCIAL_FIELDS))
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

# @admin.register(DoctorMedicine)
class DoctorMedicineAdmin(admin.ModelAdmin):
    """Standalone view of all doctor ↔ medicine mappings."""

    list_display = ("doctor", "medicine", "created_at")
    list_filter = ("doctor__mode", "doctor__doctor_type")
    search_fields = ("doctor__name", "medicine__name")
    autocomplete_fields = ("doctor", "medicine")
    list_per_page = 30
