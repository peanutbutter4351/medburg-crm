from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from doctors.models import Doctor, Investment
from medicines.models import Medicine
from sales.models import SalesEntry, PostpaidSaleEntry, PostpaidCampaign
from sales.services.analytics_service import get_home_kpis

User = get_user_model()


class DashboardHomeTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin", role="admin")
        self.rep1 = User.objects.create_user(username="rep1", role="rep")
        
        self.doc1 = Doctor.objects.create(name="Doc 1", mode="prepaid")
        self.doc2 = Doctor.objects.create(name="Doc 2", mode="postpaid", assigned_rep=self.rep1)
        
        self.med = Medicine.objects.create(
            name="Med A", 
            pts=Decimal("100.00"),
            ptr=Decimal("120.00"),
            mrp=Decimal("150.00"),
            is_active=True
        )
        
        self.inv = Investment.objects.create(
            doctor=self.doc1,
            amount=Decimal("1000.00"),
            roi_ratio=Decimal("1.00"),
            status=Investment.STATUS_IN_PROGRESS,
            start_date=date.today()
        )
        self.prepaid_sale = SalesEntry.objects.create(
            doctor=self.doc1,
            rep=self.rep1,
            medicine=self.med,
            quantity=5,
            investment=self.inv,
            entry_date=date.today()
        )
        
        # Postpaid Campaign and Sales
        self.campaign = PostpaidCampaign.objects.create(
            doctor=self.doc2,
            month=date.today().month,
            year=date.today().year,
            status=PostpaidCampaign.STATUS_OPEN,
            commission_percentage=Decimal("10.00")
        )
        self.postpaid_sale = PostpaidSaleEntry.objects.create(
            campaign=self.campaign,
            medicine=self.med,
            quantity=10,
            rep=self.rep1,
            entry_date=date.today()
        )

    def test_get_home_kpis_calculation(self):
        kpis = get_home_kpis()
        self.assertEqual(kpis["today_revenue"], Decimal("1500.00"))
        self.assertEqual(kpis["active_doctors"], 2)
        self.assertEqual(kpis["active_prepaid_investments"], 1)
        self.assertEqual(kpis["active_postpaid_campaigns"], 1)
        self.assertEqual(kpis["monthly_revenue"], Decimal("1500.00"))

    def test_get_home_kpis_empty(self):
        SalesEntry.objects.all().delete()
        PostpaidSaleEntry.objects.all().delete()
        Doctor.objects.all().delete()
        Investment.objects.all().delete()
        PostpaidCampaign.objects.all().delete()

        kpis = get_home_kpis()
        self.assertEqual(kpis["today_revenue"], Decimal("0.00"))
        self.assertEqual(kpis["active_doctors"], 0)
        self.assertEqual(kpis["active_prepaid_investments"], 0)
        self.assertEqual(kpis["active_postpaid_campaigns"], 0)
        self.assertEqual(kpis["monthly_revenue"], Decimal("0.00"))

    def test_dashboard_context_has_home_kpis(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("doctors:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertIn("home_kpis", response.context)
        kpis = response.context["home_kpis"]
        self.assertEqual(kpis["today_revenue"], Decimal("1500.00"))
        
        # Test rep user doesn't get home_kpis
        self.client.force_login(self.rep1)
        response = self.client.get(reverse("doctors:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("home_kpis", response.context)

    def test_active_campaign_statuses_logic(self):
        # Awaiting Commission
        self.campaign.status = PostpaidCampaign.STATUS_AWAITING_COMMISSION
        self.campaign.save()
        self.assertEqual(get_home_kpis()["active_postpaid_campaigns"], 1)

        # Partial
        self.campaign.status = PostpaidCampaign.STATUS_PARTIAL
        self.campaign.save()
        self.assertEqual(get_home_kpis()["active_postpaid_campaigns"], 1)

        # Settled
        self.campaign.status = PostpaidCampaign.STATUS_SETTLED
        self.campaign.settlement_reason = PostpaidCampaign.REASON_MANAGEMENT_APPROVAL
        self.campaign.settlement_notes = "Approved by management"
        self.campaign.save()
        self.assertEqual(get_home_kpis()["active_postpaid_campaigns"], 1)

        # Locked (should NOT be active)
        self.campaign.status = PostpaidCampaign.STATUS_LOCKED
        self.campaign.save()
        self.assertEqual(get_home_kpis()["active_postpaid_campaigns"], 0)
