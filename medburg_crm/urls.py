"""
Root URL configuration for medburg_crm.
"""

from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect


def root_redirect(request):
    """Redirect root to sales entry for reps, admin for admins."""
    if request.user.is_authenticated:
        if hasattr(request.user, "is_admin_user") and request.user.is_admin_user:
            return redirect("/admin/")
        return redirect("sales:entry")
    return redirect("accounts:login")


urlpatterns = [
    path("", root_redirect, name="root"),
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("doctors/", include("doctors.urls")),
    path("medicines/", include("medicines.urls")),
    path("sales/", include("sales.urls")),
    path("reports/", include("reports.urls")),
]

# Admin site branding
admin.site.site_header = "Medburg CRM Administration"
admin.site.site_title = "Medburg CRM"
admin.site.index_title = "Dashboard"
