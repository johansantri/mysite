# Generated by Django 5.1.1 on 2024-10-22 07:27

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0006_remove_course_course_overview_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='course',
            name='topic',
        ),
    ]