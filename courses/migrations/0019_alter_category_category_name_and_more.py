# Generated by Django 5.1.1 on 2024-10-24 06:18

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0018_category'),
    ]

    operations = [
        migrations.AlterField(
            model_name='category',
            name='category_name',
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AlterField(
            model_name='category',
            name='category_slug',
            field=models.CharField(blank=True, max_length=200),
        ),
    ]