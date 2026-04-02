"""
Doctor service layer.

All heavy query logic lives here so views stay thin and templates
receive pre-computed data only.
"""

from decimal import Decimal

from django.db.models import (
    Sum, F, Value, Case, When, CharField,
    DecimalField, Q,
)
from django.db.models.functions import Coalesce

from doctors.models import Doctor


def get_dashboard_queryset(*, rep_id=None, location=None, status=None, search=None):
    """
    Return an annotated Doctor queryset with all ROI columns
    pre-computed at the database level.

    Annotations added
    ─────────────────
    total_investment  – Σ investments.amount
    total_roi_amount  – Σ (investments.amount × investments.roi_ratio)
    achieved_roi      – Σ (sales_entries.quantity × sales_entries.medicine.ptr)
    balance_roi       – total_roi_amount − achieved_roi
    roi_status        – Completed / In Progress / Pending / No Investment / Postpaid
    """

    qs = (
        Doctor.objects
        .filter(is_active=True)
        .select_related("assigned_rep")
        .annotate(
            total_investment=Coalesce(
                Sum("investments__amount", distinct=True),
                Value(Decimal("0")),
                output_field=DecimalField(),
            ),
            total_roi_amount=Coalesce(
                Sum(
                    F("investments__amount") * F("investments__roi_ratio"),
                    distinct=True,
                ),
                Value(Decimal("0")),
                output_field=DecimalField(),
            ),
            achieved_roi=Coalesce(
                Sum(
                    F("sales_entries__quantity") * F("sales_entries__medicine__ptr"),
                ),
                Value(Decimal("0")),
                output_field=DecimalField(),
            ),
        )
        .annotate(
            balance_roi=F("total_roi_amount") - F("achieved_roi"),
        )
        .annotate(
            roi_status=Case(
                When(mode="postpaid", then=Value("Postpaid")),
                When(total_roi_amount=Decimal("0"), then=Value("No Investment")),
                When(achieved_roi__gte=F("total_roi_amount"), then=Value("Completed")),
                When(achieved_roi__gt=Decimal("0"), then=Value("In Progress")),
                default=Value("Pending"),
                output_field=CharField(),
            ),
        )
        .order_by("name")
    )

    # ── Filters ──────────────────────────────────────
    if rep_id:
        qs = qs.filter(assigned_rep_id=rep_id)

    if location:
        qs = qs.filter(location__iexact=location)

    if search:
        qs = qs.filter(
            Q(name__icontains=search)
            | Q(hospital__icontains=search)
            | Q(location__icontains=search)
            | Q(assigned_rep__first_name__icontains=search)
            | Q(assigned_rep__last_name__icontains=search)
        )

    if status:
        qs = qs.filter(roi_status=status)

    return qs


def get_dashboard_summary(queryset):
    """
    Aggregate totals across the filtered queryset for the summary cards.
    """
    agg = queryset.aggregate(
        sum_investment=Coalesce(Sum("total_investment"), Value(Decimal("0"))),
        sum_roi_target=Coalesce(Sum("total_roi_amount"), Value(Decimal("0"))),
        sum_achieved=Coalesce(Sum("achieved_roi"), Value(Decimal("0"))),
        sum_balance=Coalesce(Sum("balance_roi"), Value(Decimal("0"))),
    )
    return {
        "total_doctors": queryset.count(),
        "total_investment": agg["sum_investment"],
        "total_roi_target": agg["sum_roi_target"],
        "total_achieved": agg["sum_achieved"],
        "total_balance": agg["sum_balance"],
    }


def get_filter_options():
    """
    Return distinct values for filter dropdowns.
    """
    from accounts.models import User
    from core.constants import ROLE_REP

    reps = (
        User.objects
        .filter(role=ROLE_REP, is_active=True)
        .order_by("first_name", "last_name")
        .values("id", "first_name", "last_name", "username")
    )

    locations = (
        Doctor.objects
        .filter(is_active=True)
        .exclude(location="")
        .values_list("location", flat=True)
        .distinct()
        .order_by("location")
    )

    statuses = [
        "Completed",
        "In Progress",
        "Pending",
        "No Investment",
        "Postpaid",
    ]

    return {
        "reps": list(reps),
        "locations": list(locations),
        "statuses": statuses,
    }
