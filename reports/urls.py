"""Reports URL configuration."""

from django.urls import path

from . import views

app_name = "reports"

urlpatterns = [
    path("", views.report_view, name="report"),
    path("export/", views.export_report_view, name="export"),
    path("prepaid-doctors/", views.prepaid_doctor_report_view, name="prepaid_doctor_report"),
    path("prepaid-doctors/export/", views.export_prepaid_doctor_report_view, name="export_prepaid_doctor_report"),
]
