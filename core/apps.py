"""
core/apps.py
━━━━━━━━━━━━
Django AppConfig for the core infrastructure app.

'core' is the shared foundation for all business apps — it owns:
  - BaseModel          (abstract timestamped base)
  - ImportLog          (import audit model)
  - BaseExcelImporter  (reusable Excel import engine)
  - constants          (shared choice constants)
  - decorators         (RBAC/role decorators)
  - services           (shared utility services)

This AppConfig registers 'core' with Django's app registry so that:
  - ImportLog migrations are discovered and applied
  - Django admin picks up core/admin.py
  - The app label is explicit and stable
"""

from django.apps import AppConfig


class CoreConfig(AppConfig):
    # Use BigAutoField consistently with the project default
    default_auto_field = "django.db.models.BigAutoField"

    # Module path — must match the package directory name
    name = "core"

    # Human-readable label shown in Django admin and error messages
    verbose_name = "Core Infrastructure"
