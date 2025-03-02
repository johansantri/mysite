# Generated by Django 5.1.1 on 2025-03-03 01:07

import autoslug.fields
import django.core.validators
import django.db.models.deletion
from decimal import Decimal
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ('auth', '0001_initial'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='Assessment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('weight', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('description', models.TextField(blank=True, null=True)),
                ('flag', models.BooleanField(default=False)),
                ('duration_in_minutes', models.IntegerField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='CalculateAdminPrice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True, verbose_name='Pricing Type')),
                ('amount', models.DecimalField(decimal_places=2, max_digits=10, verbose_name='Amount (IDR)')),
                ('created_at', models.DateTimeField(auto_now_add=True, verbose_name='Created At')),
            ],
        ),
        migrations.CreateModel(
            name='CourseStatus',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('curation', 'Curation'), ('published', 'Published'), ('archived', 'Archived')], default='draft', max_length=20)),
                ('manual_message', models.TextField(blank=True, null=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
        ),
        migrations.CreateModel(
            name='PricingType',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=50, unique=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
            ],
        ),
        migrations.CreateModel(
            name='AskOra',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(blank=True, max_length=200, null=True)),
                ('question_text', models.TextField()),
                ('response_deadline', models.DateTimeField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('assessment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ask_oras', to='courses.assessment')),
            ],
        ),
        migrations.CreateModel(
            name='AssessmentSession',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_time', models.DateTimeField()),
                ('end_time', models.DateTimeField()),
                ('assessment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.assessment')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=250)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Course',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('course_name', models.CharField(max_length=250)),
                ('course_number', models.CharField(blank=True, max_length=250)),
                ('course_run', models.CharField(blank=True, max_length=250)),
                ('slug', models.CharField(blank=True, max_length=250)),
                ('level', models.CharField(blank=True, choices=[('basic', 'Basic'), ('middle', 'Middle'), ('advanced', 'Advanced')], default='basic', max_length=10, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('edited_on', models.DateTimeField(auto_now=True)),
                ('image', models.ImageField(blank=True, null=True, upload_to='courses/')),
                ('link_video', models.URLField(blank=True, null=True)),
                ('description', models.TextField()),
                ('sort_description', models.CharField(blank=True, max_length=150, null=True)),
                ('hour', models.CharField(blank=True, max_length=2, null=True)),
                ('language', models.CharField(choices=[('en', 'English'), ('id', 'Indonesia'), ('fr', 'French'), ('de', 'German')], default='en', max_length=10)),
                ('start_date', models.DateField(null=True)),
                ('end_date', models.DateField(null=True)),
                ('start_enrol', models.DateField(null=True)),
                ('end_enrol', models.DateField(null=True)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('category', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='category_courses', to='courses.category')),
                ('status_course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='courses', to='courses.coursestatus')),
            ],
        ),
        migrations.CreateModel(
            name='CourseStatusHistory',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('status', models.CharField(choices=[('draft', 'Draft'), ('curation', 'Curation'), ('published', 'Published'), ('archived', 'Archived')], max_length=20)),
                ('manual_message', models.TextField(blank=True, null=True)),
                ('changed_at', models.DateTimeField(auto_now_add=True)),
                ('changed_by', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='status_history', to='courses.course')),
            ],
            options={
                'ordering': ['-changed_at'],
            },
        ),
        migrations.CreateModel(
            name='GradeRange',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('name', models.CharField(max_length=255)),
                ('min_grade', models.DecimalField(decimal_places=2, max_digits=5)),
                ('max_grade', models.DecimalField(decimal_places=2, max_digits=5)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='grade_ranges', to='courses.course')),
            ],
        ),
        migrations.CreateModel(
            name='CourseProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('progress', models.FloatField(default=0)),
                ('progress_percentage', models.FloatField(default=0)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.course')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('grade', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='courses.graderange')),
            ],
        ),
        migrations.AddField(
            model_name='assessment',
            name='grade_range',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='assessments', to='courses.graderange'),
        ),
        migrations.CreateModel(
            name='Instructor',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('bio', models.TextField()),
                ('tech', models.CharField(max_length=255)),
                ('expertise', models.CharField(max_length=255)),
                ('experience_years', models.PositiveIntegerField()),
                ('status', models.CharField(choices=[('Pending', 'Pending'), ('Approved', 'Approved'), ('Rejected', 'Rejected')], default='Pending', max_length=10)),
                ('agreement', models.BooleanField(default=False, help_text='Check if the user agrees to the terms and conditions')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='instructors', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='course',
            name='instructor',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.CASCADE, related_name='courses', to='courses.instructor'),
        ),
        migrations.CreateModel(
            name='MicroCredential',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=250)),
                ('slug', models.CharField(blank=True, max_length=250)),
                ('description', models.TextField()),
                ('status', models.CharField(choices=[('active', 'Active'), ('inactive', 'Inactive'), ('draft', 'Draft')], default='draft', max_length=20)),
                ('start_date', models.DateField(blank=True, null=True)),
                ('end_date', models.DateField(blank=True, null=True)),
                ('image', models.ImageField(blank=True, null=True, upload_to='microcredentials/')),
                ('min_total_score', models.FloatField(default=0.0, help_text='Total minimum score required across all courses')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('edited_on', models.DateTimeField(auto_now=True)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('category', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='microcredentials', to='courses.category')),
                ('required_courses', models.ManyToManyField(related_name='microcredentials', to='courses.course')),
            ],
        ),
        migrations.CreateModel(
            name='Partner',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('phone', models.CharField(blank=True, max_length=50, null=True)),
                ('address', models.TextField(blank=True, max_length=200, null=True)),
                ('description', models.TextField(blank=True, null=True)),
                ('tax', models.DecimalField(decimal_places=2, default=0.0, max_digits=10, verbose_name='Tax (%)')),
                ('iceiprice', models.DecimalField(decimal_places=2, default=0.0, max_digits=10, verbose_name='share icei (%)')),
                ('account_number', models.CharField(blank=True, max_length=20, null=True)),
                ('account_holder_name', models.CharField(blank=True, max_length=250, null=True)),
                ('balance', models.DecimalField(decimal_places=2, default=0.0, max_digits=10)),
                ('logo', models.ImageField(blank=True, null=True, upload_to='logos/')),
                ('created_ad', models.DateTimeField(auto_now_add=True)),
                ('updated_ad', models.DateTimeField(auto_now=True)),
                ('author', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='partner_author', to=settings.AUTH_USER_MODEL)),
                ('name', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='partner_univ', to='auth.universiti')),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='partner_user', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='instructor',
            name='provider',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='instructors', to='courses.partner'),
        ),
        migrations.AddField(
            model_name='course',
            name='org_partner',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='courses', to='courses.partner'),
        ),
        migrations.CreateModel(
            name='CoursePrice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('partner_price', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=15, verbose_name='Partner Price')),
                ('discount_percent', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=5, verbose_name='Discount (%)')),
                ('discount_amount', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Discount Amount')),
                ('ice_share_rate', models.DecimalField(decimal_places=2, default=Decimal('20.00'), max_digits=5, verbose_name='ICE Share (%)')),
                ('admin_fee', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Admin Fee')),
                ('ice_share_value', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='ICE Share Value')),
                ('tax', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Tax (%)')),
                ('ppn_rate', models.DecimalField(decimal_places=2, default=Decimal('11.00'), max_digits=5, verbose_name='PPN Rate (%)')),
                ('ppn', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='PPN')),
                ('sub_total', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Sub Total')),
                ('portal_price', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Portal Price')),
                ('normal_price', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Normal Price')),
                ('platform_fee', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Platform Fee')),
                ('voucher', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Voucher')),
                ('user_payment', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='User Payment')),
                ('partner_earning', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='Partner Earning')),
                ('ice_earning', models.DecimalField(decimal_places=2, default=Decimal('0.00'), max_digits=10, verbose_name='ICE Earning')),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('calculate_admin_price', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='course_prices', to='courses.calculateadminprice')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='prices', to='courses.course')),
                ('partner', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_prices', to='courses.partner')),
                ('price_type', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='course_prices', to='courses.pricingtype')),
            ],
        ),
        migrations.CreateModel(
            name='Question',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('assessment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='questions', to='courses.assessment')),
            ],
        ),
        migrations.CreateModel(
            name='Choice',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('text', models.TextField(blank=True, null=True)),
                ('is_correct', models.BooleanField(default=False)),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='choices', to='courses.question')),
            ],
        ),
        migrations.CreateModel(
            name='QuestionAnswer',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('answered_at', models.DateTimeField(auto_now_add=True)),
                ('choice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.choice')),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.question')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='Section',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100)),
                ('slug', autoslug.fields.AutoSlugField(editable=False, populate_from='title', unique=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('courses', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='sections', to='courses.course')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='children', to='courses.section')),
            ],
            options={
                'verbose_name_plural': 'section',
            },
        ),
        migrations.CreateModel(
            name='Score',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.CharField(max_length=255)),
                ('score', models.IntegerField()),
                ('total_questions', models.IntegerField()),
                ('grade', models.CharField(blank=True, max_length=2)),
                ('time_taken', models.DurationField(blank=True, null=True)),
                ('date', models.DateTimeField(auto_now_add=True)),
                ('submitted', models.BooleanField(default=False)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='scores', to='courses.course')),
                ('section', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='scores', to='courses.section')),
            ],
        ),
        migrations.CreateModel(
            name='Material',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('title', models.CharField(max_length=100)),
                ('description', models.TextField(blank=True, null=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('section', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='materials', to='courses.section')),
            ],
            options={
                'verbose_name_plural': 'materials',
            },
        ),
        migrations.CreateModel(
            name='AttemptedQuestion',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('user', models.CharField(max_length=255)),
                ('is_correct', models.BooleanField()),
                ('date_attempted', models.DateTimeField(auto_now_add=True)),
                ('selected_choice', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.choice')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempted_questions', to='courses.course')),
                ('question', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='attempts', to='courses.question')),
                ('section', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name='attempted_questions', to='courses.section')),
            ],
        ),
        migrations.AddField(
            model_name='assessment',
            name='section',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assessments', to='courses.section'),
        ),
        migrations.CreateModel(
            name='Submission',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('answer_text', models.TextField()),
                ('answer_file', models.FileField(blank=True, null=True, upload_to='submissions/')),
                ('score', models.IntegerField(blank=True, null=True, validators=[django.core.validators.MinValueValidator(0)])),
                ('submitted_at', models.DateTimeField(auto_now_add=True)),
                ('askora', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='submissions', to='courses.askora')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='PeerReview',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('score', models.IntegerField(choices=[(1, 1), (2, 2), (3, 3), (4, 4), (5, 5)])),
                ('comment', models.TextField(blank=True, null=True)),
                ('weight', models.DecimalField(decimal_places=2, default=1.0, max_digits=3)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('reviewer', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('submission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='peer_reviews', to='courses.submission')),
            ],
        ),
        migrations.CreateModel(
            name='AssessmentScore',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('final_score', models.DecimalField(decimal_places=2, default=0, max_digits=5)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('submission', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='assessment_scores', to='courses.submission')),
            ],
        ),
        migrations.CreateModel(
            name='Subscription',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('start_date', models.DateTimeField(auto_now_add=True)),
                ('end_date', models.DateTimeField()),
                ('is_active', models.BooleanField(default=True)),
                ('subscription_type', models.CharField(choices=[('monthly', 'Monthly'), ('yearly', 'Yearly'), ('course_specific', 'Course-Specific')], default='monthly', max_length=50)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='TeamMember',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='team_members', to='courses.course')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='UserMicroCredential',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('completed', models.BooleanField(default=False)),
                ('certificate_id', models.CharField(blank=True, max_length=250, null=True)),
                ('issued_at', models.DateTimeField(blank=True, null=True)),
                ('microcredential', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='users', to='courses.microcredential')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='microcredentials', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='UserMicroProgress',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('progress', models.FloatField(default=0.0)),
                ('score', models.FloatField(default=0.0)),
                ('completed', models.BooleanField(default=False)),
                ('completed_at', models.DateTimeField(blank=True, null=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_progress', to='courses.course')),
                ('microcredential', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='user_progress', to='courses.microcredential')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='micro_progress', to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.CreateModel(
            name='AssessmentRead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('completed_at', models.DateTimeField(auto_now_add=True)),
                ('assessment', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.assessment')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'assessment')},
            },
        ),
        migrations.CreateModel(
            name='CourseComment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('likes', models.IntegerField(default=0)),
                ('dislikes', models.IntegerField(default=0)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.course')),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='courses.coursecomment')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'indexes': [models.Index(fields=['course'], name='courses_cou_course__52454c_idx')],
            },
        ),
        migrations.CreateModel(
            name='Enrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enrolled_at', models.DateTimeField(auto_now_add=True)),
                ('course', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='courses.course')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'course')},
            },
        ),
        migrations.CreateModel(
            name='Comment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('likes', models.IntegerField(default=0)),
                ('dislikes', models.IntegerField(default=0)),
                ('parent', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, to='courses.comment')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
                ('material', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.material')),
            ],
            options={
                'indexes': [models.Index(fields=['material'], name='courses_com_materia_60b869_idx')],
            },
        ),
        migrations.CreateModel(
            name='MaterialRead',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('read_at', models.DateTimeField(auto_now_add=True)),
                ('material', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='courses.material')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'material')},
            },
        ),
        migrations.CreateModel(
            name='MicroCredentialEnrollment',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('enrolled_at', models.DateTimeField(auto_now_add=True)),
                ('microcredential', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='enrollments', to='courses.microcredential')),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='microcredential_enrollments', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'unique_together': {('user', 'microcredential')},
            },
        ),
        migrations.AddIndex(
            model_name='partner',
            index=models.Index(fields=['user'], name='courses_par_user_id_86e67c_idx'),
        ),
        migrations.AlterUniqueTogether(
            name='questionanswer',
            unique_together={('user', 'question')},
        ),
        migrations.AlterUniqueTogether(
            name='section',
            unique_together={('slug', 'parent')},
        ),
        migrations.AlterUniqueTogether(
            name='peerreview',
            unique_together={('submission', 'reviewer')},
        ),
        migrations.AlterUniqueTogether(
            name='usermicroprogress',
            unique_together={('user', 'course', 'microcredential')},
        ),
    ]
