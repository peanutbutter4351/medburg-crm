# Security

Medburg CRM employs strict role-based access control and environment-driven security configurations.

## Authentication & Authorization

The application uses a custom user model `accounts.User` featuring a `role` field.

- **Admin (`role='admin'`):** Full access to the CRM, including financial ledgers, company-wide reporting, and campaign settlements.
- **Rep (`role='rep'`):** Restricted access. Can only log sales, view their assigned doctors, and view their own performance dashboard.

### The `@admin_required` Decorator

Located in `core.decorators`, this is the primary mechanism for protecting sensitive views.

```python
from core.decorators import admin_required

@admin_required
def postpaid_doctor_report_view(request):
    # This code is unreachable by Reps
```

Any view exposing financial aggregates, investments, or campaigns MUST be wrapped in this decorator.

## Production Security Configuration

Django settings are split. `settings/production.py` enforces secure defaults that rely on Nginx and environment variables.

### `.env.prod` Variables

- `DJANGO_SECRET_KEY`: Must be a long, cryptographically secure random string.
- `DJANGO_ALLOWED_HOSTS`: Must strictly list the production domain names (e.g., `crm.medburg.com`).
- `POSTGRES_PASSWORD`: Secure database credentials.

### SSL and HTTPS

SSL termination is handled by Nginx. Django is configured to trust the proxy and enforce secure cookies.

These settings are conditionally enabled via `.env.prod`:
- `DJANGO_SECURE_SSL_REDIRECT=True`
- `DJANGO_SESSION_COOKIE_SECURE=True`
- `DJANGO_CSRF_COOKIE_SECURE=True`
- `DJANGO_HSTS_SECONDS=31536000`

> [!IMPORTANT]
> Never set `DJANGO_DEBUG=True` in production. Doing so exposes detailed tracebacks and environment variables (including database passwords) to end-users if an error occurs.
