"""
Sales URL configuration — separates prepaid, postpaid, and AJAX endpoints.
"""

from django.urls import path

from . import views

app_name = "sales"

urlpatterns = [
    # Sales Entry Pages
    path("prepaid/entry/", views.prepaid_sales_entry_view, name="prepaid_entry"),
    path("postpaid/entry/", views.postpaid_sales_entry_view, name="postpaid_entry"),

    # Postpaid Campaign Management Report (existing)
    path("postpaid/report/", views.postpaid_report_view, name="postpaid_report"),
    path("postpaid/campaign/<int:campaign_id>/manage/", views.campaign_management_view, name="campaign_manage"),
    path("postpaid/campaign/<int:campaign_id>/pay/", views.record_payment_view, name="record_payment"),
    path("postpaid/campaign/<int:campaign_id>/commission/", views.update_commission_view, name="update_commission"),
    path("postpaid/campaign/<int:campaign_id>/advance/", views.advance_campaign_status_view, name="advance_status"),

    # MR-9.0: Postpaid Sales Report
    path("postpaid/sales-report/", views.postpaid_sales_report_view, name="postpaid_sales_report"),
    path("postpaid/sales-report/export/", views.export_postpaid_sales_view, name="export_postpaid_sales"),

    # MR-9.0: Settlement Ledger Report
    path("postpaid/settlement-ledger/", views.settlement_ledger_view, name="settlement_ledger"),
    path("postpaid/settlement-ledger/export/", views.export_settlement_ledger_view, name="export_settlement_ledger"),

    # AJAX API Endpoints
    path("api/medicines/<int:doctor_id>/", views.api_medicines_for_doctor, name="api_medicines"),
    path("api/campaign/<int:doctor_id>/<int:month>/<int:year>/", views.api_campaign_for_doctor, name="api_campaign"),
]

