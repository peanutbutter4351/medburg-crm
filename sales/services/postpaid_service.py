"""
Postpaid entry service layer.

Keeps view logic thin — all query and aggregation logic lives here.
"""

from decimal import Decimal

from django.db.models import Sum, Q, Value, DecimalField
from django.db.models.functions import Coalesce

from core.constants import (
    PAYMENT_STATUS_PAID,
    PAYMENT_STATUS_PARTIAL,
    PAYMENT_STATUS_UNPAID,
)
from sales.models import PostpaidEntry


def get_postpaid_queryset(*, doctor_id=None, status=None, search=None):
    """
    Return a PostpaidEntry queryset with optional filters applied.

    Filters
    ───────
    doctor_id  – restrict to a specific doctor
    status     – "paid", "partial", or "unpaid"
    search     – free-text search on doctor name or medicine name
    """
    qs = (
        PostpaidEntry.objects
        .select_related("doctor", "medicine")
        .order_by("-created_at")
    )

    if doctor_id:
        qs = qs.filter(doctor_id=doctor_id)

    if status in (PAYMENT_STATUS_PAID, PAYMENT_STATUS_PARTIAL, PAYMENT_STATUS_UNPAID):
        qs = qs.filter(payment_status=status)

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

    Now tracks three states: paid, partial, unpaid — and sums
    actual paid_amount alongside computed amount.
    """
    agg = queryset.aggregate(
        total_amount=Coalesce(
            Sum("amount"), Value(Decimal("0")),
            output_field=DecimalField(),
        ),
        total_paid=Coalesce(
            Sum("paid_amount"), Value(Decimal("0")),
            output_field=DecimalField(),
        ),
        paid_entry_amount=Coalesce(
            Sum("amount", filter=Q(payment_status=PAYMENT_STATUS_PAID)),
            Value(Decimal("0")),
            output_field=DecimalField(),
        ),
        partial_paid_so_far=Coalesce(
            Sum("paid_amount", filter=Q(payment_status=PAYMENT_STATUS_PARTIAL)),
            Value(Decimal("0")),
            output_field=DecimalField(),
        ),
    )

    total = queryset.count()
    paid_count = queryset.filter(payment_status=PAYMENT_STATUS_PAID).count()
    partial_count = queryset.filter(payment_status=PAYMENT_STATUS_PARTIAL).count()
    unpaid_count = total - paid_count - partial_count

    total_outstanding = agg["total_amount"] - agg["total_paid"]

    return {
        "total_entries": total,
        "paid_count": paid_count,
        "partial_count": partial_count,
        "unpaid_count": unpaid_count,
        "total_amount": agg["total_amount"],
        "total_paid": agg["total_paid"],
        "total_outstanding": total_outstanding,
        # Backward compat keys
        "paid_amount": agg["paid_entry_amount"],
        "unpaid_amount": total_outstanding,
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
            {"value": PAYMENT_STATUS_PAID, "label": "Fully Paid"},
            {"value": PAYMENT_STATUS_PARTIAL, "label": "Partially Paid"},
            {"value": PAYMENT_STATUS_UNPAID, "label": "Unpaid"},
        ],
    }


def mark_as_paid(entry_id):
    """
    Mark a PostpaidEntry as fully paid (sets paid_amount = amount).

    Uses queryset.update() to avoid triggering the save() override.

    Returns the updated entry, or raises PostpaidEntry.DoesNotExist.
    """
    from datetime import date

    entry = PostpaidEntry.objects.get(pk=entry_id)
    PostpaidEntry.objects.filter(pk=entry_id).update(
        payment_status=PAYMENT_STATUS_PAID,
        paid_amount=entry.amount,
        payment_date=date.today(),
    )
    entry.refresh_from_db()
    return entry


def record_payment(entry_id, payment_amount):
    """
    Record a partial or full payment against a PostpaidEntry.

    Delegates to the model's record_payment() method which handles
    status transitions and validation.

    Returns the updated entry, or raises PostpaidEntry.DoesNotExist
    or ValidationError.
    """
    entry = PostpaidEntry.objects.get(pk=entry_id)
    return entry.record_payment(payment_amount)
