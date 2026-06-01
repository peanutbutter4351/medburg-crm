"""
Sales views — entry forms, reporting, management dashboards, and AJAX endpoints.
"""

from datetime import date
from decimal import Decimal
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import ValidationError
from django.http import JsonResponse, HttpResponseForbidden
from django.shortcuts import render, redirect, get_object_or_404
from django.utils import timezone
from django.views.decorators.http import require_POST

from core.decorators import admin_required
from doctors.models import Doctor
from .models import SalesEntry, PostpaidCampaign, PostpaidSaleEntry, CampaignPayment
from .forms import (
    SalesEntryForm,
    PostpaidSalesEntryForm,
    CampaignCommissionForm,
    CampaignPaymentForm
)
from .services.sales_service import (
    create_sales_entry,
    get_investments_data_for_doctor,
    get_medicines_for_doctor,
)
from .services.postpaid_service import (
    get_campaign_queryset,
    get_campaign_summary,
    get_campaign_filter_options,
)


@login_required
def prepaid_sales_entry_view(request):
    """
    Sales entry page for Prepaid doctors.
    """
    if request.method == "POST":
        form = SalesEntryForm(request.POST, rep=request.user)
        if form.is_valid():
            entry = create_sales_entry(
                rep=request.user,
                doctor=form.cleaned_data["doctor"],
                investment=form.cleaned_data["investment"],
                medicine=form.cleaned_data["medicine"],
                quantity=form.cleaned_data["quantity"],
            )
            if form.cleaned_data.get("notes"):
                entry.notes = form.cleaned_data["notes"]
                entry.save(update_fields=["notes"])

            messages.success(
                request,
                f"✅ Prepaid Sale Saved — {entry.medicine.name} × {entry.quantity} "
                f"for Dr. {entry.doctor.name} (₹{entry.value:,.2f})",
            )
            return redirect("sales:prepaid_entry")
    else:
        form = SalesEntryForm(rep=request.user)

    return render(request, "sales/sales_entry.html", {"form": form})


@login_required
def postpaid_sales_entry_view(request):
    """
    Sales entry page for Postpaid doctors.
    Auto-resolves or creates the monthly campaign on submission.
    """
    if request.method == "POST":
        form = PostpaidSalesEntryForm(request.POST, rep=request.user)
        if form.is_valid():
            doctor = form.cleaned_data["doctor"]
            month = int(form.cleaned_data["month"])
            year = int(form.cleaned_data["year"])
            medicine = form.cleaned_data["medicine"]
            quantity = form.cleaned_data["quantity"]
            notes = form.cleaned_data.get("notes", "")

            # 1. Resolve or Auto-Create Campaign in awaiting_commission status (NULL commission)
            campaign, created = PostpaidCampaign.objects.get_or_create(
                doctor=doctor,
                month=month,
                year=year,
                defaults={
                    "commission_percentage": None,
                    "status": PostpaidCampaign.STATUS_AWAITING_COMMISSION,
                }
            )

            # 2. Check campaign lock state
            if campaign.status in (
                PostpaidCampaign.STATUS_PARTIAL,
                PostpaidCampaign.STATUS_SETTLED,
                PostpaidCampaign.STATUS_LOCKED,
            ):
                form.add_error("doctor", f"This campaign is locked, partial, or settled. No new entries can be added.")
            else:
                try:
                    # 3. Create PostpaidSaleEntry
                    sale = PostpaidSaleEntry.objects.create(
                        campaign=campaign,
                        medicine=medicine,
                        quantity=quantity,
                        entry_date=date.today(),
                        rep=request.user,
                        notes=notes
                    )
                    messages.success(
                        request,
                        f"✅ Postpaid Sale Saved — {sale.medicine.name} × {sale.quantity} "
                        f"for Dr. {doctor.name} ({month:02d}/{year})",
                    )
                    return redirect("sales:postpaid_entry")
                except ValidationError as e:
                    form.add_error(None, e)
    else:
        form = PostpaidSalesEntryForm(rep=request.user)

    return render(request, "sales/postpaid_sales_entry.html", {"form": form})


