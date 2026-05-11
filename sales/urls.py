"""
Sales URL configuration.
"""

from django.urls import path

from . import views

app_name = "sales"

urlpatterns = [
    path("entry/", views.sales_entry_view, name="entry"),
    path(
        "api/medicines/<int:doctor_id>/",
        views.api_medicines_for_doctor,
        name="api_medicines",
    ),
    path("postpaid/", views.postpaid_list_view, name="postpaid"),
    path(
        "postpaid/<int:entry_id>/mark-paid/",
        views.mark_as_paid_view,
        name="mark_paid",
    ),
]
