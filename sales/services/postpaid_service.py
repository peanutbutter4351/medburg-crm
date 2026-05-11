"""
Postpaid entry service layer.

Keeps view logic thin — all query and aggregation logic lives here.
"""

from decimal import Decimal

from django.db.models import Sum, Q, Value, DecimalField
from django.db.models.functions import Coalesce

from sales.models import PostpaidEntry


def get_postpaid_queryset(*, doctor_id=None, status=None, search=None):
    """
    Return a PostpaidEntry queryset with optional filters applied.

    Filters
    ───────
    doctor_id  – restrict to a specific doctor
    status     – "paid" or "unpaid"
    search     – free-text search on doctor name or medicine name
    """
    qs = (
        PostpaidEntry.objects
        .select_related("doctor", "medicine")
        .order_by("-created_at")
    )

    if doctor_id:
        qs = qs.filter(doctor_id=doctor_id)

    if status == "paid":
        qs = qs.filter(is_paid=True)
    elif status == "unpaid":
        qs = qs.filter(is_paid=False)

    if search:
        qs = qs.filter(
            Q(doctor__name__icontains=search)
            | Q(medicine__name__icontains=search)
            | Q(remarks__icontains=search)
        )

    return qs


def get_postpaid_summary(queryset):
    """
    Aggregate totals across the filtered PostpaidEntry queryset
    for the summary cards.
    """
    agg = queryset.aggregate(
        total_amount=Coalesce(
            Sum("amount"), Value(Decimal("0")),
            output_field=DecimalField(),
        ),
        paid_amount=Coalesce(
            Sum("amount", filter=Q(is_paid=True)),
            Value(Decimal("0")),
            output_field=DecimalField(),
        ),
        unpaid_amount=Coalesce(
            Sum("amount", filter=Q(is_paid=False)),
            Value(Decimal("0")),
            output_field=DecimalField(),
        ),
    )

    total = queryset.count()
    paid_count = queryset.filter(is_paid=True).count()

    return {
        "total_entries": total,
        "paid_count": paid_count,
        "unpaid_count": total - paid_count,
        "total_amount": agg["total_amount"],
        "paid_amount": agg["paid_amount"],
        "unpaid_amount": agg["unpaid_amount"],
    }


def get_postpaid_filter_options():
    """
    Return distinct values for filter dropdowns on the postpaid page.
    """
    from doctors.models import Doctor

    doctors = (
        Doctor.objects
        .filter(is_active=True, postpaid_entries__isnull=False)
        .distinct()
        .order_by("name")
        .values("id", "name")
    )

    return {
        "doctors": list(doctors),
        "statuses": [
            {"value": "paid", "label": "Paid"},
            {"value": "unpaid", "label": "Unpaid"},
        ],
    }


def mark_as_paid(entry_id):
    """
    Mark a PostpaidEntry as paid and set payment_date to today.

    Uses queryset.update() to avoid triggering the save() override
    (which recomputes amount). Only payment fields are changed.

    Returns the updated entry, or raises PostpaidEntry.DoesNotExist.
    """
    from datetime import date

    entry = PostpaidEntry.objects.get(pk=entry_id)
    PostpaidEntry.objects.filter(pk=entry_id).update(
        is_paid=True,
        payment_date=date.today(),
    )
    entry.refresh_from_db()
    return entry