@admin_required
def postpaid_report_view(request):
    """
    Read-only postpaid campaign monitoring report.
    """
    # Collect filter params
    doctor_id_raw = request.GET.get("doctor", "")
    try:
        doctor_id = int(doctor_id_raw) if doctor_id_raw else None
    except (ValueError, TypeError):
        doctor_id = None

    month_raw = request.GET.get("month", "")
    try:
        month = int(month_raw) if month_raw else None
    except (ValueError, TypeError):
        month = None

    year_raw = request.GET.get("year", "")
    try:
        year = int(year_raw) if year_raw else None
    except (ValueError, TypeError):
        year = None

    status = request.GET.get("status", "")
    search = request.GET.get("search", "").strip()

    campaigns = get_campaign_queryset(
        doctor_id=doctor_id,
        month=month,
        year=year,
        status=status,
        search=search
    )
    summary = get_campaign_summary(campaigns)
    filter_options = get_campaign_filter_options()

    context = {
        "campaigns": campaigns,
        "summary": summary,
        "filter_options": filter_options,
        "current_doctor": doctor_id,
        "current_month": month,
        "current_year": year,
        "current_status": status,
        "current_search": search,
        "has_filters": any([doctor_id, month, year, status, search]),
    }
    return render(request, "sales/postpaid_report.html", context)


@admin_required
def campaign_management_view(request, campaign_id):
    """
    Admin control center for a specific postpaid campaign.
    Renders commission configuration, ledger payment recording, and status changes.
    """
    campaign = get_object_or_404(PostpaidCampaign, pk=campaign_id)
    sales = campaign.sales_entries.select_related("medicine", "rep").order_by("-entry_date")
    payments = campaign.payments.order_by("-payment_date", "-created_at")

    commission_form = CampaignCommissionForm(instance=campaign)
    payment_form = CampaignPaymentForm()

    context = {
        "campaign": campaign,
        "sales": sales,
        "payments": payments,
        "commission_form": commission_form,
        "payment_form": payment_form,
    }
    return render(request, "sales/campaign_manage.html", context)


@admin_required
@require_POST
def update_commission_view(request, campaign_id):
    """
    Endpoint for updating campaign commission percentage.
    Only allowed in awaiting_commission or open status.
    """
    from django.db import transaction
    with transaction.atomic():
        campaign = get_object_or_404(PostpaidCampaign, pk=campaign_id)
        form = CampaignCommissionForm(request.POST, instance=campaign)
        if form.is_valid():
            try:
                campaign.update_commission_percentage(form.cleaned_data["commission_percentage"])
                messages.success(request, f"✅ Commission updated successfully to {campaign.commission_percentage}%.")
            except ValidationError as e:
                messages.error(request, f"❌ Failed to update commission: {e.message if hasattr(e, 'message') else str(e)}")
        else:
            messages.error(request, "❌ Invalid commission value entered.")

    return redirect("sales:campaign_manage", campaign_id=campaign.id)


@admin_required
@require_POST
def record_payment_view(request, campaign_id):
    """
    Endpoint for recording a ledger payment against a campaign.
    Only allowed in open or partial status.
    """
    from django.db import transaction
    with transaction.atomic():
        campaign = get_object_or_404(PostpaidCampaign, pk=campaign_id)
        form = CampaignPaymentForm(request.POST)
        if form.is_valid():
            try:
                payment = form.save(commit=False)
                payment.campaign = campaign
                # Validation inside clean() checks status and blocks negative payments
                payment.clean()
                payment.save()
                messages.success(request, f"✅ Payment of ₹{payment.amount:,.2f} recorded successfully.")
            except ValidationError as e:
                error_msg = "; ".join(msg for msg_list in e.message_dict.values() for msg in msg_list) if hasattr(e, "message_dict") else str(e)
                messages.error(request, f"❌ Payment failed: {error_msg}")
        else:
            messages.error(request, "❌ Invalid payment fields entered.")

    return redirect("sales:campaign_manage", campaign_id=campaign.id)


