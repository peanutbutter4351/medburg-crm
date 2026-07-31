"""
Report views — Sales report page + Excel export endpoint.

All business logic delegated to reports.services.report_service.
Views are thin: parse request params, call service, render / respond.

Pagination strategy (R1-B)
──────────────────────────
Progressive balance calculation and sorting happen FIRST inside
get_doctor_roi_report().  Only after the full sorted list is ready
do we slice it with Django’s Paginator.  This guarantees that
balances are always computed across the whole investment sequence,
not just the current page.

The export endpoint deliberately bypasses pagination and always
exports the full filtered+sorted dataset.
"""

from datetime import datetime

from django.core.paginator import InvalidPage, Paginator
from django.http import HttpResponse
from django.shortcuts import render

from core.decorators import admin_required

from .services.report_service import (
    export_to_excel,
    get_doctor_roi_report,
    get_report_filter_options,
    get_report_queryset,
    get_report_summary,
    get_prepaid_doctor_report_queryset,
    get_prepaid_doctor_report_summary,
    export_prepaid_doctor_report_to_excel,
    get_prepaid_doctor_report_filter_options,
)


def _parse_filters(request):
    """
    Extract and normalise filter parameters from the GET querystring.
    Returns a dict ready to be unpacked into get_report_queryset().
    """
    from_date_raw = request.GET.get("from_date", "").strip()
    to_date_raw = request.GET.get("to_date", "").strip()

    from_date = None
    to_date = None
    if from_date_raw:
        try:
            from_date = datetime.strptime(from_date_raw, "%Y-%m-%d").date()
        except ValueError:
            pass
    if to_date_raw:
        try:
            to_date = datetime.strptime(to_date_raw, "%Y-%m-%d").date()
        except ValueError:
            pass

    doctor_id_raw = request.GET.get("doctor", "")
    rep_id_raw = request.GET.get("rep", "")
    medicine_id_raw = request.GET.get("medicine", "")

    def _safe_int(val):
        try:
            return int(val) if val else None
        except (ValueError, TypeError):
            return None

    sort_raw = request.GET.get("sort", "newest_first")
    valid_sorts = {
        "newest_first", "oldest_first",
        "doctor_az", "doctor_za",
        "highest_balance", "lowest_balance",
        "completed_first", "inprogress_first"
    }
    if sort_raw not in valid_sorts:
        sort_raw = "newest_first"

    return {
        "from_date": from_date,
        "to_date": to_date,
        "doctor_id": _safe_int(doctor_id_raw),
        "rep_id": _safe_int(rep_id_raw),
        "medicine_id": _safe_int(medicine_id_raw),
        "sort": sort_raw,
    }


# ── Pagination constant ──────────────────────────────────────────
PAGE_SIZE = 25


def _filter_querystring(request, exclude=("page",)):
    """
    Build a URL-encoded querystring from the current GET params,
    excluding the keys listed in `exclude`.
    Used to preserve all active filters/sort across page links.
    """
    params = request.GET.copy()
    for key in exclude:
        params.pop(key, None)
    return params.urlencode()


@admin_required
def report_view(request):
    """
    Sales report page with filters, data table, and summary cards.

    Pagination is applied AFTER progressive balance calculation and sorting
    so that running balances are always mathematically correct.
    """
    filters = _parse_filters(request)
    queryset = get_report_queryset(**filters)
    summary = get_report_summary(queryset)
    filter_options = get_report_filter_options()

    # Full sorted list with correct running balances
    all_rows = get_doctor_roi_report(**filters)

    # Paginate the pre-computed list
    paginator = Paginator(all_rows, PAGE_SIZE)
    page_number_raw = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page_number_raw)
    except InvalidPage:
        page_obj = paginator.page(1)

    # Query string without ?page= for building pagination links
    filter_qs = _filter_querystring(request)

    context = {
        "roi_rows": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "filter_qs": filter_qs,
        "summary": summary,
        "filter_options": filter_options,
        # Sticky filter values
        "current_from_date": request.GET.get("from_date", ""),
        "current_to_date": request.GET.get("to_date", ""),
        "current_doctor": filters["doctor_id"],
        "current_rep": filters["rep_id"],
        "current_medicine": filters["medicine_id"],
        "current_sort": filters["sort"],
        "has_filters": any(v for k, v in filters.items() if k != "sort"),
    }

    return render(request, "reports/report.html", context)


