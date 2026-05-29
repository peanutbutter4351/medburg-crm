"""
Doctor service layer.  (ARCH-2B: Snapshot Accounting)

All heavy query logic lives here so views stay thin and templates
receive pre-computed data only.

ARCH-2B changes
───────────────
1. achieved_roi Subquery now uses Sum("value_at_sale") — NEVER medicine.pts.

2. distinct=True BUG FIXED for total_investment and total_roi_amount:
   ─────────────────────────────────────────────────────────────────────
   The original code used Sum("investments__amount", distinct=True).
   This de-duplicates on VALUE, not on identity.

   Example of the bug:
     Doctor has Investment A (₹15,000) and Investment B (₹15,000)
     distinct=True sees two identical values → keeps only one → total = ₹15,000
     Correct total should be ₹30,000.

   Fix: Use a Subquery that computes the SUM inside the Investment table
   filtered to the doctor's ID — one SELECT per doctor, no cross-join, no
   value-based deduplication.

3. Both investment Subqueries are scoped to active (in_progress) investments
   so the dashboard shows ACTIVE EXPOSURE only, not historical totals.
"""

from decimal import Decimal

from django.db.models import (
    Sum, F, Value, Case, When, CharField,
    DecimalField, IntegerField, Q,
    OuterRef, Subquery,
)
from django.db.models.functions import Coalesce, Least

from doctors.models import Doctor, Investment
from sales.models import SalesEntry


def get_dashboard_queryset(*, rep_id=None, location=None, status=None, search=None):
    """
    Return an annotated Doctor queryset with all ROI columns
    pre-computed at the database level.

    Annotations added
    ─────────────────
    total_investment  – Σ active investment amounts    (Subquery, no distinct)
    total_roi_amount  – Σ active investment roi_amounts (Subquery, no distinct)
    achieved_roi      – Σ value_at_sale for all prepaid entries (Subquery)
    balance_roi       – total_roi_amount − achieved_roi
    roi_status        – Completed / In Progress / Pending / No Investment / Postpaid

    Subquery strategy (avoids cross-join inflation AND distinct=True value bug):
    Each annotation is computed as an independent correlated Subquery so that
    the results are never inflated by JOINs between Investment and SalesEntry.
    """

    # ── Subquery 1: total active investment amount per doctor ──────────────
    # Sums Investment.amount for in_progress investments only.
    # No distinct=True — the Subquery operates on the Investment table directly.
    investment_total_subquery = (
        Investment.objects
        .filter(
            doctor_id=OuterRef("pk"),
            status=Investment.STATUS_IN_PROGRESS,
        )
        .values("doctor_id")
        .annotate(total=Sum("amount"))
        .values("total")[:1]
    )

    # ── Subquery 2: total active ROI target per doctor ─────────────────────
    # Sums amount × roi_ratio for in_progress investments only.
    roi_total_subquery = (
        Investment.objects
        .filter(
            doctor_id=OuterRef("pk"),
            status=Investment.STATUS_IN_PROGRESS,
        )
        .values("doctor_id")
        .annotate(total=Sum(F("amount") * F("roi_ratio")))
        .values("total")[:1]
    )

    # ── Subquery 3: achieved ROI per doctor (snapshot-based) ───────────────
    # Sums value_at_sale for SalesEntry rows linked to ANY investment
    # (investment__isnull=False ensures prepaid-only entries).
    # ARCH-2B: uses value_at_sale — NEVER quantity × medicine.pts.
    achieved_subquery = (
        SalesEntry.objects
        .filter(
            doctor_id=OuterRef("pk"),
            investment__isnull=False,        # prepaid entries only
        )
        .values("doctor_id")
        .annotate(total=Sum("value_at_sale"))
        .values("total")[:1]
    )

    qs = (
        Doctor.objects
        .filter(is_active=True, mode="prepaid")
        .select_related("assigned_rep")
        .annotate(
            total_investment=Coalesce(
                Subquery(investment_total_subquery, output_field=DecimalField()),
                Value(Decimal("0")),
                output_field=DecimalField(),
            ),
            total_roi_amount=Coalesce(
                Subquery(roi_total_subquery, output_field=DecimalField()),
                Value(Decimal("0")),
                output_field=DecimalField(),
            ),
            achieved_roi=Coalesce(
                Subquery(achieved_subquery, output_field=DecimalField()),
                Value(Decimal("0")),
                output_field=DecimalField(),
            ),
        )
        .annotate(
            balance_roi=F("total_roi_amount") - F("achieved_roi"),
        )
        .annotate(
            roi_status=Case(
                When(total_roi_amount=Decimal("0"), then=Value("No Investment")),
                When(achieved_roi__gte=F("total_roi_amount"), then=Value("Completed")),
                When(achieved_roi__gt=Decimal("0"), then=Value("In Progress")),
                default=Value("Pending"),
                output_field=CharField(),
            ),
            progress_pct=Case(
                When(total_roi_amount=Decimal("0"), then=Value(0)),
                default=Least(
                    Value(100),
                    F("achieved_roi") * Value(100) / F("total_roi_amount"),
                ),
                output_field=IntegerField(),
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

    These sum the already-computed Subquery annotations (total_investment,
    total_roi_amount, achieved_roi, balance_roi) — no further live-PTS
    calculations are performed.
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
    ]

    return {
        "reps": list(reps),
        "locations": list(locations),
        "statuses": statuses,
    }
