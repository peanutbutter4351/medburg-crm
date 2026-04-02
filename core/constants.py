"""
Centralised constants for the Medburg CRM.

Import from here instead of hard-coding strings in models / views.
"""

# ──────────────────────────────────────────────
# Doctor mode
# ──────────────────────────────────────────────
DOCTOR_MODE_PREPAID = "prepaid"
DOCTOR_MODE_POSTPAID = "postpaid"

DOCTOR_MODE_CHOICES = [
    (DOCTOR_MODE_PREPAID, "Prepaid"),
    (DOCTOR_MODE_POSTPAID, "Postpaid"),
]

# ──────────────────────────────────────────────
# Doctor type
# ──────────────────────────────────────────────
DOCTOR_TYPE_TRADE = "trade"
DOCTOR_TYPE_HOSPITAL = "hospital"
DOCTOR_TYPE_STOCKING = "stocking"

DOCTOR_TYPE_CHOICES = [
    (DOCTOR_TYPE_TRADE, "Trade"),
    (DOCTOR_TYPE_HOSPITAL, "Hospital"),
    (DOCTOR_TYPE_STOCKING, "Stocking"),
]

# ──────────────────────────────────────────────
# User roles
# ──────────────────────────────────────────────
ROLE_ADMIN = "admin"
ROLE_REP = "rep"

ROLE_CHOICES = [
    (ROLE_ADMIN, "Admin"),
    (ROLE_REP, "Sales Representative"),
]
