"""
Report views — Sales report page + Excel export endpoint.

All business logic delegated to reports.services.report_service.
Views are thin: parse request params, call service, render / respond.
"""

from datetime import datetime

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from .services.report_service import (
    export_to_excel,
    get_doctor_roi_report,
    get_report_filter_options,
    get_report_queryset,
    get_report_summary,
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

    return {
        "from_date": from_date,
        "to_date": to_date,
        "doctor_id": _safe_int(doctor_id_raw),
        "rep_id": _safe_int(rep_id_raw),
        "medicine_id": _safe_int(medicine_id_raw),
    }


@login_required
def report_view(request):
    """
    Sales report page with filters, data table, and summary cards.
    """
    filters = _parse_filters(request)
    queryset = get_report_queryset(**filters)
    summary = get_report_summary(queryset)
    filter_options = get_report_filter_options()
    roi_rows = get_doctor_roi_report(**filters)

    context = {
        "entries": queryset,
        "roi_rows": roi_rows,
        "summary": summary,
        "filter_options": filter_options,
        # Sticky filter values
        "current_from_date": request.GET.get("from_date", ""),
        "current_to_date": request.GET.get("to_date", ""),
        "current_doctor": filters["doctor_id"],
        "current_rep": filters["rep_id"],
        "current_medicine": filters["medicine_id"],
        "has_filters": any(filters.values()),
    }

    return render(request, "reports/report.html", context)


@login_required
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
