# Generated by Django 5.1.1 on 2024-10-24 03:23

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0015_instructor'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.RenameField(
            model_name='instructor',
            old_name='org_partner',
            new_name='org',
        ),
        migrations.RemoveField(
            model_name='course',
            name='author',
        ),
        migrations.AlterField(
            model_name='instructor',
            name='name',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]