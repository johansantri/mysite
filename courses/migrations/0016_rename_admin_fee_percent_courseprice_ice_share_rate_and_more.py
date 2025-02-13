# Generated by Django 5.1.1 on 2025-02-06 08:20

from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0015_alter_courseprice_partner_price_and_more'),
    ]

    operations = [
        migrations.RenameField(
            model_name='courseprice',
            old_name='admin_fee_percent',
            new_name='ice_share_rate',
        ),
        migrations.RemoveField(
            model_name='courseprice',
            name='iceiprice',
        ),
        migrations.RemoveField(
            model_name='courseprice',
            name='ppn_percent',
        ),
        migrations.AddField(
            model_name='courseprice',
            name='ice_share_value',
            field=models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='ICE Share Value'),
        ),
        migrations.AddField(
            model_name='courseprice',
            name='ppn_rate',
            field=models.DecimalField(decimal_places=2, default=Decimal('11.00'), max_digits=5, verbose_name='PPN Rate (%)'),
        ),
    ]
