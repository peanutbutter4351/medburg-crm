"""
Custom User model with role-based access.

Roles
─────
admin  – full access to admin panel, reports, all CRUD
rep    – limited access: sales entry page only
"""

from django.contrib.auth.models import AbstractUser
from django.db import models

from core.constants import ROLE_ADMIN, ROLE_CHOICES, ROLE_REP


class User(AbstractUser):
    """
    Extends Django's AbstractUser with a role field.

    Using AbstractUser (not AbstractBaseUser) so we retain the full
    auth pipeline — login, password hashing, permissions — out of
    the box.
    """

    role = models.CharField(
        max_length=10,
        choices=ROLE_CHOICES,
        default=ROLE_REP,
        db_index=True,
        help_text="Determines dashboard access level.",
    )
    phone = models.CharField(
        max_length=15,
        blank=True,
        help_text="Optional contact number.",
    )

    class Meta:
        verbose_name = "User"
        verbose_name_plural = "Users"
        ordering = ["username"]

    def __str__(self):
        return f"{self.get_full_name() or self.username} ({self.get_role_display()})"

    # ── convenience helpers ──────────────────────────
    @property
    def is_admin_user(self):
        return self.role == ROLE_ADMIN

    @property
    def is_rep(self):
        return self.role == ROLE_REP
