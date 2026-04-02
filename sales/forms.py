"""
Sales entry form.

The form only exposes doctor, medicine, and quantity.
Rep and entry_date are set automatically by the view.
"""

from django import forms

from doctors.models import Doctor, DoctorMedicine
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
        fields = ("doctor", "medicine", "quantity")
        widgets = {
            "doctor": forms.Select(
                attrs={
                    "class": "form-select form-select-lg",
                    "id": "id_doctor",
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

        # Medicine starts empty — populated dynamically via JS
        self.fields["medicine"].queryset = Medicine.objects.none()

        # If form is bound (POST) and doctor is submitted, load valid medicines
        if self.data.get("doctor"):
            try:
                doctor_id = int(self.data.get("doctor"))
                medicine_ids = DoctorMedicine.objects.filter(
                    doctor_id=doctor_id
                ).values_list("medicine_id", flat=True)
                self.fields["medicine"].queryset = Medicine.objects.filter(
                    id__in=medicine_ids, is_active=True
                ).order_by("name")
            except (ValueError, TypeError):
                pass

        # Labels
        self.fields["doctor"].label = "Doctor"
        self.fields["medicine"].label = "Medicine"
        self.fields["quantity"].label = "Quantity"

        # Empty label for selects
        self.fields["doctor"].empty_label = "— Select Doctor —"
        self.fields["medicine"].empty_label = "— Select Medicine —"

    def clean(self):
        cleaned_data = super().clean()
        doctor = cleaned_data.get("doctor")
        medicine = cleaned_data.get("medicine")

        if doctor and medicine:
            # Validate the doctor-medicine mapping exists
            if not DoctorMedicine.objects.filter(
                doctor=doctor, medicine=medicine
            ).exists():
                raise forms.ValidationError(
                    "This medicine is not assigned to the selected doctor."
                )

        return cleaned_data
