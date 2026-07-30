from datetime import date, timedelta
from decimal import Decimal

from django.test import TestCase
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model

from doctors.models import Doctor, DoctorMedicine, Investment
from medicines.models import Medicine
from sales.models import SalesEntry
from sales.forms import SalesEntryForm
from doctors.services.doctor_service import get_dashboard_alerts

User = get_user_model()


class InvestmentLifecycleTests(TestCase):
    def setUp(self):
        self.rep = User.objects.create_user(username="rep_test", password="pwd", role="rep")
        self.doctor = Doctor.objects.create(
            name="Dr. Manual Lifecycle",
            mode="prepaid",
            assigned_rep=self.rep,
            is_active=True,
        )
        self.medicine = Medicine.objects.create(
            name="Med Lifecycle Test",
            pts=Decimal("100.00"),
            ptr=Decimal("80.00"),
            mrp=Decimal("120.00"),
            is_active=True,
        )
        DoctorMedicine.objects.create(doctor=self.doctor, medicine=self.medicine)

        self.investment = Investment.objects.create(
            doctor=self.doctor,
            amount=Decimal("1000.00"),
            roi_ratio=Decimal("2.00"),  # Target ROI = 2000.00
            start_date=date.today() - timedelta(days=10),
            status=Investment.STATUS_IN_PROGRESS,
        )

    def test_investment_does_not_auto_complete_when_roi_target_reached(self):
        """
        Verify that an investment remains IN_PROGRESS even after sales entries
        meet or exceed the target ROI (balance <= 0).
        """
        self.assertEqual(self.investment.status, Investment.STATUS_IN_PROGRESS)
        self.assertEqual(self.investment.balance, Decimal("2000.00"))

        # Log sales reaching exactly 2000.00 target
        SalesEntry.objects.create(
            rep=self.rep,
            doctor=self.doctor,
            investment=self.investment,
            medicine=self.medicine,
            quantity=20,  # 20 * 100 = 2000
            entry_date=date.today(),
        )

        self.investment.refresh_from_db()
        self.assertEqual(self.investment.balance, Decimal("0.00"))
        # Status MUST remain in_progress
        self.assertEqual(self.investment.status, Investment.STATUS_IN_PROGRESS)

    def test_sales_rep_can_log_sales_on_overachieved_investment(self):
        """
        Verify sales reps can continue adding sales to an investment after ROI exceeds target.
        """
        # First entry: achieve target (balance = 0)
        SalesEntry.objects.create(
            rep=self.rep,
            doctor=self.doctor,
            investment=self.investment,
            medicine=self.medicine,
            quantity=20,
            entry_date=date.today(),
        )

        # Second entry: over-achieve (balance = -1000)
        entry2 = SalesEntry.objects.create(
            rep=self.rep,
            doctor=self.doctor,
            investment=self.investment,
            medicine=self.medicine,
            quantity=10,  # 10 * 100 = 1000
            entry_date=date.today(),
        )

        self.investment.refresh_from_db()
        self.assertEqual(self.investment.balance, Decimal("-1000.00"))
        self.assertEqual(self.investment.status, Investment.STATUS_IN_PROGRESS)
        self.assertEqual(entry2.value_at_sale, Decimal("1000.00"))

    def test_manual_completion_blocked_when_balance_positive(self):
        """
        Verify an admin cannot manually set status = COMPLETED if balance > 0.
        """
        self.assertTrue(self.investment.balance > 0)
        self.investment.status = Investment.STATUS_COMPLETED

        with self.assertRaises(ValidationError) as ctx:
            self.investment.clean()

        self.assertIn("status", ctx.exception.message_dict)

    def test_manual_completion_allowed_when_balance_less_than_or_equal_zero(self):
        """
        Verify an admin CAN manually set status = COMPLETED once balance <= 0.
        """
        # Log sales to achieve target balance <= 0
        SalesEntry.objects.create(
            rep=self.rep,
            doctor=self.doctor,
            investment=self.investment,
            medicine=self.medicine,
            quantity=25,  # 2500 achieved -> balance = -500
            entry_date=date.today(),
        )

        self.investment.refresh_from_db()
        self.assertEqual(self.investment.balance, Decimal("-500.00"))

        # Admin changes status to COMPLETED
        self.investment.status = Investment.STATUS_COMPLETED
        self.investment.clean()  # Should not raise error
        self.investment.save()

        self.investment.refresh_from_db()
        self.assertEqual(self.investment.status, Investment.STATUS_COMPLETED)

    def test_completed_investment_hidden_from_dropdown_and_blocks_new_sales(self):
        """
        Verify that once an investment is manually marked COMPLETED:
        1. It is excluded from SalesEntryForm investment dropdown.
        2. New sales entries against it raise ValidationError.
        """
        # Over-achieve target
        SalesEntry.objects.create(
            rep=self.rep,
            doctor=self.doctor,
            investment=self.investment,
            medicine=self.medicine,
            quantity=20,
            entry_date=date.today(),
        )

        # Before manual completion: appears in form dropdown
        form_before = SalesEntryForm(data={"doctor": str(self.doctor.id)}, rep=self.rep)
        self.assertIn(self.investment, form_before.fields["investment"].queryset)

        # Admin marks completed
        self.investment.status = Investment.STATUS_COMPLETED
        self.investment.save()

        # After manual completion: excluded from form dropdown
        form_after = SalesEntryForm(data={"doctor": str(self.doctor.id)}, rep=self.rep)
        self.assertNotIn(self.investment, form_after.fields["investment"].queryset)

        # Attempting to save a new sale against completed investment fails
        new_sale = SalesEntry(
            rep=self.rep,
            doctor=self.doctor,
            investment=self.investment,
            medicine=self.medicine,
            quantity=5,
            entry_date=date.today(),
        )
        with self.assertRaises(ValidationError):
            new_sale.clean()

    def test_no_prepaid_overrun_alert_on_dashboard(self):
        """
        Verify that active investments with over-achieved ROI (negative balance)
        do NOT trigger Prepaid Overrun notifications in dashboard alerts.
        """
        # Create sales entry exceeding target ROI
        SalesEntry.objects.create(
            rep=self.rep,
            doctor=self.doctor,
            investment=self.investment,
            medicine=self.medicine,
            quantity=30,  # 30 * 100 = 3000 achieved (exceeds 2000 target by 1000)
            entry_date=date.today(),
        )
        self.investment.refresh_from_db()
        self.assertTrue(self.investment.balance < 0)

        alerts = get_dashboard_alerts()
        overrun_alerts = [a for a in alerts if "Overrun" in a.get("message", "")]
        self.assertEqual(len(overrun_alerts), 0)

