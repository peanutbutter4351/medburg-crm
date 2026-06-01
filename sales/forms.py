"""
Sales forms — Prepaid and Postpaid entry forms, commission configuration, and payments.
"""

import datetime
from django import forms

from doctors.models import Doctor, DoctorMedicine, Investment
from medicines.models import Medicine
from .models import SalesEntry, PostpaidCampaign, CampaignPayment


class SalesEntryForm(forms.ModelForm):
    """
    Form for Prepaid Sales Entry.
    Restricts doctor choices to prepaid mode only and enforces investment assignment.
    """

    class Meta:
        model = SalesEntry
        fields = ("doctor", "investment", "medicine", "quantity", "notes")
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
                },
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Optional remarks...",
                }
            )
        }

    def __init__(self, *args, rep=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rep = rep

        # Filter doctors to active prepaid doctors assigned to this rep
        if rep:
            self.fields["doctor"].queryset = Doctor.objects.filter(
                assigned_rep=rep, is_active=True, mode="prepaid"
            ).order_by("name")
        else:
            self.fields["doctor"].queryset = Doctor.objects.filter(
                is_active=True, mode="prepaid"
            ).order_by("name")

        # Start dynamic fields empty
        self.fields["medicine"].queryset = Medicine.objects.none()
        self.fields["investment"].queryset = Investment.objects.none()
        
        # Enforce that investment is required for Prepaid
        self.fields["investment"].required = True

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

        self.fields["doctor"].empty_label = "— Select Doctor —"
        self.fields["investment"].empty_label = "— Select Investment —"
        self.fields["medicine"].empty_label = "— Select Medicine —"

    def clean(self):
        cleaned_data = super().clean()
        doctor = cleaned_data.get("doctor")
        medicine = cleaned_data.get("medicine")
        investment = cleaned_data.get("investment")

        if doctor:
            if not investment:
                self.add_error("investment", "Investment is required for prepaid doctors.")

        if doctor and medicine:
            if not DoctorMedicine.objects.filter(
                doctor=doctor, medicine=medicine
            ).exists():
                self.add_error("medicine", "This medicine is not assigned to the selected doctor.")

        if investment:
            if investment.status == "completed":
                self.add_error("investment", "Completed investments cannot accept new sales entries.")

        return cleaned_data


class PostpaidSalesEntryForm(forms.Form):
    """
    Form for Postpaid Sales Entry.
    Reps enter Doctor (postpaid only), Month, Year, Medicine, Quantity, and Notes.
    The Campaign is resolved or created automatically behind the scenes.
    """

    doctor = forms.ModelChoiceField(
        queryset=Doctor.objects.none(),
        widget=forms.Select(attrs={"class": "form-select form-select-lg", "id": "id_doctor"}),
        empty_label="— Select Doctor —"
    )
    month = forms.ChoiceField(
        choices=[(i, f"{i:02d}") for i in range(1, 13)],
        widget=forms.Select(attrs={"class": "form-select form-select-lg", "id": "id_month"})
    )
    year = forms.ChoiceField(
        choices=[],
        widget=forms.Select(attrs={"class": "form-select form-select-lg", "id": "id_year"})
    )
    medicine = forms.ModelChoiceField(
        queryset=Medicine.objects.none(),
        widget=forms.Select(attrs={"class": "form-select form-select-lg", "id": "id_medicine"}),
        empty_label="— Select Medicine —"
    )
    quantity = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={"class": "form-control form-control-lg", "id": "id_quantity", "placeholder": "Enter quantity"})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "placeholder": "Optional remarks..."})
    )

    def __init__(self, *args, rep=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.rep = rep

        # Filter doctors to active postpaid doctors assigned to this rep
        if rep:
            self.fields["doctor"].queryset = Doctor.objects.filter(
                assigned_rep=rep, is_active=True, mode="postpaid"
            ).order_by("name")
        else:
            self.fields["doctor"].queryset = Doctor.objects.filter(
                is_active=True, mode="postpaid"
            ).order_by("name")

        # Setup Year choices dynamically around current year
        current_year = datetime.date.today().year
        self.fields["year"].choices = [(y, str(y)) for y in range(current_year - 1, current_year + 3)]

        # Set default values to current month and year
        self.fields["month"].initial = str(datetime.date.today().month)
        self.fields["year"].initial = str(current_year)

        # Start medicine options empty
        self.fields["medicine"].queryset = Medicine.objects.none()

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

    def clean(self):
        cleaned_data = super().clean()
        doctor = cleaned_data.get("doctor")
        medicine = cleaned_data.get("medicine")

        if doctor and medicine:
            if not DoctorMedicine.objects.filter(
                doctor=doctor, medicine=medicine
            ).exists():
                self.add_error("medicine", "This medicine is not assigned to the selected doctor.")

        return cleaned_data


class CampaignCommissionForm(forms.ModelForm):
    """Form for Admins to explicitly set the commission percentage of a campaign."""

    class Meta:
        model = PostpaidCampaign
        fields = ("commission_percentage",)
        widgets = {
            "commission_percentage": forms.NumberInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "step": "0.01",
                    "min": "0.00",
                    "max": "100.00",
                    "placeholder": "e.g. 15.00",
                }
            )
        }


class CampaignPaymentForm(forms.ModelForm):
    """Form for Admins to record a ledger payment against a campaign."""

    class Meta:
        model = CampaignPayment
        fields = ("amount", "payment_date", "reference", "notes")
        widgets = {
            "amount": forms.NumberInput(
                attrs={
                    "class": "form-control form-control-lg",
                    "step": "0.01",
                    "placeholder": "Enter payment amount",
                }
            ),
            "payment_date": forms.DateInput(
                attrs={
                    "class": "form-control",
                    "type": "date",
                }
            ),
            "reference": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Cheque, Transaction ID, Reference…",
                }
            ),
            "notes": forms.Textarea(
                attrs={
                    "class": "form-control",
                    "rows": 3,
                    "placeholder": "Payment remarks…",
                }
            ),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["payment_date"].initial = datetime.date.today().strftime("%Y-%m-%d")
