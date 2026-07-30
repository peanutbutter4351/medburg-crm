from decimal import Decimal
from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse

from doctors.models import Doctor, Investment
from medicines.models import Medicine
from sales.models import SalesEntry, PostpaidSaleEntry, PostpaidCampaign
from sales.services.analytics_service import get_admin_dashboard_analytics, get_rep_dashboard_analytics, get_last_12_months_labels

User = get_user_model()


class AnalyticsServiceTest(TestCase):
    def setUp(self):
        self.admin = User.objects.create_user(username="admin", role="admin")
        self.rep1 = User.objects.create_user(username="rep1", role="rep")
        self.rep2 = User.objects.create_user(username="rep2", role="rep")
        
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

    def test_get_admin_dashboard_analytics_with_data(self):
        analytics = get_admin_dashboard_analytics()
        
        # Verify keys
        self.assertIn("prepaid_monthly", analytics)
        self.assertIn("postpaid_monthly", analytics)
        self.assertIn("revenue_split", analytics)
        self.assertIn("top_reps", analytics)
        self.assertIn("top_doctors", analytics)
        
        # Verify Revenue Split
        self.assertEqual(analytics["revenue_split"]["data"], [500.0, 1000.0])
        
        # Verify Top Reps
        self.assertIn(self.rep1.username, analytics["top_reps"]["labels"])
        rep1_index = analytics["top_reps"]["labels"].index(self.rep1.username)
        self.assertEqual(analytics["top_reps"]["data"][rep1_index], 1500.0)

    def test_get_admin_dashboard_analytics_empty_dataset(self):
        SalesEntry.objects.all().delete()
        PostpaidSaleEntry.objects.all().delete()
        
        analytics = get_admin_dashboard_analytics()
        self.assertEqual(analytics["revenue_split"]["data"], [0.0, 0.0])
        self.assertEqual(sum(analytics["prepaid_monthly"]["data"]), 0.0)
        self.assertEqual(sum(analytics["postpaid_monthly"]["data"]), 0.0)

    def test_get_rep_dashboard_analytics(self):
        analytics = get_rep_dashboard_analytics(self.rep1)
        
        self.assertIn("campaign_distribution", analytics)
        self.assertIn("monthly_postpaid_sales", analytics)
        
        # rep1 has 1 OPEN campaign
        dist_labels = analytics["campaign_distribution"]["labels"]
        dist_data = analytics["campaign_distribution"]["data"]
        
        open_idx = dist_labels.index("Open")
        self.assertEqual(dist_data[open_idx], 1)
        
        # rep2 has no campaigns
        analytics2 = get_rep_dashboard_analytics(self.rep2)
        dist_data2 = analytics2["campaign_distribution"]["data"]
        self.assertEqual(sum(dist_data2), 0)

    def test_dashboard_view_context_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("doctors:dashboard"))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("admin_analytics", response.context)
        analytics = response.context["admin_analytics"]
        self.assertIn("revenue_split", analytics)

    def test_dashboard_view_context_rep(self):
        self.client.force_login(self.rep1)
        response = self.client.get(reverse("doctors:dashboard"))
        
        self.assertEqual(response.status_code, 200)
        self.assertIn("rep_analytics", response.context)
        analytics = response.context["rep_analytics"]
        self.assertIn("campaign_distribution", analytics)

    def test_chart_json_payload_generation(self):
        """Test that json_script renders properly in the template."""
        self.client.force_login(self.admin)
        response = self.client.get(reverse("doctors:dashboard"))
        
        content = response.content.decode('utf-8')
        self.assertIn('<script id="admin-analytics-data" type="application/json">', content)
        self.assertIn('"revenue_split"', content)
        
        self.client.force_login(self.rep1)
        response = self.client.get(reverse("doctors:dashboard"))
        
        content = response.content.decode('utf-8')
        self.assertIn('<script id="rep-analytics-data" type="application/json">', content)
        self.assertIn('"campaign_distribution"', content)

    def test_dashboard_view_section_parameter(self):
        """Test section parameter logic and UI state rendering in admin dashboard view."""
        self.client.force_login(self.admin)
        
        # Test default section is home
        response = self.client.get(reverse("doctors:dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_section"], "home")
        
        # Test valid prepaid section
        response = self.client.get(reverse("doctors:dashboard") + "?section=prepaid")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_section"], "prepaid")
        content = response.content.decode('utf-8')
        self.assertIn('name="section" id="active-section-input" value="prepaid"', content)
        self.assertIn('id="btn-prepaid">PREPAID</button>', content)
        self.assertIn('class="switcher-btn active" onclick="switchDashboardSection(\'prepaid\')"', content)
        
        # Test valid postpaid section
        response = self.client.get(reverse("doctors:dashboard") + "?section=postpaid")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_section"], "postpaid")
        content = response.content.decode('utf-8')
        self.assertIn('name="section" id="active-section-input" value="postpaid"', content)
        
        # Test invalid section resets to default (home)
        response = self.client.get(reverse("doctors:dashboard") + "?section=invalid_tab")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_section"], "home")

