from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from doctors.models import Doctor, Investment
from medicines.models import Medicine
from sales.models import SalesEntry
from reports.services.report_service import (
    get_prepaid_doctor_report_queryset,
    get_prepaid_doctor_report_summary,
)

User = get_user_model()


class PrepaidDoctorReportTests(TestCase):
    def setUp(self):
        # Create users
        self.admin = User.objects.create_user(username="admin", role="admin")
        self.rep = User.objects.create_user(username="rep", role="rep")

        # Create medicines
        self.med1 = Medicine.objects.create(
            name="Medicine A",
            brand="Brand A",
            pts=Decimal("100.00"),
            ptr=Decimal("120.00"),
            mrp=Decimal("150.00"),
            is_active=True,
        )
        self.med2 = Medicine.objects.create(
            name="Medicine B",
            brand="Brand B",
            pts=Decimal("200.00"),
            ptr=Decimal("240.00"),
            mrp=Decimal("300.00"),
            is_active=True,
        )

        # Create doctors
        self.doctor1 = Doctor.objects.create(
            name="Doctor John",
            mode="prepaid",
            location="New York",
            is_active=True,
        )
        self.doctor2 = Doctor.objects.create(
            name="Doctor Alice",
            mode="prepaid",
            location="Boston",
            is_active=True,
        )

        # Create investments for Doctor 1 (Multiple: In Progress & Completed)
        self.inv1 = Investment.objects.create(
            doctor=self.doctor1,
            amount=Decimal("1000.00"),
            roi_ratio=Decimal("2.0"),
            start_date=date.today() - timedelta(days=30),
            status=Investment.STATUS_IN_PROGRESS,
        )
        self.inv2 = Investment.objects.create(
            doctor=self.doctor1,
            amount=Decimal("2000.00"),
            roi_ratio=Decimal("1.5"),
            start_date=date.today() - timedelta(days=60),
            status=Investment.STATUS_IN_PROGRESS,
        )

        # Create investment for Doctor 2 (In Progress only)
        self.inv3 = Investment.objects.create(
            doctor=self.doctor2,
            amount=Decimal("5000.00"),
            roi_ratio=Decimal("1.2"),
            start_date=date.today() - timedelta(days=10),
            status=Investment.STATUS_IN_PROGRESS,
        )

        # Create Sales Entries (Returns Received)
        # Sales Entry for Doctor 1 under Inv 1 (Medicine A)
        self.sale1 = SalesEntry.objects.create(
            rep=self.rep,
            doctor=self.doctor1,
            investment=self.inv1,
            medicine=self.med1,
            quantity=5,  # 5 * 100 = ₹500
            entry_date=date.today() - timedelta(days=15),
        )
        # Sales Entry for Doctor 1 under Inv 2 (Medicine B)
        self.sale2 = SalesEntry.objects.create(
            rep=self.rep,
            doctor=self.doctor1,
            investment=self.inv2,
            medicine=self.med2,
            quantity=10,  # 10 * 200 = ₹2000
            entry_date=date.today() - timedelta(days=45),
        )
        
        # Mark inv2 as completed after creating sales entry
        self.inv2.status = Investment.STATUS_COMPLETED
        self.inv2.save()
        # Sales Entry for Doctor 2 under Inv 3 (Medicine A)
        self.sale3 = SalesEntry.objects.create(
            rep=self.rep,
            doctor=self.doctor2,
            investment=self.inv3,
            medicine=self.med1,
            quantity=3,  # 3 * 100 = ₹300
            entry_date=date.today() - timedelta(days=5),
        )

    def test_access_control(self):
        """Verify report page and export are restricted to admin only."""
        report_url = reverse("reports:prepaid_doctor_report")
        export_url = reverse("reports:export_prepaid_doctor_report")

        # Rep (Non-admin) -> 403 Forbidden
        self.client.force_login(self.rep)
        response = self.client.get(report_url)
        self.assertEqual(response.status_code, 403)
        response_export = self.client.get(export_url)
        self.assertEqual(response_export.status_code, 403)

        # Admin -> 200 OK
        self.client.force_login(self.admin)
        response = self.client.get(report_url)
        self.assertEqual(response.status_code, 200)
        response_export = self.client.get(export_url)
        self.assertEqual(response_export.status_code, 200)

    def test_aggregation_without_filters(self):
        """Verify correct consolidated doctor-wise totals (Completed + In Progress)."""
        qs = get_prepaid_doctor_report_queryset()
        self.assertEqual(qs.count(), 2)

        # Doctor Alice (A-Z sorting check: Alice is first in name order)
        alice = qs.filter(pk=self.doctor2.pk).first()
        self.assertEqual(alice.total_investment, Decimal("5000.00"))
        self.assertEqual(alice.total_expected_return, Decimal("6000.00"))
        self.assertEqual(alice.total_returns, Decimal("300.00"))

        # Doctor John (has multiple investments: 1000 + 2000 = 3000, expected: 2000 + 3000 = 5000)
        john = qs.filter(pk=self.doctor1.pk).first()
        self.assertEqual(john.total_investment, Decimal("3000.00"))
        self.assertEqual(john.total_expected_return, Decimal("5000.00"))
        self.assertEqual(john.total_returns, Decimal("2500.00"))

        # Summary check
        summary = get_prepaid_doctor_report_summary(qs)
        self.assertEqual(summary["total_doctors"], 2)
        self.assertEqual(summary["total_investment"], Decimal("8000.00"))
        self.assertEqual(summary["total_expected_return"], Decimal("11000.00"))
        self.assertEqual(summary["total_returns"], Decimal("2800.00"))
        # Average Recovery %: (2800 / 11000) * 100 = 25.45...%
        self.assertAlmostEqual(float(summary["average_recovery_pct"]), 25.4545, places=2)

    def test_filter_by_doctor(self):
        """Verify filtering by Doctor."""
        qs = get_prepaid_doctor_report_queryset(doctor_id=self.doctor1.pk)
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().name, self.doctor1.name)

    def test_filter_by_location(self):
        """Verify filtering by Location."""
        qs = get_prepaid_doctor_report_queryset(location="Boston")
        self.assertEqual(qs.count(), 1)
        self.assertEqual(qs.first().name, self.doctor2.name)

        qs_empty = get_prepaid_doctor_report_queryset(location="Unknown")
        self.assertEqual(qs_empty.count(), 0)

    def test_filter_by_product(self):
        """Verify Product filter recalculates returns only, keeping investment and expected return unchanged."""
        qs = get_prepaid_doctor_report_queryset(medicine_id=self.med1.pk)
        # Both doctors have sales entries for Medicine A
        self.assertEqual(qs.count(), 2)

        john = qs.filter(pk=self.doctor1.pk).first()
        self.assertEqual(john.total_investment, Decimal("3000.00"))      # Unchanged
        self.assertEqual(john.total_expected_return, Decimal("5000.00")) # Unchanged
        self.assertEqual(john.total_returns, Decimal("500.00"))          # Only Medicine A sales (sale1)

    def test_filter_by_status_in_progress(self):
        """Verify status='in_progress' filters investments and related returns."""
        qs = get_prepaid_doctor_report_queryset(status="in_progress")
        self.assertEqual(qs.count(), 2)

        # Doctor John has only ₹1000 in-progress investment (expected ₹2000) and ₹500 return
        john = qs.filter(pk=self.doctor1.pk).first()
        self.assertEqual(john.total_investment, Decimal("1000.00"))
        self.assertEqual(john.total_expected_return, Decimal("2000.00"))
        self.assertEqual(john.total_returns, Decimal("500.00"))

    def test_filter_by_status_completed(self):
        """Verify status='completed' filters investments and related returns."""
        qs = get_prepaid_doctor_report_queryset(status="completed")
        # Only Doctor John has a completed investment (Alice has none)
        self.assertEqual(qs.count(), 1)

        john = qs.first()
        self.assertEqual(john.name, self.doctor1.name)
        self.assertEqual(john.total_investment, Decimal("2000.00"))
        self.assertEqual(john.total_expected_return, Decimal("3000.00"))
        self.assertEqual(john.total_returns, Decimal("2000.00"))

    def test_filter_by_date_range(self):
        """Verify sales date range filters returns received correctly."""
        # Sales dates: sale1 = today-15, sale2 = today-45, sale3 = today-5
        # Range: today-20 to today-10 (should only match sale1)
        start_date = date.today() - timedelta(days=20)
        end_date = date.today() - timedelta(days=10)

        qs = get_prepaid_doctor_report_queryset(from_date=start_date, to_date=end_date)
        # Doctor John has sale1 in range. Doctor Alice has no sales in range.
        # But both doctors should appear since they have investments, but Alice's returns will be ₹0.
        self.assertEqual(qs.count(), 2)

        john = qs.filter(pk=self.doctor1.pk).first()
        self.assertEqual(john.total_investment, Decimal("3000.00"))
        self.assertEqual(john.total_expected_return, Decimal("5000.00"))
        self.assertEqual(john.total_returns, Decimal("500.00"))

        alice = qs.filter(pk=self.doctor2.pk).first()
        self.assertEqual(alice.total_investment, Decimal("5000.00"))
        self.assertEqual(alice.total_expected_return, Decimal("6000.00"))
        self.assertEqual(alice.total_returns, Decimal("0.00"))

    def test_empty_state_rendering(self):
        """Verify the template shows empty state message when search yields no matches."""
        self.client.force_login(self.admin)
        # Query with an impossible location to produce 0 rows
        report_url = reverse("reports:prepaid_doctor_report") + "?location=Nonexistent"
        response = self.client.get(report_url)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "No prepaid doctor records match the selected filters.")
        # Ensure headers are still in the HTML
        self.assertContains(response, "Doctor Name")
        self.assertContains(response, "Total Investment (₹)")
        self.assertContains(response, "Total Expected Return (₹)")
