"""
Sales entry service layer.

Keeps view logic thin — all business operations centralised here.
"""

from datetime import date

from django.db.models import Sum, F

from doctors.models import DoctorMedicine
from sales.models import SalesEntry


def get_medicines_for_doctor(doctor_id):
    """
    Return list of medicine dicts for a given doctor.
    Used by the AJAX endpoint to populate the medicine dropdown.
    """
    mappings = (
        DoctorMedicine.objects
        .filter(doctor_id=doctor_id, medicine__is_active=True)
        .select_related("medicine")
        .order_by("medicine__name")
    )
    return [
        {
            "id": m.medicine.id,
            "name": str(m.medicine),
            "pts": str(m.medicine.pts),
        }
        for m in mappings
    ]


def get_investments_data_for_doctor(doctor):
    """
    Return list of investment dicts for a given doctor.
    Used by the AJAX endpoint to populate the investment dropdown and ROI summary panel.
    Only returns in_progress investments.
    """
    from doctors.models import Investment
    
    investments = doctor.investments.filter(status=Investment.STATUS_IN_PROGRESS).order_by("-start_date")
    data = []
    for inv in investments:
        data.append({
            "id": inv.id,
            "text": str(inv),
            "amount": float(inv.amount),
            "roi_amount": float(inv.roi_amount),
            "achieved": float(inv.total_sales_value),
            "balance": float(inv.balance),
            "status": inv.get_status_display()
        })
    return data


def create_sales_entry(*, rep, doctor, investment, medicine, quantity):
    """Create and return a new SalesEntry."""
    return SalesEntry.objects.create(
        rep=rep,
        doctor=doctor,
        investment=investment,
        medicine=medicine,
        quantity=quantity,
        entry_date=date.today(),
    )
