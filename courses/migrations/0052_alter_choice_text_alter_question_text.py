# Generated by Django 5.1.1 on 2025-01-14 06:55

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0051_remove_question_section_question_created_at_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='choice',
            name='text',
            field=models.CharField(blank=True, max_length=200, null=True),
        ),
        migrations.AlterField(
            model_name='question',
            name='text',
            field=models.CharField(blank=True, max_length=255, null=True),
        ),
    ]