# Generated by Django 5.1.1 on 2025-01-10 09:15

import datetime
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0042_assignmenttype_graderange_gradingpolicy_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='assignmenttype',
            name='abbreviation',
            field=models.CharField(default='HW', max_length=10),
        ),
        migrations.AlterField(
            model_name='assignmenttype',
            name='name',
            field=models.CharField(default='Homework', max_length=100),
        ),
        migrations.AlterField(
            model_name='assignmenttype',
            name='total_number',
            field=models.PositiveIntegerField(default=1),
        ),
        migrations.AlterField(
            model_name='assignmenttype',
            name='weight',
            field=models.FloatField(default=10.0),
        ),
        migrations.AlterField(
            model_name='graderange',
            name='color',
            field=models.CharField(default='#00FF00', max_length=7),
        ),
        migrations.AlterField(
            model_name='graderange',
            name='label',
            field=models.CharField(default='Pass', max_length=50),
        ),
        migrations.AlterField(
            model_name='graderange',
            name='max_score',
            field=models.FloatField(default=100.0),
        ),
        migrations.AlterField(
            model_name='graderange',
            name='min_score',
            field=models.FloatField(default=0.0),
        ),
        migrations.AlterField(
            model_name='gradingpolicy',
            name='grace_period',
            field=models.DurationField(default=datetime.timedelta(days=1)),
        ),
    ]