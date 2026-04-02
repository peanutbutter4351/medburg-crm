"""
Sales views — entry form + AJAX endpoints.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404

from doctors.models import Doctor

from .forms import SalesEntryForm
from .services.sales_service import (
    create_sales_entry,
    get_doctor_roi_summary,
    get_medicines_for_doctor,
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
