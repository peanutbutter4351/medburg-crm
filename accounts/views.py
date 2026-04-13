"""
Accounts views — login / logout.
"""

from django.contrib.auth import views as auth_views


class LoginView(auth_views.LoginView):
    template_name = "accounts/login.html"


class LogoutView(auth_views.LogoutView):
    next_page = "accounts:login"
