import json
from decimal import Decimal
from datetime import date
from django.db.models import Sum, Count, Case, When, DecimalField, F
from django.db.models.functions import Coalesce, TruncMonth
from django.contrib.auth import get_user_model

from sales.models import SalesEntry, PostpaidSaleEntry, PostpaidCampaign
from doctors.models import Doctor

User = get_user_model()


def get_last_12_months_labels():
    """Returns a list of month labels (e.g., 'Jan 2026') and the start date for the past 12 months."""
    today = date.today()
    labels = []
    start_date = None
    
    for i in range(11, -1, -1):
        year = today.year
        month = today.month - i
        if month <= 0:
            month += 12
            year -= 1
            
        d = date(year, month, 1)
        labels.append(d.strftime("%b %Y"))
        if i == 11:
            start_date = d
            
    return start_date, labels


def get_admin_dashboard_analytics():
    """
    Returns JSON-serializable chart data for the Admin Dashboard.
    - prepaid_monthly: line chart (last 12 months)
    - postpaid_monthly: line chart (last 12 months)
    - revenue_split: doughnut chart
    - top_reps: bar chart
    - top_doctors: bar chart
    """
    start_date, labels = get_last_12_months_labels()

    # 1. Prepaid Monthly
    prepaid_qs = SalesEntry.objects.filter(entry_date__gte=start_date).annotate(
        month=TruncMonth('entry_date')
    ).values('month').annotate(
        total=Coalesce(Sum('value_at_sale'), Decimal('0.00'), output_field=DecimalField())
    ).order_by('month')
    
    prepaid_monthly_data = {label: Decimal('0.00') for label in labels}
    for row in prepaid_qs:
        month_label = row['month'].strftime("%b %Y")
        if month_label in prepaid_monthly_data:
            prepaid_monthly_data[month_label] = row['total']

    # 2. Postpaid Monthly
    postpaid_qs = PostpaidSaleEntry.objects.filter(entry_date__gte=start_date).annotate(
        month=TruncMonth('entry_date')
    ).values('month').annotate(
        total=Coalesce(Sum('value_at_sale'), Decimal('0.00'), output_field=DecimalField())
    ).order_by('month')

    postpaid_monthly_data = {label: Decimal('0.00') for label in labels}
    for row in postpaid_qs:
        month_label = row['month'].strftime("%b %Y")
        if month_label in postpaid_monthly_data:
            postpaid_monthly_data[month_label] = row['total']

    # 3. Revenue Split (All time)
    total_prepaid = SalesEntry.objects.aggregate(
        total=Coalesce(Sum('value_at_sale'), Decimal('0.00'), output_field=DecimalField())
    )['total']
    
    total_postpaid = PostpaidSaleEntry.objects.aggregate(
        total=Coalesce(Sum('value_at_sale'), Decimal('0.00'), output_field=DecimalField())
    )['total']
    
    # 4. Top Performing Reps (Top 5 by total sales value)
    reps = User.objects.filter(role="rep").annotate(
        prepaid_sales=Coalesce(Sum('sales_entries__value_at_sale'), Decimal('0.00'), output_field=DecimalField()),
        postpaid_sales=Coalesce(Sum('postpaidsaleentry__value_at_sale'), Decimal('0.00'), output_field=DecimalField()),
    ).annotate(
        total_sales=F('prepaid_sales') + F('postpaid_sales')
    ).order_by('-total_sales')[:5]

    top_reps_labels = []
    top_reps_data = []
    for rep in reps:
        name = f"{rep.first_name} {rep.last_name}".strip() or rep.username
        top_reps_labels.append(name)
        top_reps_data.append(float(rep.total_sales))

    # 5. Top Performing Doctors (Top 10 by total sales value)
    doctors = Doctor.objects.annotate(
        prepaid_sales=Coalesce(
            Sum('sales_entries__value_at_sale'),
            Decimal('0.00'),
            output_field=DecimalField()
        ),
        postpaid_sales=Coalesce(
            Sum('postpaid_campaigns__sales_entries__value_at_sale'),
            Decimal('0.00'),
            output_field=DecimalField()
        ),
    ).annotate(
        total_sales=F('prepaid_sales') + F('postpaid_sales')
    ).order_by('-total_sales')[:10]

    top_doctors_labels = []
    top_doctors_data = []
    for doc in doctors:
        top_doctors_labels.append(doc.name)
        top_doctors_data.append(float(doc.total_sales))

    return {
        "prepaid_monthly": {
            "labels": labels,
            "data": [float(val) for val in prepaid_monthly_data.values()]
        },
        "postpaid_monthly": {
            "labels": labels,
            "data": [float(val) for val in postpaid_monthly_data.values()]
        },
        "revenue_split": {
            "labels": ["Prepaid", "Postpaid"],
            "data": [float(total_prepaid), float(total_postpaid)]
        },
        "top_reps": {
            "labels": top_reps_labels,
            "data": top_reps_data
        },
        "top_doctors": {
            "labels": top_doctors_labels,
            "data": top_doctors_data
        }
    }


