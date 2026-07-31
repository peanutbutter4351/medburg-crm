"""
Doctor views — ROI Dashboard.
"""

from django.contrib.auth.decorators import login_required
from django.shortcuts import render

from core.constants import ROLE_ADMIN
from .services.doctor_service import (
    get_dashboard_queryset,
    get_dashboard_summary,
    get_filter_options,
    get_postpaid_dashboard_summary,
    get_dashboard_alerts,
    get_rep_dashboard_data,
    get_prepaid_admin_metrics,
    get_unified_activity_feed,
    get_active_postpaid_campaigns,
)
from sales.services.analytics_service import (
    get_admin_dashboard_analytics,
    get_rep_dashboard_analytics,
    get_home_kpis,
)


@login_required
def doctor_dashboard(request):
    """
    Dashboard view that routes users based on their role:
    - Admins see the company-wide Prepaid and Postpaid Dashboards.
    - Reps see their personal Prepaid and Postpaid performance summary.
    """
    if request.user.role == ROLE_ADMIN:
        # ── Collect filter params ────────────────────────
        rep_id_raw = request.GET.get("rep", "")
        try:
            rep_id = int(rep_id_raw) if rep_id_raw else None
        except (ValueError, TypeError):
            rep_id = None
        location = request.GET.get("location", "")
        status   = request.GET.get("status", "")
        search   = request.GET.get("search", "").strip()
        section  = request.GET.get("section", "home")
        if section not in ["home", "prepaid", "postpaid"]:
            section = "home"

        # ── Fetch Prepaid data via service ───────────────────────
        doctors = get_dashboard_queryset(
            rep_id=rep_id or None,
            location=location or None,
            status=status or None,
            search=search or None,
        )
        summary = get_dashboard_summary(doctors)
        filters = get_filter_options()

        # ── Fetch Postpaid summary and Alerts ────────────────────
        postpaid_summary = get_postpaid_dashboard_summary()
        alerts = get_dashboard_alerts()
        
        # New MR-4F metrics and feeds
        prepaid_metrics = get_prepaid_admin_metrics()
        unified_feed = get_unified_activity_feed()
        active_campaigns = get_active_postpaid_campaigns()

        # MR-9.2 Analytics
        admin_analytics = get_admin_dashboard_analytics()
        home_kpis = get_home_kpis()

        context = {
            "doctors": doctors,
            "summary": summary,
            "filters": filters,
            "postpaid_summary": postpaid_summary,
            "prepaid_metrics": prepaid_metrics,
            "unified_feed": unified_feed,
            "active_campaigns": active_campaigns,
            "alerts": alerts,
            "admin_analytics": admin_analytics,
            "home_kpis": home_kpis,
            # Pass current filter values back to template for sticky selects
            "current_rep": rep_id,
            "current_location": location,
            "current_status": status,
            "current_search": search,
            "current_section": section,
        }
        return render(request, "doctors/admin_dashboard.html", context)
    else:
        # Rep dashboard view
        from datetime import date
        rep_data = get_rep_dashboard_data(request.user)
        rep_analytics = get_rep_dashboard_analytics(request.user)
        context = {
            "rep_data": rep_data,
            "rep_analytics": rep_analytics,
            "today": date.today(),
        }
        return render(request, "doctors/rep_dashboard.html", context)
