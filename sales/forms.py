"""
Sales entry form.

The form only exposes doctor, medicine, and quantity.
Rep and entry_date are set automatically by the view.
"""

from django import forms

from doctors.models import Doctor, DoctorMedicine, Investment
from medicines.models import Medicine

from .models import SalesEntry


class SalesEntryForm(forms.ModelForm):
    """
    Minimal form for fast data entry by sales reps.

    • doctor  — filtered to rep's assigned doctors in __init__
    • medicine — starts empty; populated via AJAX when doctor is selected
    • quantity — simple number input
    """

    class Meta:
        model = SalesEntry
        fields = ("doctor", "investment", "medicine", "quantity")
        widgets = {
            "doctor": forms.Select(
                attrs={
                    "class": "form-select form-select-lg",
                    "id": "id_doctor",
                },
            ),
            "investment": forms.Select(
                attrs={
                    "class": "form-select form-select-lg",
                    "id": "id_investment",
                },
            ),
            "medicine": forms.Select(
                attrs={
                    "class": "form-select form-select-lg",
                    "id": "id_medicine",
                },
            ),
            "quantity": forms.NumberInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "id": "id_quantity",
                    "min": "1",
                    "placeholder": "Enter quantity",
                    "autofocus": False,
                },
            ),
        }

    def __init__(self, *args, rep=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rep = rep

        # Filter doctors to those assigned to this rep
        if rep:
            self.fields["doctor"].queryset = Doctor.objects.filter(
                assigned_rep=rep, is_active=True
            ).order_by("name")
        else:
            self.fields["doctor"].queryset = Doctor.objects.filter(
                is_active=True
            ).order_by("name")

        # Medicine and Investment start empty — populated dynamically via JS
        self.fields["medicine"].queryset = Medicine.objects.none()
        self.fields["investment"].queryset = Investment.objects.none()
        self.fields["investment"].required = False

        # If form is bound (POST) and doctor is submitted, load valid medicines and investments
        if self.data.get("doctor"):
            try:
                doctor_id = int(self.data.get("doctor"))
                medicine_ids = DoctorMedicine.objects.filter(
                    doctor_id=doctor_id
                ).values_list("medicine_id", flat=True)
                self.fields["medicine"].queryset = Medicine.objects.filter(
                    id__in=medicine_ids, is_active=True
                ).order_by("name")
                
                self.fields["investment"].queryset = Investment.objects.filter(
                    doctor_id=doctor_id, status=Investment.STATUS_IN_PROGRESS
                ).order_by("-start_date")
            except (ValueError, TypeError):
                pass

        # Labels
        self.fields["doctor"].label = "Doctor"
        self.fields["investment"].label = "Investment"
        self.fields["medicine"].label = "Medicine"
        self.fields["quantity"].label = "Quantity"

        # Empty label for selects
        self.fields["doctor"].empty_label = "— Select Doctor —"
        self.fields["investment"].empty_label = "— Select Investment —"
        self.fields["medicine"].empty_label = "— Select Medicine —"

    def clean(self):
        cleaned_data = super().clean()
        doctor = cleaned_data.get("doctor")
        medicine = cleaned_data.get("medicine")
        investment = cleaned_data.get("investment")
        
        if doctor:
            if doctor.mode == "prepaid" and not investment:
                self.add_error("investment", "Investment is required for prepaid doctors.")
            if doctor.mode != "prepaid" and investment:
                self.add_error("investment", "Postpaid doctors do not use investments.")

        if doctor and medicine:
            # Validate the doctor-medicine mapping exists
            if not DoctorMedicine.objects.filter(
                doctor=doctor, medicine=medicine
            ).exists():
                self.add_error("medicine", "This medicine is not assigned to the selected doctor.")

        if investment:
            if investment.status == "completed":
                self.add_error("investment", "Completed investments cannot accept new sales entries.")

        return cleaned_data
