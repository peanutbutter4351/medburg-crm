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

# ──────────────────────────────────────────────
# Postpaid payout type
# ──────────────────────────────────────────────
PAYOUT_TYPE_RANGE = "range"
PAYOUT_TYPE_MONTHLY = "monthly"
PAYOUT_TYPE_CAMPAIGN = "campaign"

PAYOUT_TYPE_CHOICES = [
    (PAYOUT_TYPE_RANGE, "Date Range"),
    (PAYOUT_TYPE_MONTHLY, "Monthly"),
    (PAYOUT_TYPE_CAMPAIGN, "Campaign"),
]

# ──────────────────────────────────────────────
# Payment status
# ──────────────────────────────────────────────
PAYMENT_STATUS_UNPAID = "unpaid"
PAYMENT_STATUS_PARTIAL = "partial"
PAYMENT_STATUS_PAID = "paid"

PAYMENT_STATUS_CHOICES = [
    (PAYMENT_STATUS_UNPAID, "Unpaid"),
    (PAYMENT_STATUS_PARTIAL, "Partially Paid"),
    (PAYMENT_STATUS_PAID, "Fully Paid"),
]

