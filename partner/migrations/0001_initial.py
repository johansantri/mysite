# Generated by Django 5.1.1 on 2024-10-08 09:06

import django.db.models.deletion
import partner.models
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Partner',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('partner_name', models.TextField(max_length=191)),
                ('abbreviation', models.CharField(max_length=50)),
                ('phone', models.CharField(max_length=50)),
                ('address', models.TextField(max_length=50)),
                ('tax', models.CharField(max_length=50)),
                ('status', models.CharField(max_length=50)),
                ('checks', models.CharField(max_length=50)),
                ('logo', models.ImageField(blank=True, null=True, upload_to=partner.models.filepath)),
                ('join', models.DateTimeField(auto_now_add=True)),
                ('e_mail', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
    ]