"""
Admin configuration for the accounts app.

Extends Django's built-in UserAdmin to include the custom `role` and
`phone` fields while keeping the standard password-management UX intact.
"""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User admin with role & phone fields integrated."""

    list_display = (
        "username",
        "get_full_name_display",
        "role",
        "phone",
        "is_active",
        "date_joined",
    )
    list_filter = ("role", "is_active", "is_staff", "date_joined")
    search_fields = ("username", "first_name", "last_name", "email", "phone")
    list_per_page = 25
    ordering = ("username",)

    # ── inject custom fields into the standard UserAdmin fieldsets ──
    fieldsets = BaseUserAdmin.fieldsets + (
        (
            "CRM Info",
            {
                "fields": ("role", "phone"),
            },
        ),
    )
    add_fieldsets = BaseUserAdmin.add_fieldsets + (
        (
            "CRM Info",
            {
                "fields": ("role", "phone"),
            },
        ),
    )

    # ── custom column ────────────────────────────────
    @admin.display(description="Full Name")
    def get_full_name_display(self, obj):
        return obj.get_full_name() or "—"
