# Generated by Django 5.1.1 on 2024-12-30 08:23

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth', '0020_alter_user_university'),
        ('courses', '0023_alter_partner_name'),
    ]

    operations = [
        migrations.AlterField(
            model_name='partner',
            name='name',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='auth.univer'),
        ),
    ]
