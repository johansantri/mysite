# Generated by Django 5.1.1 on 2024-11-11 02:12

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0030_organization_employee'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='instructor',
            name='mycourse',
        ),
        migrations.RemoveField(
            model_name='instructor',
            name='name',
        ),
        migrations.RemoveField(
            model_name='instructor',
            name='org',
        ),
        migrations.DeleteModel(
            name='Employee',
        ),
        migrations.DeleteModel(
            name='Organization',
        ),
        migrations.DeleteModel(
            name='Instructor',
        ),
    ]