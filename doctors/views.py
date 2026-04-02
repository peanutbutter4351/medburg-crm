"""
Doctor views — ROI Dashboard.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from .services.doctor_service import (
    get_dashboard_queryset,
    get_dashboard_summary,
    get_filter_options,
)


@login_required
def doctor_dashboard(request):
    """
    Admin-facing doctor ROI dashboard.

    All heavy lifting is done in the service layer — the view simply
    collects filter params, passes them through, and renders.
    """
    # ── Collect filter params ────────────────────────
    rep_id_raw = request.GET.get("rep", "")
    try:
        rep_id = int(rep_id_raw) if rep_id_raw else None
    except (ValueError, TypeError):
        rep_id = None
    location = request.GET.get("location", "")
    status   = request.GET.get("status", "")
    search   = request.GET.get("search", "").strip()

    # ── Fetch data via service ───────────────────────
    doctors = get_dashboard_queryset(
        rep_id=rep_id or None,
        location=location or None,
        status=status or None,
        search=search or None,
    )
    summary = get_dashboard_summary(doctors)
    filters = get_filter_options()

    context = {
        "doctors": doctors,
        "summary": summary,
        "filters": filters,
        # Pass current filter values back to template for sticky selects
        "current_rep": rep_id,  # int or None — matches r.id in template
        "current_location": location,
        "current_status": status,
        "current_search": search,
    }

    return render(request, "doctors/doctor_dashboard.html", context)
