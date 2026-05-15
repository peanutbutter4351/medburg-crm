"""
Sales views — entry form, AJAX endpoints, and postpaid listing.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST

from core.decorators import admin_required
from doctors.models import Doctor

from .forms import SalesEntryForm
from .services.sales_service import (
    create_sales_entry,
    get_doctor_roi_summary,
    get_medicines_for_doctor,
)
from .services.postpaid_service import (
    get_postpaid_queryset,
    get_postpaid_summary,
    get_postpaid_filter_options,
    mark_as_paid,
    record_payment,
)


@login_required
def sales_entry_view(request):
    """
    Sales entry page — the primary interface for reps.

    GET  → render empty form
    POST → validate, create entry, show success, reset form
    """
    if request.method == "POST":
        form = SalesEntryForm(request.POST, rep=request.user)
        if form.is_valid():
            entry = create_sales_entry(
                rep=request.user,
                doctor=form.cleaned_data["doctor"],
                medicine=form.cleaned_data["medicine"],
                quantity=form.cleaned_data["quantity"],
            )
            messages.success(
                request,
                f"✅ Saved — {entry.medicine.name} × {entry.quantity} "
                f"for Dr. {entry.doctor.name} (₹{entry.value:,.2f})",
            )
            return redirect("sales:entry")
    else:
        form = SalesEntryForm(rep=request.user)

    return render(request, "sales/sales_entry.html", {"form": form})


@login_required
def api_medicines_for_doctor(request, doctor_id):
    """
    AJAX endpoint: returns medicines mapped to a doctor as JSON.
    Also returns the doctor's ROI summary for the info panel.
    """
    doctor = get_object_or_404(Doctor, pk=doctor_id, is_active=True)
    medicines = get_medicines_for_doctor(doctor_id)
    roi_summary = get_doctor_roi_summary(doctor)

    return JsonResponse({
        "medicines": medicines,
        "roi": roi_summary,
    })


@admin_required
def postpaid_list_view(request):
    """
    Postpaid entries listing page with filters and summary cards.
    """
    # ── Collect filter params ────────────────────────
    doctor_id_raw = request.GET.get("doctor", "")
    try:
        doctor_id = int(doctor_id_raw) if doctor_id_raw else None
    except (ValueError, TypeError):
        doctor_id = None

    status = request.GET.get("status", "")
    search = request.GET.get("search", "").strip()

    # ── Fetch data via service ───────────────────────
    entries = get_postpaid_queryset(
        doctor_id=doctor_id or None,
        status=status or None,
        search=search or None,
    )
    summary = get_postpaid_summary(entries)
    filter_options = get_postpaid_filter_options()

    context = {
        "entries": entries,
        "summary": summary,
        "filter_options": filter_options,
        # Sticky filter values
        "current_doctor": doctor_id,
        "current_status": status,
        "current_search": search,
        "has_filters": any([doctor_id, status, search]),
    }

    return render(request, "sales/postpaid_list.html", context)


@admin_required
@require_POST
def mark_as_paid_view(request, entry_id):
    """
    Record a payment against a postpaid entry.

    Supports two modes:
    - Full pay: no 'amount' in POST → marks entry as fully paid.
    - Partial pay: 'amount' in POST → records that specific amount.

    POST-only with CSRF protection.  Redirects back to the
    postpaid list with a success or error message.
    """
    from django.core.exceptions import ValidationError
    from sales.models import PostpaidEntry

    try:
        pay_amount_raw = request.POST.get("amount", "").strip()

        if pay_amount_raw:
            # Partial / specific amount payment
            entry = record_payment(entry_id, pay_amount_raw)
            messages.success(
                request,
                f"✅ Payment of ₹{entry.paid_amount:,.2f} recorded — "
                f"{entry.doctor.name} | {entry.medicine.name} "
                f"({entry.get_payment_status_display()})",
            )
        else:
            # Full payment
            entry = mark_as_paid(entry_id)
            messages.success(
                request,
                f"✅ Marked as fully paid — {entry.doctor.name} | "
                f"{entry.medicine.name} (₹{entry.amount:,.2f})",
            )
    except PostpaidEntry.DoesNotExist:
        messages.error(request, "Entry not found.")
    except ValidationError as e:
        # Surface validation errors (e.g. overpayment)
        error_msg = "; ".join(
            msg for msg_list in e.message_dict.values() for msg in msg_list
        ) if hasattr(e, "message_dict") else str(e)
        messages.error(request, f"Payment failed: {error_msg}")

    return redirect("sales:postpaid")

