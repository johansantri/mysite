# Generated by Django 5.1.1 on 2024-12-17 01:54

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0016_alter_course_status_course'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='level',
            field=models.CharField(blank=True, choices=[('basic', 'Basic'), ('middle', 'Middle'), ('advanced', 'Advanced')], default='basic', max_length=10, null=True),
        ),
    ]