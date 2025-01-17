# Generated by Django 5.1.1 on 2025-01-10 09:12

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0041_question_question_type_choice'),
    ]

    operations = [
        migrations.CreateModel(
            name='AssignmentType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=100)),
                ('abbreviation', models.CharField(max_length=10)),
                ('weight', models.FloatField()),
                ('total_number', models.PositiveIntegerField(default=0)),
                ('droppable', models.PositiveIntegerField(default=0)),
            ],
        ),
        migrations.CreateModel(
            name='GradeRange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('label', models.CharField(max_length=50)),
                ('min_score', models.FloatField()),
                ('max_score', models.FloatField()),
                ('color', models.CharField(default='#FFFFFF', max_length=7)),
            ],
        ),
        migrations.CreateModel(
            name='GradingPolicy',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('grace_period', models.DurationField()),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.AddField(
            model_name='course',
            name='assignment_types',
            field=models.ManyToManyField(blank=True, related_name='courses', to='courses.assignmenttype'),
        ),
        migrations.AddField(
            model_name='course',
            name='grade_ranges',
            field=models.ManyToManyField(blank=True, related_name='courses', to='courses.graderange'),
        ),
        migrations.AddField(
            model_name='course',
            name='grading_policy',
            field=models.OneToOneField(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='course', to='courses.gradingpolicy'),
        ),
    ]
