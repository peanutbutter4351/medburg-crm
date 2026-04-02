"""
Doctors URL configuration.
"""

from django.urls import path

from . import views

app_name = "doctors"

urlpatterns = [
    path("dashboard/", views.doctor_dashboard, name="dashboard"),
]