@admin_required
def export_report_view(request):
    """
    Excel export endpoint.

    Applies the same filters as the report page and streams
    back the generated .xlsx file.
    """
    filters = _parse_filters(request)
    queryset = get_report_queryset(**filters)
    summary = get_report_summary(queryset)
    roi_rows = get_doctor_roi_report(**filters)

    buf = export_to_excel(roi_rows, summary)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"medburg_sales_report_{timestamp}.xlsx"

    response = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response


def _parse_prepaid_doctor_filters(request):
    """
    Extract and normalise filter parameters from the GET querystring for Prepaid Doctor Report.
    """
    from_date_raw = request.GET.get("from_date", "").strip()
    to_date_raw = request.GET.get("to_date", "").strip()

    from_date = None
    to_date = None
    if from_date_raw:
        try:
            from_date = datetime.strptime(from_date_raw, "%Y-%m-%d").date()
        except ValueError:
            pass
    if to_date_raw:
        try:
            to_date = datetime.strptime(to_date_raw, "%Y-%m-%d").date()
        except ValueError:
            pass

    doctor_id_raw = request.GET.get("doctor", "")
    location_raw = request.GET.get("location", "").strip()
    medicine_id_raw = request.GET.get("medicine", "")
    status_raw = request.GET.get("status", "").strip()

    def _safe_int(val):
        try:
            return int(val) if val else None
        except (ValueError, TypeError):
            return None

    valid_statuses = {"in_progress", "completed"}
    status = status_raw if status_raw in valid_statuses else None

    return {
        "from_date": from_date,
        "to_date": to_date,
        "doctor_id": _safe_int(doctor_id_raw),
        "location": location_raw or None,
        "medicine_id": _safe_int(medicine_id_raw),
        "status": status,
    }


@admin_required
def prepaid_doctor_report_view(request):
    """
    Consolidated doctor-wise prepaid report page with filters, metrics, and data table.
    """
    filters = _parse_prepaid_doctor_filters(request)
    queryset = get_prepaid_doctor_report_queryset(**filters)
    summary = get_prepaid_doctor_report_summary(queryset)
    filter_options = get_prepaid_doctor_report_filter_options()

    # Paginate
    paginator = Paginator(queryset, PAGE_SIZE)
    page_number = request.GET.get("page", 1)
    try:
        page_obj = paginator.page(page_number)
    except InvalidPage:
        page_obj = paginator.page(1)

    filter_qs = _filter_querystring(request)

    context = {
        "doctors": page_obj.object_list,
        "page_obj": page_obj,
        "paginator": paginator,
        "filter_qs": filter_qs,
        "summary": summary,
        "filter_options": filter_options,
        # Sticky filters
        "current_from_date": request.GET.get("from_date", ""),
        "current_to_date": request.GET.get("to_date", ""),
        "current_doctor": filters["doctor_id"],
        "current_location": filters["location"],
        "current_medicine": filters["medicine_id"],
        "current_status": request.GET.get("status", ""),
        "has_filters": any(v for k, v in filters.items() if v is not None),
    }

    return render(request, "reports/prepaid_doctor_report.html", context)


@admin_required
def export_prepaid_doctor_report_view(request):
    """
    Excel export for the consolidated doctor-wise prepaid report.
    """
    filters = _parse_prepaid_doctor_filters(request)
    queryset = get_prepaid_doctor_report_queryset(**filters)
    summary = get_prepaid_doctor_report_summary(queryset)

    # Format applied filters description for Excel header
    filters_desc = {}
    if filters["doctor_id"]:
        from doctors.models import Doctor
        try:
            doc = Doctor.objects.get(pk=filters["doctor_id"])
            filters_desc["Doctor"] = doc.name
        except Doctor.DoesNotExist:
            pass
    if filters["location"]:
        filters_desc["Location"] = filters["location"]
    if filters["medicine_id"]:
        from medicines.models import Medicine
        try:
            med = Medicine.objects.get(pk=filters["medicine_id"])
            filters_desc["Product"] = f"{med.name} ({med.brand})" if med.brand else med.name
        except Medicine.DoesNotExist:
            pass
    if filters["from_date"]:
        filters_desc["Sales Date From"] = filters["from_date"].strftime("%Y-%m-%d")
    if filters["to_date"]:
        filters_desc["Sales Date To"] = filters["to_date"].strftime("%Y-%m-%d")
    if filters["status"]:
        filters_desc["Investment Status"] = filters["status"].replace("_", " ").title()

    buf = export_prepaid_doctor_report_to_excel(queryset, summary, filters_desc)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    filename = f"medburg_prepaid_doctors_report_{timestamp}.xlsx"

    response = HttpResponse(
        buf.getvalue(),
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    response["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response

