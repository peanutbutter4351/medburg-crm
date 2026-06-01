# MR-8.0: Drop the legacy PostpaidEntry table.
#
# The PostpaidEntry model tracked ROI payments for the old postpaid workflow.
# It has been completely superseded by the PostpaidCampaign / PostpaidSaleEntry
# / CampaignPayment engine introduced in MR-5 through MR-7.
#
# This migration drops the table and all its associated constraints.
# The Python model class was removed from sales/models.py in MR-8.0.

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ("sales", "0013_alter_postpaidsaleentry_options_and_more"),
    ]

    operations = [
        migrations.DeleteModel(
            name="PostpaidEntry",
        ),
    ]
