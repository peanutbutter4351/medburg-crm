"""
Medburg CRM — Production Superuser Creation Command
Management command: python manage.py create_production_superuser

Usage on VPS:
    DJANGO_ADMIN_PASSWORD="YourSecurePassword" \\
    python manage.py create_production_superuser \\
        --username admin \\
        --email admin@medburgmedical.com

All arguments are optional — defaults are shown above.
Password MUST be supplied via env var DJANGO_ADMIN_PASSWORD.

Why a management command instead of build.sh shell heredoc?
  - The heredoc pattern in build.sh is fragile with special chars in passwords
  - It has no error reporting, no idempotency, and bypasses Django's validation
  - Management commands run inside Django's ORM — correct User model, migrations
  - Can be audited, version-controlled, and tested
  - Safe to run multiple times (idempotent by design)
"""

import os
import sys

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Create or update the production admin superuser idempotently."

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default="admin",
            help="Admin username (default: admin)",
        )
        parser.add_argument(
            "--email",
            default="admin@medburgmedical.com",
            help="Admin email address",
        )

    def handle(self, *args, **options):
        User = get_user_model()
        username = options["username"]
        email = options["email"]

        # ── Password from env var only — never accept it as a CLI argument ──
        # Passing passwords as CLI arguments exposes them in `ps aux` output
        # and shell history. Env var is the only safe transport here.
        password = os.environ.get("DJANGO_ADMIN_PASSWORD", "").strip()
        if not password:
            raise CommandError(
                "DJANGO_ADMIN_PASSWORD environment variable is not set.\n"
                "Set it before running:\n"
                "  export DJANGO_ADMIN_PASSWORD='YourSecurePassword'\n"
                "  python manage.py create_production_superuser"
            )

        if len(password) < 12:
            raise CommandError(
                "DJANGO_ADMIN_PASSWORD is too short. "
                "Use at least 12 characters for a production admin account."
            )

        # ── Idempotent create/update ──────────────────────────────────────────
        user, created = User.objects.get_or_create(username=username)

        if created:
            self.stdout.write(f"  Creating new admin user: {username}")
        else:
            self.stdout.write(f"  Updating existing user: {username} (idempotent)")

        user.email = email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.role = "admin"    # ROLE_ADMIN from core.constants
        user.set_password(password)
        user.save()

        action = "created" if created else "updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"✓ Admin user '{username}' {action} successfully.\n"
                f"  Email: {email}\n"
                f"  Role: admin | is_staff: True | is_superuser: True"
            )
        )
