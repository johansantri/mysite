# Generated by Django 5.1.1 on 2024-10-24 06:22

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('courses', '0020_alter_course_category'),
    ]

    operations = [
        migrations.AlterField(
            model_name='course',
            name='category',
            field=models.CharField(blank=True, choices=[('technology', 'technology'), ('law', 'law'), ('economic', 'economic'), ('social', 'social'), ('agriculture', 'agriculture'), ('mining', 'mining'), ('management', 'management'), ('program', 'program')], max_length=50, null=True),
        ),
        migrations.DeleteModel(
            name='Category',
        ),
    ]
