# Generated by Django 5.1.1 on 2025-01-10 09:42

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0045_remove_assignmenttype_course_and_more'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='course',
            name='assignment_types',
        ),
        migrations.RemoveField(
            model_name='course',
            name='grade_ranges',
        ),
        migrations.RemoveField(
            model_name='course',
            name='grading_policy',
        ),
    ]