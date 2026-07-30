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

from datetime import date
from decimal import Decimal

from django.db.models import (
    Sum, F, Value, Case, When, CharField,
    DecimalField, IntegerField, Q,
    OuterRef, Subquery, ExpressionWrapper,
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
    # Sums value_at_sale for SalesEntry rows linked to active investments.
    # ARCH-2B: uses value_at_sale — NEVER quantity × medicine.pts.
    achieved_subquery = (
        SalesEntry.objects
        .filter(
            doctor_id=OuterRef("pk"),
            investment__status=Investment.STATUS_IN_PROGRESS,
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


def get_postpaid_dashboard_summary():
    """
    Aggregate postpaid metrics, excluding locked campaigns from active exposure.
    """
    from sales.models import PostpaidCampaign, PostpaidSaleEntry
    from datetime import date
    
    qs = PostpaidCampaign.objects.exclude(status=PostpaidCampaign.STATUS_LOCKED)
    
    agg = qs.aggregate(
        comm=Coalesce(Sum("total_commission"), Value(Decimal("0")), output_field=DecimalField()),
        paid=Coalesce(Sum("paid_amount"), Value(Decimal("0")), output_field=DecimalField()),
    )
    
    today = date.today()
    monthly_sales = PostpaidSaleEntry.objects.filter(
        entry_date__month=today.month,
        entry_date__year=today.year
    ).aggregate(t=Sum("value_at_sale"))["t"] or Decimal("0.00")
    
    comm = agg["comm"]
    paid = agg["paid"]
    outstanding = comm - paid
    
    return {
        "active_campaigns_count": qs.count(),
        "monthly_sales": monthly_sales,
        "total_commission": comm,
        "total_paid": paid,
        "total_outstanding": outstanding,
    }


def get_dashboard_alerts():
    """
    Return a list of alerts: awaiting commission older than 3 days (yellow) and 7 days (red),
    and settlement integrity anomalies.
    """
    from sales.models import PostpaidCampaign
    from django.utils import timezone
    from decimal import Decimal
    
    alerts = []
    now = timezone.now()
    
    # 1. Settlement Integrity Alert (Critical — Red)
    # Use DB-level annotation with ExpressionWrapper to avoid full Python-side table scan.
    # Do not iterate over all settled campaigns and check the @property in Python.
    settled_anomalies = PostpaidCampaign.objects.filter(
        status=PostpaidCampaign.STATUS_SETTLED
    ).annotate(
        computed_outstanding=ExpressionWrapper(
            F("total_commission") - F("paid_amount"),
            output_field=DecimalField()
        )
    ).filter(computed_outstanding__gt=Decimal("0")).select_related("doctor")

    for camp in settled_anomalies:
        alerts.append({
            "type": "danger",
            "message": (
                f"🚨 Settlement Integrity Anomaly: Campaign for Dr. {camp.doctor.name} "
                f"({camp.month:02d}/{camp.year}) is Settled but has an unpaid outstanding "
                f"balance of ₹{camp.computed_outstanding:,.2f}. Verify justification notes."
            )
        })
    
    # 2. Awaiting Commission alerts
    # Age is measured using campaign.created_at because MR-4F is a non-schema phase and no awaiting_since field exists.
    # This proxy is only reliable for campaigns that have remained in STATUS_AWAITING_COMMISSION since creation.
    # FUTURE ENHANCEMENT: A dedicated awaiting_since = DateTimeField(null=True) field should be added in a future schema phase to track status transitions accurately.
    awaiting = PostpaidCampaign.objects.filter(status=PostpaidCampaign.STATUS_AWAITING_COMMISSION).select_related("doctor")
    for camp in awaiting:
        age_days = (now - camp.created_at).days
        if age_days >= 7:
            alerts.append({
                "type": "danger",
                "message": f"🚨 RED WARNING: Campaign for Dr. {camp.doctor.name} ({camp.month:02d}/{camp.year}) has been Awaiting Commission for {age_days} days. Configure commission immediately."
            })
        elif age_days >= 3:
            alerts.append({
                "type": "warning",
                "message": f"⚠️ WARNING: Campaign for Dr. {camp.doctor.name} ({camp.month:02d}/{camp.year}) has been Awaiting Commission for {age_days} days."
            })
            
    # FUTURE ENHANCEMENT (MR-4I or later): Add stalled payout alert for STATUS_PARTIAL campaigns with no payment > N days.
            
    return alerts


def get_rep_dashboard_data(rep_user):
    """
    Gather prepaid and postpaid metrics for a representative's personal dashboard.
    """
    from sales.models import SalesEntry, PostpaidCampaign, PostpaidSaleEntry
    from doctors.models import Investment
    
    # Prepaid Metrics
    active_invs = Investment.objects.filter(
        doctor__assigned_rep=rep_user,
        doctor__is_active=True,
        status=Investment.STATUS_IN_PROGRESS
    )
    
    total_roi_target = active_invs.aggregate(t=Sum(F("amount") * F("roi_ratio")))["t"] or Decimal("0.00")
    
    # Sales recorded by this rep against active investments
    achieved_val = SalesEntry.objects.filter(
        rep=rep_user,
        investment__status=Investment.STATUS_IN_PROGRESS
    ).aggregate(t=Sum("value_at_sale"))["t"] or Decimal("0.00")
    
    remaining_balance = total_roi_target - achieved_val
    recovery_pct = 0
    if total_roi_target > 0:
        recovery_pct = min(100, int((achieved_val / total_roi_target) * 100))
        
    recent_prepaid_sales = SalesEntry.objects.filter(
        rep=rep_user,
        investment__isnull=False
    ).select_related("doctor", "medicine", "investment").order_by("-entry_date", "-created_at")[:10]
    
    completed_invs_count = Investment.objects.filter(
        doctor__assigned_rep=rep_user,
        status=Investment.STATUS_COMPLETED
    ).count()

    # Postpaid Metrics
    active_camps = PostpaidCampaign.objects.filter(
        doctor__assigned_rep=rep_user,
        doctor__is_active=True
    ).exclude(status=PostpaidCampaign.STATUS_LOCKED)
    
    today = date.today()
    monthly_sales_val = PostpaidSaleEntry.objects.filter(
        rep=rep_user,
        entry_date__month=today.month,
        entry_date__year=today.year
    ).aggregate(t=Sum("value_at_sale"))["t"] or Decimal("0.00")
    
    status_summary = {
        "awaiting_commission": active_camps.filter(status=PostpaidCampaign.STATUS_AWAITING_COMMISSION).count(),
        "open": active_camps.filter(status=PostpaidCampaign.STATUS_OPEN).count(),
        "partial": active_camps.filter(status=PostpaidCampaign.STATUS_PARTIAL).count(),
        "settled": active_camps.filter(status=PostpaidCampaign.STATUS_SETTLED).count(),
    }
    
    recent_postpaid_sales = PostpaidSaleEntry.objects.filter(
        rep=rep_user
    ).select_related("campaign__doctor", "medicine").order_by("-entry_date", "-created_at")[:10]

    return {
        "prepaid": {
            "active_investments_count": active_invs.count(),
            "completed_investments_count": completed_invs_count,
            "achieved_value": achieved_val,
            "balance": remaining_balance,
            "recovery_pct": recovery_pct,
            "recent_sales": recent_prepaid_sales,
        },
        "postpaid": {
            "active_campaigns_count": active_camps.count(),
            "monthly_sales": monthly_sales_val,
            "status_summary": status_summary,
            "recent_sales": recent_postpaid_sales,
        }
    }


def get_prepaid_admin_metrics():
    """
    Compute recovery rate and completed investments count for the admin dashboard.
    """
    from django.db.models import ExpressionWrapper, DecimalField
    from django.utils import timezone
    from datetime import timedelta
    
    active_invs = Investment.objects.filter(status=Investment.STATUS_IN_PROGRESS)

    total_active_target = active_invs.aggregate(
        t=Sum(
            ExpressionWrapper(F("amount") * F("roi_ratio"), output_field=DecimalField())
        )
    )["t"] or Decimal("0.00")

    total_active_achieved = SalesEntry.objects.filter(
        investment__status=Investment.STATUS_IN_PROGRESS
    ).aggregate(t=Sum("value_at_sale"))["t"] or Decimal("0.00")

    recovery_rate = (
        (total_active_achieved / total_active_target * 100)
        if total_active_target > 0
        else Decimal("0.00")
    )
    
    thirty_days_ago = timezone.now().date() - timedelta(days=30)
    completed_count = Investment.objects.filter(
        status=Investment.STATUS_COMPLETED,
        updated_at__date__gte=thirty_days_ago
    ).count()
    
    return {
        "recovery_rate": recovery_rate,
        "completed_last_30d": completed_count,
    }


def get_unified_activity_feed():
    """
    Chronological activity feed merging prepaid SalesEntry and postpaid PostpaidSaleEntry.
    """
    from sales.models import PostpaidSaleEntry
    from itertools import chain

    recent_prepaid = (
        SalesEntry.objects
        .select_related("doctor", "medicine", "rep")
        .order_by("-entry_date", "-created_at")[:20]
    )
    recent_postpaid = (
        PostpaidSaleEntry.objects
        .select_related("campaign__doctor", "medicine", "rep")
        .order_by("-entry_date", "-created_at")[:20]
    )

    unified_feed = sorted(
        chain(
            [{"type": "prepaid", "obj": s} for s in recent_prepaid],
            [{"type": "postpaid", "obj": s} for s in recent_postpaid],
        ),
        key=lambda x: (x["obj"].entry_date, x["obj"].created_at),
        reverse=True,
    )[:10]
    return unified_feed


def get_active_postpaid_campaigns():
    """
    Return active postpaid campaigns, excluding Locked status.
    """
    from sales.models import PostpaidCampaign
    return PostpaidCampaign.objects.exclude(
        status=PostpaidCampaign.STATUS_LOCKED
    ).select_related("doctor").order_by("-year", "-month", "doctor__name")