@admin_required
@require_POST
def advance_campaign_status_view(request, campaign_id):
    """
    POST action to manually advance a campaign's status in the lifecycle.
    Supported transitions:
    - Open -> Partial
    - Partial -> Settled
    - Settled -> Locked
    """
    from django.db import transaction
    with transaction.atomic():
        campaign = get_object_or_404(PostpaidCampaign, pk=campaign_id)
        target_status = request.POST.get("status")

        if target_status == PostpaidCampaign.STATUS_PARTIAL:
            if campaign.status == PostpaidCampaign.STATUS_OPEN:
                campaign.status = PostpaidCampaign.STATUS_PARTIAL
                campaign.save(update_fields=["status", "updated_at"])
                messages.success(request, "Campaign advanced to Partial status. Payments are now open.")
            else:
                messages.error(request, "❌ Campaign must be in Open status to transition to Partial.")
                
        elif target_status == PostpaidCampaign.STATUS_SETTLED:
            if campaign.status == PostpaidCampaign.STATUS_PARTIAL:
                campaign.status = PostpaidCampaign.STATUS_SETTLED
                campaign.settled_at = timezone.now()
                campaign.settled_by = request.user
                campaign.settlement_reason = request.POST.get("settlement_reason")
                campaign.settlement_notes = request.POST.get("settlement_notes", "").strip()
                if "settlement_attachment" in request.FILES:
                    campaign.settlement_attachment = request.FILES["settlement_attachment"]
                try:
                    campaign.full_clean()
                    campaign.save()
                    messages.success(request, "Campaign manually Settled.")
                except ValidationError as e:
                    error_msg = "; ".join(msg for msg_list in e.message_dict.values() for msg in msg_list) if hasattr(e, "message_dict") else str(e)
                    messages.error(request, f"❌ Failed to settle: {error_msg}")
            else:
                messages.error(request, "❌ Campaign must be in Partial status to settle.")
                
        elif target_status == PostpaidCampaign.STATUS_LOCKED:
            if campaign.status in (PostpaidCampaign.STATUS_PARTIAL, PostpaidCampaign.STATUS_SETTLED, PostpaidCampaign.STATUS_OPEN):
                campaign.status = PostpaidCampaign.STATUS_LOCKED
                campaign.locked_at = timezone.now()
                campaign.save(update_fields=["status", "locked_at", "updated_at"])
                messages.success(request, "🔒 Campaign successfully Locked and archived.")
            else:
                messages.error(request, f"❌ Cannot lock campaign in status '{campaign.get_status_display()}'.")
        else:
            messages.error(request, "❌ Invalid status transition requested.")

    return redirect("sales:campaign_manage", campaign_id=campaign.id)


@login_required
def api_medicines_for_doctor(request, doctor_id):
    """
    AJAX endpoint: returns medicines mapped to a doctor as JSON.
    Also returns the doctor's ROI summary for the info panel.
    """
    doctor = get_object_or_404(Doctor, pk=doctor_id, is_active=True)
    medicines = get_medicines_for_doctor(doctor_id)
    investments = get_investments_data_for_doctor(doctor)

    return JsonResponse({
        "medicines": medicines,
        "investments": investments,
        "mode": doctor.get_mode_display(),
        "is_prepaid": doctor.mode == "prepaid",
    })


@login_required
def api_campaign_for_doctor(request, doctor_id, month, year):
    """
    AJAX endpoint: returns postpaid campaign info for dynamic UI panels.
    """
    doctor = get_object_or_404(Doctor, pk=doctor_id, is_active=True)
    if doctor.mode != "postpaid":
        return JsonResponse({"exists": False, "is_prepaid": True})

    try:
        campaign = PostpaidCampaign.objects.get(doctor=doctor, month=month, year=year)
        return JsonResponse({
            "exists": True,
            "status": campaign.status,
            "status_display": campaign.get_status_display(),
            "commission_percentage": str(campaign.commission_percentage) if campaign.commission_percentage is not None else None,
            "total_sales_value": str(campaign.total_sales_value),
            "total_commission": str(campaign.total_commission),
            "is_locked": campaign.status in (PostpaidCampaign.STATUS_PARTIAL, PostpaidCampaign.STATUS_SETTLED, PostpaidCampaign.STATUS_LOCKED),
        })
    except PostpaidCampaign.DoesNotExist:
        return JsonResponse({
            "exists": False,
            "is_prepaid": False,
            "status_display": "Not Started (Will Auto-Create)",
        })
