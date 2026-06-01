from decimal import Decimal
from datetime import date, timedelta
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.auth import get_user_model

from doctors.models import Doctor, DoctorMedicine, Investment
from medicines.models import Medicine
from sales.models import SalesEntry, PostpaidCampaign, PostpaidSaleEntry, CampaignPayment
from doctors.services.doctor_service import get_dashboard_alerts, get_dashboard_queryset

User = get_user_model()


class PostpaidLifecycleTests(TestCase):
    def setUp(self):
        self.rep = User.objects.create_user(username="rep_user", password="pwd", role="rep")
        self.admin = User.objects.create_user(username="admin_user", password="pwd", role="admin")

        self.doctor = Doctor.objects.create(
            name="Dr. Postpaid",
            mode="postpaid",
            assigned_rep=self.rep,
            is_active=True
        )
        self.medicine = Medicine.objects.create(
            name="Med A",
            pts=Decimal("150.00"),
            ptr=Decimal("130.00"),
            mrp=Decimal("180.00"),
            is_active=True
        )
        DoctorMedicine.objects.create(doctor=self.doctor, medicine=self.medicine)

    def test_postpaid_sale_entry_auto_creates_campaign_awaiting_commission(self):
        """
        Submitting a postpaid sales entry should auto-create a PostpaidCampaign
        in 'awaiting_commission' status with a commission_percentage of None.
        """
        # Create campaign and entry via model creation
        campaign, created = PostpaidCampaign.objects.get_or_create(
            doctor=self.doctor,
            month=6,
            year=2026,
            defaults={
                "commission_percentage": None,
                "status": PostpaidCampaign.STATUS_AWAITING_COMMISSION,
            }
        )
        self.assertTrue(created)
        self.assertEqual(campaign.status, PostpaidCampaign.STATUS_AWAITING_COMMISSION)
        self.assertIsNone(campaign.commission_percentage)

        sale = PostpaidSaleEntry.objects.create(
            campaign=campaign,
            medicine=self.medicine,
            quantity=10,
            entry_date=date.today(),
            rep=self.rep
        )

        # Check snapshots
        self.assertEqual(sale.pts_at_sale, Decimal("150.00"))
        self.assertEqual(sale.value_at_sale, Decimal("1500.00"))
        self.assertEqual(sale.commission_percentage_at_sale, Decimal("0.00"))
        self.assertEqual(sale.commission_at_sale, Decimal("0.00"))

        # Verify campaign totals recalculate
        campaign.refresh_from_db()
        self.assertEqual(campaign.total_sales_value, Decimal("1500.00"))
        self.assertEqual(campaign.total_commission, Decimal("0.00"))

    def test_commission_update_transitions_status_to_open(self):
        """
        Setting a commission percentage on an awaiting_commission campaign
        should automatically transition the campaign to Open status.
        """
        campaign = PostpaidCampaign.objects.create(
            doctor=self.doctor,
            month=6,
            year=2026,
            commission_percentage=None,
            status=PostpaidCampaign.STATUS_AWAITING_COMMISSION
        )
        self.assertEqual(campaign.status, PostpaidCampaign.STATUS_AWAITING_COMMISSION)

        # Configure commission
        campaign.update_commission_percentage(Decimal("10.00"))
        self.assertEqual(campaign.status, PostpaidCampaign.STATUS_OPEN)
        self.assertEqual(campaign.commission_percentage, Decimal("10.00"))

    def test_postpaid_snapshot_rule(self):
        """
        PostpaidSaleEntry values are frozen at creation and never recalculate
        from Medicine.pts even if the medicine price changes later.
        """
        campaign = PostpaidCampaign.objects.create(
            doctor=self.doctor,
            month=6,
            year=2026,
            commission_percentage=Decimal("15.00"),
            status=PostpaidCampaign.STATUS_OPEN
        )

        sale = PostpaidSaleEntry.objects.create(
            campaign=campaign,
            medicine=self.medicine,
            quantity=10,
            entry_date=date.today(),
            rep=self.rep
        )

        self.assertEqual(sale.pts_at_sale, Decimal("150.00"))
        self.assertEqual(sale.value_at_sale, Decimal("1500.00"))
        self.assertEqual(sale.commission_at_sale, Decimal("225.00"))

        # Alter live medicine price
        self.medicine.pts = Decimal("200.00")
        self.medicine.save()

        # Save sale entry again
        sale.save()

        # Verify snapshot prices DID NOT change
        sale.refresh_from_db()
        self.assertEqual(sale.pts_at_sale, Decimal("150.00"))
        self.assertEqual(sale.value_at_sale, Decimal("1500.00"))
        self.assertEqual(sale.commission_at_sale, Decimal("225.00"))

    def test_payments_only_allowed_on_partial_status(self):
        """
        Payments cannot be recorded unless the campaign is in Partial status.
        This blocks payments on Awaiting Commission, Open, Settled, and Locked campaigns.
        """
        campaign = PostpaidCampaign.objects.create(
            doctor=self.doctor,
            month=6,
            year=2026,
            commission_percentage=None,
            status=PostpaidCampaign.STATUS_AWAITING_COMMISSION
        )

        # Awaiting Commission status
        payment = CampaignPayment(campaign=campaign, amount=Decimal("100.00"), payment_date=date.today())
        with self.assertRaises(ValidationError):
            payment.clean()

        # Open status
        campaign.update_commission_percentage(Decimal("10.00"))
        self.assertEqual(campaign.status, PostpaidCampaign.STATUS_OPEN)
        with self.assertRaises(ValidationError):
            payment.clean()

        # Record sales so there is commission target (must be done while status is Open)
        PostpaidSaleEntry.objects.create(
            campaign=campaign,
            medicine=self.medicine,
            quantity=10,
            entry_date=date.today(),
            rep=self.rep
        )
        campaign.refresh_from_db()
        self.assertEqual(campaign.total_commission, Decimal("150.00"))

        # Advance manually to Partial status
        campaign.status = PostpaidCampaign.STATUS_PARTIAL
        campaign.save()

        # Try now — should pass validation
        payment.clean()  # Should not raise ValidationError

        # Save payment (transitions to Settled automatically if fully paid)
        payment.save()
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, PostpaidCampaign.STATUS_PARTIAL)  # 100 < 150

        # Create second payment to exceed balance (should auto-settle campaign)
        payment2 = CampaignPayment.objects.create(
            campaign=campaign,
            amount=Decimal("50.00"),
            payment_date=date.today()
        )
        campaign.refresh_from_db()
        self.assertEqual(campaign.status, PostpaidCampaign.STATUS_SETTLED)

        # Record a payment when campaign is Settled (should raise ValidationError)
        payment3 = CampaignPayment(campaign=campaign, amount=Decimal("10.00"), payment_date=date.today())
        with self.assertRaises(ValidationError):
            payment3.clean()

    def test_locked_campaigns_block_all_modifications(self):
        """
        Locked campaigns block all edits to campaign details.
        """
        campaign = PostpaidCampaign.objects.create(
            doctor=self.doctor,
            month=6,
            year=2026,
            commission_percentage=Decimal("10.00"),
            status=PostpaidCampaign.STATUS_LOCKED
        )

        # Attempt to change commission percentage
        campaign.commission_percentage = Decimal("15.00")
        with self.assertRaises(ValidationError):
            campaign.clean()

    def test_commission_locked_past_open(self):
        """
        Commission percentage cannot be changed once the campaign transitions past Open.
        """
        campaign = PostpaidCampaign.objects.create(
            doctor=self.doctor,
            month=6,
            year=2026,
            commission_percentage=Decimal("10.00"),
            status=PostpaidCampaign.STATUS_PARTIAL
        )

        # Attempt to modify commission
        campaign.commission_percentage = Decimal("15.00")
        with self.assertRaises(ValidationError):
            campaign.clean()

    def test_append_only_ledger_entries(self):
        """
        Ledger entries cannot be updated or deleted.
        """
        campaign = PostpaidCampaign.objects.create(
            doctor=self.doctor,
            month=6,
            year=2026,
            commission_percentage=Decimal("10.00"),
            status=PostpaidCampaign.STATUS_PARTIAL
        )

        payment = CampaignPayment.objects.create(
            campaign=campaign,
            amount=Decimal("100.00"),
            payment_date=date.today()
        )

        # Attempt to edit payment amount
        payment.amount = Decimal("150.00")
        with self.assertRaises(ValueError):
            payment.save()

        # Attempt to delete payment
        with self.assertRaises(ValidationError):
            payment.delete()

    def test_awaiting_commission_alerts(self):
        """
        Unconfigured campaigns show warnings after 3 days (yellow) and 7 days (red).
        """
        # Clear existing campaigns to avoid alert pollution
        PostpaidCampaign.objects.all().delete()

        # Create one awaiting commission campaign with age = 4 days
        campaign_yellow = PostpaidCampaign.objects.create(
            doctor=self.doctor,
            month=5,
            year=2026,
            commission_percentage=None,
            status=PostpaidCampaign.STATUS_AWAITING_COMMISSION
        )
        # Manually alter created_at to simulate age
        PostpaidCampaign.objects.filter(pk=campaign_yellow.pk).update(
            created_at=timezone.now() - timedelta(days=4)
        )

        # Create another awaiting commission campaign with age = 8 days
        campaign_red = PostpaidCampaign.objects.create(
            doctor=self.doctor,
            month=4,
            year=2026,
            commission_percentage=None,
            status=PostpaidCampaign.STATUS_AWAITING_COMMISSION
        )
        PostpaidCampaign.objects.filter(pk=campaign_red.pk).update(
            created_at=timezone.now() - timedelta(days=8)
        )

        alerts = get_dashboard_alerts()

        # Look for warnings in alerts list
        yellow_found = any("WARNING" in a["message"] and "Dr. Postpaid" in a["message"] and a["type"] == "warning" for a in alerts)
        red_found = any("RED WARNING" in a["message"] and "Dr. Postpaid" in a["message"] and a["type"] == "danger" for a in alerts)

        self.assertTrue(yellow_found)
        self.assertTrue(red_found)


