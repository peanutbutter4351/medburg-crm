"""Reports URL configuration."""

from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.report_view, name="report"),
    path("export/", views.export_report_view, name="export"),
]
