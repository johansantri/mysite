# Generated by Django 5.1.1 on 2024-11-20 09:19

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0012_course_created_at'),
    ]

    operations = [
        migrations.AddField(
            model_name='course',
            name='edited_on',
            field=models.DateTimeField(auto_now=True),
        ),
    ]