def get_rep_dashboard_analytics(user):
    """
    Returns JSON-serializable chart data for the Rep Dashboard.
    - campaign_distribution: pie/doughnut chart for this rep's campaigns
    - monthly_postpaid_sales: line chart for this rep's postpaid sales (last 12 months)
    """
    # 1. Campaign Distribution
    campaigns = PostpaidCampaign.objects.filter(doctor__assigned_rep=user).values('status').annotate(count=Count('id'))
    
    status_counts = {
        PostpaidCampaign.STATUS_AWAITING_COMMISSION: 0,
        PostpaidCampaign.STATUS_OPEN: 0,
        PostpaidCampaign.STATUS_PARTIAL: 0,
        PostpaidCampaign.STATUS_SETTLED: 0,
        PostpaidCampaign.STATUS_LOCKED: 0,
    }
    
    for row in campaigns:
        if row['status'] in status_counts:
            status_counts[row['status']] = row['count']
            
    distribution_labels = [dict(PostpaidCampaign.STATUS_CHOICES).get(k) for k in status_counts.keys()]
    distribution_data = list(status_counts.values())

    # 2. Monthly Postpaid Sales (last 12 months)
    start_date, labels = get_last_12_months_labels()
    
    postpaid_qs = PostpaidSaleEntry.objects.filter(rep=user, entry_date__gte=start_date).annotate(
        month=TruncMonth('entry_date')
    ).values('month').annotate(
        total=Coalesce(Sum('value_at_sale'), Decimal('0.00'), output_field=DecimalField())
    ).order_by('month')

    monthly_postpaid_data = {label: Decimal('0.00') for label in labels}
    for row in postpaid_qs:
        month_label = row['month'].strftime("%b %Y")
        if month_label in monthly_postpaid_data:
            monthly_postpaid_data[month_label] = row['total']

    # 3. Monthly Prepaid Sales (last 12 months)
    prepaid_qs = SalesEntry.objects.filter(rep=user, entry_date__gte=start_date).annotate(
        month=TruncMonth('entry_date')
    ).values('month').annotate(
        total=Coalesce(Sum('value_at_sale'), Decimal('0.00'), output_field=DecimalField())
    ).order_by('month')

    monthly_prepaid_data = {label: Decimal('0.00') for label in labels}
    for row in prepaid_qs:
        month_label = row['month'].strftime("%b %Y")
        if month_label in monthly_prepaid_data:
            monthly_prepaid_data[month_label] = row['total']

    # 4. Investment Status Distribution
    from doctors.models import Investment
    prepaid_doctors = Doctor.objects.filter(assigned_rep=user, mode='prepaid')
    
    in_progress = 0
    completed = 0
    no_investment = 0
    
    for doc in prepaid_doctors:
        active_inv = doc.investments.filter(status=Investment.STATUS_IN_PROGRESS).exists()
        if active_inv:
            in_progress += 1
        elif doc.investments.filter(status=Investment.STATUS_COMPLETED).exists():
            completed += 1
        else:
            no_investment += 1

    investment_distribution_labels = ["In Progress", "Completed", "No Investment"]
    investment_distribution_data = [in_progress, completed, no_investment]

    return {
        "campaign_distribution": {
            "labels": distribution_labels,
            "data": distribution_data
        },
        "monthly_postpaid_sales": {
            "labels": labels,
            "data": [float(val) for val in monthly_postpaid_data.values()]
        },
        "monthly_prepaid_sales": {
            "labels": labels,
            "data": [float(val) for val in monthly_prepaid_data.values()]
        },
        "investment_distribution": {
            "labels": investment_distribution_labels,
            "data": investment_distribution_data
        }
    }


def get_home_kpis():
    """
    Compute KPI summary metrics for the Admin Dashboard Home Redesign.
    - Today's Revenue: Sum of prepaid + postpaid value_at_sale where entry_date == today.
    - Active Doctors: Count of active Doctor records.
    - Active Prepaid Investments: Count of Investment objects with status = in_progress.
    - Active Postpaid Campaigns: Count of non-locked postpaid campaigns.
    - Monthly Revenue: Sum of prepaid + postpaid value_at_sale for the current calendar month.
    """
    from datetime import date
    from doctors.models import Investment
    
    today = date.today()
    
    # 1. Today's Revenue
    prepaid_today = SalesEntry.objects.filter(entry_date=today).aggregate(
        total=Coalesce(Sum('value_at_sale'), Decimal('0.00'), output_field=DecimalField())
    )['total']
    
    postpaid_today = PostpaidSaleEntry.objects.filter(entry_date=today).aggregate(
        total=Coalesce(Sum('value_at_sale'), Decimal('0.00'), output_field=DecimalField())
    )['total']
    
    today_revenue = prepaid_today + postpaid_today
    
    # 2. Active Doctors
    active_doctors = Doctor.objects.filter(is_active=True).count()
    
    # 3. Active Prepaid Investments
    active_prepaid_investments = Investment.objects.filter(status=Investment.STATUS_IN_PROGRESS).count()
    
    # 4. Active Postpaid Campaigns (non-locked campaigns)
    active_postpaid_campaigns = PostpaidCampaign.objects.exclude(status=PostpaidCampaign.STATUS_LOCKED).count()
    
    # 5. Monthly Revenue
    prepaid_month = SalesEntry.objects.filter(
        entry_date__year=today.year,
        entry_date__month=today.month
    ).aggregate(
        total=Coalesce(Sum('value_at_sale'), Decimal('0.00'), output_field=DecimalField())
    )['total']
    
    postpaid_month = PostpaidSaleEntry.objects.filter(
        entry_date__year=today.year,
        entry_date__month=today.month
    ).aggregate(
        total=Coalesce(Sum('value_at_sale'), Decimal('0.00'), output_field=DecimalField())
    )['total']
    
    monthly_revenue = prepaid_month + postpaid_month
    
    return {
        "today_revenue": today_revenue,
        "active_doctors": active_doctors,
        "active_prepaid_investments": active_prepaid_investments,
        "active_postpaid_campaigns": active_postpaid_campaigns,
        "monthly_revenue": monthly_revenue,
    }
