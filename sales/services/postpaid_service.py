"""
Postpaid campaign service layer.
Manages queries, aggregations, and business logic for PostpaidCampaign and CampaignPayment.
"""

from decimal import Decimal
from django.db.models import Sum, Q, F, Value, DecimalField
from django.db.models.functions import Coalesce

from sales.models import PostpaidCampaign
from doctors.models import Doctor


def get_campaign_queryset(*, month=None, year=None, doctor_id=None, status=None, search=None):
    """
    Return a PostpaidCampaign queryset with filters applied.
    """
    qs = (
        PostpaidCampaign.objects
        .select_related("doctor")
        .prefetch_related("payments", "sales_entries")
        .order_by("-year", "-month", "doctor__name")
    )

    if month:
        qs = qs.filter(month=month)
    if year:
        qs = qs.filter(year=year)
    if doctor_id:
        qs = qs.filter(doctor_id=doctor_id)
    if status:
        qs = qs.filter(status=status)
    if search:
        qs = qs.filter(
            Q(doctor__name__icontains=search) |
            Q(doctor__hospital__icontains=search)
        )

    return qs


def get_campaign_summary(queryset):
    """
    Aggregate totals across the filtered PostpaidCampaign queryset.
    """
    agg = queryset.aggregate(
        sales=Coalesce(Sum("total_sales_value"), Value(Decimal("0")), output_field=DecimalField()),
        commission=Coalesce(Sum("total_commission"), Value(Decimal("0")), output_field=DecimalField()),
        paid=Coalesce(Sum("paid_amount"), Value(Decimal("0")), output_field=DecimalField()),
    )

    sales = agg["sales"]
    commission = agg["commission"]
    paid = agg["paid"]
    outstanding = commission - paid

    return {
        "total_campaigns": queryset.count(),
        "total_sales": sales,
        "total_commission": commission,
        "total_paid": paid,
        "total_outstanding": outstanding,
    }


def get_campaign_filter_options():
    """
    Return distinct values for filter dropdowns on the postpaid campaigns report page.
    """
    doctors = (
        Doctor.objects
        .filter(is_active=True, mode="postpaid")
        .order_by("name")
        .values("id", "name")
    )

    # Gather distinct years present in the campaigns database
    campaign_years = (
        PostpaidCampaign.objects
        .values_list("year", flat=True)
        .distinct()
        .order_by("-year")
    )
    years = list(campaign_years)
    
    # If no years, default to current year
    if not years:
        import datetime
        years = [datetime.date.today().year]

    return {
        "doctors": list(doctors),
        "years": years,
        "statuses": PostpaidCampaign.STATUS_CHOICES,
    }
