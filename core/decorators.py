"""
Access control decorators for Medburg CRM.

Use these instead of bare @login_required on admin-only views.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.http import HttpResponseForbidden


def admin_required(view_func):
    """
    Decorator that ensures the user is authenticated AND has the admin role.

    Returns 403 Forbidden for authenticated non-admin users.
    Redirects unauthenticated users to the login page.

    Usage:
        @admin_required
        def my_admin_view(request):
            ...
    """

    @wraps(view_func)
    @login_required
    def _wrapped(request, *args, **kwargs):
        if not getattr(request.user, "is_admin_user", False):
            return HttpResponseForbidden(
                "You do not have permission to access this page."
            )
        return view_func(request, *args, **kwargs)

    return _wrapped
