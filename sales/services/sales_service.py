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
            "ptr": str(m.medicine.ptr),
        }
        for m in mappings
    ]


def get_doctor_roi_summary(doctor):
    """
    Return a dict with ROI summary for a doctor.
    Used to show live ROI info on the sales entry page.
    """
    from doctors.models import Investment

    investments = doctor.investments.all()
    total_investment = sum(inv.amount for inv in investments)
    total_roi_amount = sum(inv.roi_amount for inv in investments)

    achieved = (
        SalesEntry.objects.filter(doctor=doctor).aggregate(
            total=Sum(F("quantity") * F("medicine__ptr"))
        )["total"]
        or 0
    )

    balance = total_roi_amount - achieved

    return {
        "mode": doctor.get_mode_display(),
        "investment": float(total_investment),
        "roi_amount": float(total_roi_amount),
        "achieved": float(achieved),
        "balance": float(balance),
        "is_prepaid": doctor.mode == "prepaid",
    }


def create_sales_entry(*, rep, doctor, medicine, quantity):
    """Create and return a new SalesEntry."""
    return SalesEntry.objects.create(
        rep=rep,
        doctor=doctor,
        medicine=medicine,
        quantity=quantity,
        entry_date=date.today(),
    )
