# Generated by Django 5.1.1 on 2025-01-10 09:38

import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0043_alter_assignmenttype_abbreviation_and_more'),
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
        migrations.AddField(
            model_name='assignmenttype',
            name='course',
            field=models.ForeignKey(default=True, on_delete=django.db.models.deletion.CASCADE, related_name='assignment_types', to='courses.course'),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name='graderange',
            name='course',
            field=models.ForeignKey(default=True, on_delete=django.db.models.deletion.CASCADE, related_name='grade_ranges', to='courses.course'),
            preserve_default=False,
        ),
    ]