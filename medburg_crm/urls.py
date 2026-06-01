"""
Root URL configuration for medburg_crm.
"""

from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect


def root_redirect(request):
    """Redirect root to dashboard for authenticated users."""
    if request.user.is_authenticated:
        return redirect("doctors:dashboard")
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

# ── Media file serving (development only) ───────────────────────────────────
# When DEBUG=True, Django's dev server serves uploaded media files.
# In production, Nginx handles /media/ directly — static() returns [] when
# DEBUG=False, so this has zero cost in production.
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

# Admin site branding
admin.site.site_header = "Medburg CRM Administration"
admin.site.site_title = "Medburg CRM"
admin.site.index_title = "Dashboard"