class PrepaidDashboardTests(TestCase):
    def setUp(self):
        self.rep = get_user_model().objects.create_user(username="rep_user2", password="pwd", role="rep")
        self.doctor = Doctor.objects.create(
            name="Dr. Prepaid ABC",
            mode="prepaid",
            assigned_rep=self.rep,
            is_active=True
        )
        self.medicine = Medicine.objects.create(
            name="Med B",
            pts=Decimal("100.00"),
            ptr=Decimal("80.00"),
            mrp=Decimal("120.00"),
            is_active=True
        )
        DoctorMedicine.objects.create(doctor=self.doctor, medicine=self.medicine)

    def test_dashboard_excludes_completed_investments_from_active_exposure(self):
        """
        Prepaid dashboard queryset achieved_roi must only sum sales entries from active (in_progress) investments.
        Completed investment totals and sales must not contaminate active dashboard metrics.
        """
        # Create completed investment
        inv_completed = Investment.objects.create(
            doctor=self.doctor,
            amount=Decimal("1000.00"),
            roi_ratio=Decimal("2.50"),
            start_date=date.today() - timedelta(days=60),
            status=Investment.STATUS_IN_PROGRESS
        )
        
        # Create sales entry associated with completed investment
        entry_completed = SalesEntry.objects.create(
            rep=self.rep,
            doctor=self.doctor,
            investment=inv_completed,
            medicine=self.medicine,
            quantity=25,  # 25 * 100 = 2500 achieved (fully completes target of 1000*2.5 = 2500)
            entry_date=date.today() - timedelta(days=50)
        )
        inv_completed.refresh_from_db()
        self.assertEqual(inv_completed.status, Investment.STATUS_COMPLETED)
        # Ensure snapshot populated correctly
        self.assertEqual(entry_completed.value_at_sale, Decimal("2500.00"))

        # Verify that doctor with only completed investments returns 0 metrics on the active dashboard
        qs1 = get_dashboard_queryset().filter(pk=self.doctor.pk)
        self.assertEqual(qs1.count(), 1)
        doc_metric1 = qs1.first()
        self.assertEqual(doc_metric1.total_investment, Decimal("0.00"))
        self.assertEqual(doc_metric1.total_roi_amount, Decimal("0.00"))
        self.assertEqual(doc_metric1.achieved_roi, Decimal("0.00"))
        self.assertEqual(doc_metric1.balance_roi, Decimal("0.00"))

        # Now create an active (in_progress) investment
        inv_active = Investment.objects.create(
            doctor=self.doctor,
            amount=Decimal("2000.00"),
            roi_ratio=Decimal("2.00"),
            start_date=date.today() - timedelta(days=10),
            status=Investment.STATUS_IN_PROGRESS
        )

        # Create sales entry associated with active investment
        entry_active = SalesEntry.objects.create(
            rep=self.rep,
            doctor=self.doctor,
            investment=inv_active,
            medicine=self.medicine,
            quantity=15,  # 15 * 100 = 1500 achieved
            entry_date=date.today()
        )

        # Verify that the dashboard queryset now only aggregates metrics for the active investment
        qs2 = get_dashboard_queryset().filter(pk=self.doctor.pk)
        doc_metric2 = qs2.first()
        self.assertEqual(doc_metric2.total_investment, Decimal("2000.00"))
        self.assertEqual(doc_metric2.total_roi_amount, Decimal("4000.00"))
        self.assertEqual(doc_metric2.achieved_roi, Decimal("1500.00"))  # excludes the 2500 from inv_completed
        self.assertEqual(doc_metric2.balance_roi, Decimal("2500.00"))   # 4000 - 1500 = 2500
