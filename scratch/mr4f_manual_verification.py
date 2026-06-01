import os
import sys
import django
from decimal import Decimal

# Insert project directory to resolve medburg_crm imports
sys.path.insert(0, r"d:\Dev\medburg_crm")

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "medburg_crm.settings.development")
django.setup()

from django.template.loader import render_to_string
from django.contrib.auth import get_user_model

User = get_user_model()

class MockDoctor:
    def __init__(self, name, hospital=None):
        self.name = name
        self.hospital = hospital

class MockCampaign:
    def __init__(self, id, doctor, month, year, status, commission_percentage, total_sales_value, total_commission, paid_amount):
        self.id = id
        self.doctor = doctor
        self.month = month
        self.year = year
        self.status = status
        self.commission_percentage = commission_percentage
        self.total_sales_value = total_sales_value
        self.total_commission = total_commission
        self.paid_amount = paid_amount

    @property
    def outstanding_balance(self):
        return self.total_commission - self.paid_amount

# Create mock data
doc1 = MockDoctor("Dr. Awaiting", "Hospital A")
doc2 = MockDoctor("Dr. Open", "Hospital B")
doc3 = MockDoctor("Dr. Partial", "Hospital C")
doc4 = MockDoctor("Dr. Ready", "Hospital D")
doc5 = MockDoctor("Dr. Settled", "Hospital E")
doc6 = MockDoctor("Dr. Locked", "Hospital F")

campaigns = [
    MockCampaign(1, doc1, 6, 2026, 'awaiting_commission', None, Decimal("1000"), Decimal("0"), Decimal("0")),
    MockCampaign(2, doc2, 6, 2026, 'open', Decimal("10"), Decimal("5000"), Decimal("500"), Decimal("0")),
    MockCampaign(3, doc3, 6, 2026, 'partial', Decimal("10"), Decimal("10000"), Decimal("1000"), Decimal("400")),
    MockCampaign(4, doc4, 6, 2026, 'partial', Decimal("10"), Decimal("10000"), Decimal("1000"), Decimal("1000")),
    MockCampaign(5, doc5, 6, 2026, 'settled', Decimal("10"), Decimal("10000"), Decimal("1000"), Decimal("1000")),
    MockCampaign(6, doc6, 6, 2026, 'locked', Decimal("10"), Decimal("10000"), Decimal("1000"), Decimal("1000")),
]

class MockUser:
    is_authenticated = True
    is_admin_user = True
    first_name = "Admin"
    username = "admin"
    role = "admin"

mock_user = MockUser()

# Render template with campaigns
context_with_data = {
    "user": mock_user,
    "active_campaigns": campaigns,
    "unified_feed": [
        {
            "type": "prepaid",
            "obj": {
                "entry_date": "2026-06-01",
                "doctor": MockDoctor("Dr. Prepaid Feed"),
                "medicine": {"name": "Prepaid Med"},
                "quantity": 10,
                "value_at_sale": Decimal("1000"),
                "rep": {"get_full_name": "John Doe", "username": "johndoe"}
            }
        },
        {
            "type": "postpaid",
            "obj": {
                "entry_date": "2026-06-01",
                "campaign": {"doctor": MockDoctor("Dr. Postpaid Feed")},
                "medicine": {"name": "Postpaid Med"},
                "quantity": 5,
                "value_at_sale": Decimal("500"),
                "rep": {"get_full_name": "Jane Smith", "username": "janesmith"}
            }
        }
    ],
    "prepaid_metrics": {
        "recovery_rate": Decimal("85.4"),
        "completed_last_30d": 3
    },
    "summary": {
        "total_doctors": 5,
        "total_investment": Decimal("50000"),
        "total_achieved": Decimal("40000"),
        "total_balance": Decimal("10000")
    },
    "postpaid_summary": {
        "active_campaigns_count": 5,
        "monthly_sales": Decimal("25000"),
        "total_commission": Decimal("2500"),
        "total_outstanding": Decimal("1000")
    }
}

html_output = render_to_string("doctors/admin_dashboard.html", context_with_data)

# Print/verify check results
def check(label, condition):
    status = "PASS" if condition else "FAIL"
    mark = "OK" if condition else "ERR"
    print(f"  [{mark}] {label}: {status}")
    return condition

print("=" * 60)
print("MR-4F-D MANUAL VERIFICATION REPORT (HTML RENDERING)")
print("=" * 60)
with open("scratch/rendered.html", "w", encoding="utf-8") as f:
    f.write(html_output)

check("Awaiting Commission badge rendered", "Awaiting Commission" in html_output and "crm-badge pending" in html_output)
check("Open badge rendered", "Open" in html_output and "crm-badge in-progress" in html_output)
check("Partial badge rendered", "Partial" in html_output and "color: #1d4ed8;" in html_output)
check("Ready To Settle badge rendered", "Ready To Settle" in html_output and "crm-badge completed" in html_output)
check("Settled badge rendered", "Settled" in html_output and "crm-badge completed" in html_output)
check("Locked badge rendered", "Locked" in html_output and "crm-badge no-investment" in html_output and "bi-lock-fill" in html_output)

# Verify empty states
context_empty = {
    "user": mock_user,
    "active_campaigns": [],
    "unified_feed": [],
    "prepaid_metrics": {
        "recovery_rate": Decimal("0.0"),
        "completed_last_30d": 0
    },
    "summary": {
        "total_doctors": 0,
        "total_investment": Decimal("0"),
        "total_achieved": Decimal("0"),
        "total_balance": Decimal("0")
    },
    "postpaid_summary": {
        "active_campaigns_count": 0,
        "monthly_sales": Decimal("0"),
        "total_commission": Decimal("0"),
        "total_outstanding": Decimal("0")
    }
}

html_empty = render_to_string("doctors/admin_dashboard.html", context_empty)
print(f"Rendered Empty HTML length: {len(html_empty)}")
with open("scratch/rendered_empty.html", "w", encoding="utf-8") as f:
    f.write(html_empty)

check("Empty postpaid campaign grid message rendered", "No active postpaid campaigns." in html_empty)
check("Empty activity feed message rendered", "No recent sales activity." in html_empty)
print("=" * 60)
