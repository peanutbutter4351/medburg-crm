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
]
