# authentication/views.py
from django.shortcuts import render, redirect,get_object_or_404
import os
from PIL import Image
from io import BytesIO
from django.core.files.base import ContentFile
from django.contrib.auth import authenticate, login,logout
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse,HttpResponseNotAllowed
from django.contrib.sites.shortcuts import get_current_site
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.contrib.auth.tokens import default_token_generator
from .forms import RegistrationForm,LoginForm
from django.conf import settings
from django.contrib import messages
from .models import CustomUser
from django.contrib.auth.forms import PasswordResetForm,SetPasswordForm
from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.urls import reverse
from django.core.mail import send_mail
from authentication.forms import  Userprofile, UserPhoto
from .models import Profile
from courses.models import LastAccessCourse,SearchHistory,Instructor,CourseRating,Partner,Assessment,GradeRange,AssessmentRead,Material, MaterialRead, Submission,AssessmentScore,QuestionAnswer,CourseStatus,Enrollment,MicroCredential, MicroCredentialEnrollment,Course, Enrollment, Category,CourseProgress
from django.http import HttpResponse,JsonResponse
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.http import HttpResponseForbidden
from django.core.cache import cache
from django.db.models import Avg, Count,Q,FloatField
from django.core import serializers
from django.db.models import Count
from django.utils import timezone
from django.views.decorators.csrf import csrf_protect
from decimal import Decimal
from django.urls import reverse
from django_ratelimit.decorators import ratelimit
from django.http import HttpResponseNotAllowed, HttpResponseNotFound
from django.core.cache import cache
from django.views.decorators.cache import cache_page
from django.db.models import Prefetch
from django.core.mail import EmailMultiAlternatives,EmailMessage
from django.db.models.functions import Coalesce
from blog.models import BlogPost
from django.views.decorators.http import require_GET
import html
import re
from django.views.decorators.http import require_http_methods
import logging

def about(request):
    return render(request, 'home/about.html')


def mycourse(request):
    if request.user.is_authenticated:
        courses = Enrollment.objects.filter(user=request.user)

        if request.method != 'GET':
            return HttpResponseNotAllowed("Metode tidak diperbolehkan")
        
        search_query = request.GET.get('search', '')
        if search_query:
            courses = courses.filter(Q(course__course_name__icontains=search_query))

        courses = courses.order_by('-enrolled_at')
        paginator = Paginator(courses, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Ambil semua LastAccess untuk user ini
        last_access_list = LastAccessCourse.objects.filter(user=request.user)
        last_access_map = { la.course_id: la for la in last_access_list }

        return render(request, 'learner/mycourse_list.html', {
            'page_obj': page_obj,
            'search_query': search_query,
            'last_access_map': last_access_map,
        })

    return redirect("/login/?next=%s" % request.path)

def microcredential_list(request):
    if request.user.is_authenticated:
        # Mengambil semua MicroCredential yang diambil oleh user yang sedang login
        microcredentials = MicroCredentialEnrollment.objects.filter(user=request.user)
        # Jika metode bukan GET, batalkan
        if request.method != 'GET':
            return HttpResponseNotAllowed("Metode tidak diperbolehkan")
        
        # Pencarian (Search)
        search_query = request.GET.get('search', '')
        if search_query:
            # Menambahkan filter pencarian berdasarkan judul atau nama microcredential
            microcredentials = microcredentials.filter(Q(microcredential__title__icontains=search_query))

        # Add order_by to ensure consistent pagination
        microcredentials = microcredentials.order_by('microcredential__title')  # Change 'title' to your preferred field

        # Pagination
        paginator = Paginator(microcredentials, 10)  # 10 item per halaman
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)

        # Render template dengan data microcredentials dan pagination
        return render(request, 'learner/microcredential_list.html', {
            'page_obj': page_obj,
            'search_query': search_query
        })

    # Jika user belum login, redirect ke halaman login
    return redirect("/login/?next=%s" % request.path)



#course_list lms
@ratelimit(key='ip', rate='100/h')
@cache_page(60 * 15)  # Cache the page for 15 minutes
def course_list(request):
    if request.method != 'GET':
        return HttpResponseNotAllowed("Metode tidak diperbolehkan")

    published_status = CourseStatus.objects.filter(status='published').first()
    if not published_status:
        return HttpResponseNotFound("Status 'published' tidak ditemukan")

    # Ambil courses dengan select_related dan prefetch_related untuk optimasi query
    courses = Course.objects.filter(
        status_course=published_status,
        end_enrol__gte=timezone.now()
    ).select_related(
        'category', 'instructor__user', 'org_partner'
    ).prefetch_related('enrollments')

    category_filter = request.GET.getlist('category')
    language_filter = request.GET.get('language')
    level_filter = request.GET.get('level')  # Menangkap filter level

    if category_filter:
        courses = courses.filter(category__in=category_filter)
    if language_filter:
        courses = courses.filter(language=language_filter)
    if level_filter:  # Menambahkan filter level
        courses = courses.filter(level=level_filter)

    paginator = Paginator(courses, 9)
    page_number = request.GET.get('page', 1)

    try:
        page_obj = paginator.get_page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    # Kategori dengan jumlah course
    categories = Category.objects.filter(
        category_courses__status_course=published_status,
        category_courses__end_enrol__gte=timezone.now()
    ).annotate(course_count=Count('category_courses')).distinct()

    # Daftar bahasa unik dari hasil courses terfilter
    language_codes = courses.values_list('language', flat=True).distinct()
    all_languages = dict(Course.choice_language)
    language_options = [{'code': code, 'name': all_languages.get(code, code)} for code in language_codes]

    # Siapkan data untuk ditampilkan
    courses_data = []
    total_enrollments = 0

    # Ambil ratings dan enrollments terkait
    for course in page_obj:
        review_qs = CourseRating.objects.filter(course=course)
        average_rating = round(review_qs.aggregate(avg=Avg('rating'))['avg'] or 0, 1)
        full_stars = int(average_rating)
        half_star = (average_rating % 1) >= 0.5
        empty_stars = 5 - full_stars - (1 if half_star else 0)

        num_enrollments = course.enrollments.count()
        total_enrollments += num_enrollments

        courses_data.append({
            'course_name': course.course_name,
            'hour': course.hour,
            'course_id': course.id,
            'num_enrollments': num_enrollments,
            'course_slug': course.slug,
            'course_image': course.image.url if course.image else None,
            'instructor': course.instructor.user.get_full_name() if course.instructor else None,
            'instructor_username': course.instructor.user.username if course.instructor else None,
            'photo': course.instructor.user.photo.url if course.instructor and course.instructor.user.photo else None,
            'partner': course.org_partner.name if course.org_partner else None,
            'partner_kode': course.org_partner.name.kode if course.org_partner else None,
            'category': course.category.name if course.category else None,
            'language': course.get_language_display(),  # ← ini
            'level': course.level,  # Menambahkan level ke data
            'average_rating': average_rating,
            'review_count': review_qs.count(),
            'full_star_range': range(full_stars),
            'half_star': half_star,
            'empty_star_range': range(empty_stars),
        })

    context = {
        'courses': courses_data,
        'page_obj': page_obj,
        'total_courses': courses.count(),
        'total_enrollments': total_enrollments,
        'total_pages': paginator.num_pages,
        'current_page': page_obj.number,
        'start_index': page_obj.start_index(),
        'end_index': page_obj.end_index(),
        'category_filter': category_filter,
        'language_filter': language_filter,
        'level_filter': level_filter,  # Menambahkan level_filter ke context
        'categories': list(categories.values('id', 'name', 'course_count')),
        'language_options': language_options,
    }

    return render(request, 'home/course_list.html', context)





#detailuser
@login_required
@ratelimit(key='ip', rate='100/h')
def user_detail(request, user_id):
    # Ambil pengguna berdasarkan user_id
    user = get_object_or_404(CustomUser, id=user_id)

    # Ambil daftar enrollment untuk pengguna ini
    enrollments = Enrollment.objects.filter(user=user).select_related('course')

    # Implementasi pencarian berdasarkan course_name
    search_query = request.GET.get('search', '')
    if search_query:
        enrollments = enrollments.filter(course__course_name__icontains=search_query)

    # Siapkan data untuk pagination
    course_details = []
    for enrollment in enrollments:
        course = enrollment.course

        # Ambil total skor dan status dari setiap kursus
        total_max_score = 0
        total_score = 0
        all_assessments_submitted = True  # Untuk memastikan semua asesmen diselesaikan

        # Ambil grade range untuk kursus tersebut
        grade_range = GradeRange.objects.filter(course=course).first()
        passing_threshold = grade_range.min_grade if grade_range else 0

        # Hitung skor dari asesmen
        assessments = Assessment.objects.filter(section__courses=course)
        for assessment in assessments:
            score_value = Decimal(0)
            total_correct_answers = 0
            total_questions = assessment.questions.count()

            if total_questions > 0:  # Multiple choice
                answers_exist = False
                for question in assessment.questions.all():
                    answers = QuestionAnswer.objects.filter(question=question, user=user)
                    if answers.exists():
                        answers_exist = True
                    total_correct_answers += answers.filter(choice__is_correct=True).count()
                if not answers_exist:
                    all_assessments_submitted = False
                if total_questions > 0:
                    score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
            # Anda bisa tambahkan logika untuk AskOra di sini jika relevan (seperti di dashbord)

            total_max_score += assessment.weight
            total_score += score_value

        # Hitung persentase skor
        overall_percentage = (total_score / total_max_score) * 100 if total_max_score > 0 else 0

        # Ambil progress dari CourseProgress
        course_progress = CourseProgress.objects.filter(user=user, course=course).first()
        progress_percentage = course_progress.progress_percentage if course_progress else 0

        # Tentukan status kelulusan
        status = "Fail"  # Default status
        if progress_percentage == 100 and all_assessments_submitted and overall_percentage >= passing_threshold:
            status = "Pass"

        # Tambahkan detail kursus ke daftar
        course_details.append({
            'course_name': course.course_name,
            'total_score': total_score,
            'total_max_score': total_max_score,
            'status': status,
            'progress_percentage': progress_percentage,  # Untuk debug atau tampilan
            'overall_percentage': overall_percentage,    # Untuk debug atau tampilan
        })

    # Pagination untuk hasil kursus
    paginator = Paginator(course_details, 5)  # 5 kursus per halaman
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'user': user,
        'course_details': page_obj,
        'search_query': search_query,
    }
    
    return render(request, 'authentication/user_detail.html', context)

@login_required
@ratelimit(key='ip', rate='100/h')
def all_user(request):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    # Role-based filtering
    if request.user.is_superuser:
        # Superuser can access all users
        users = CustomUser.objects.all().order_by('-date_joined')
    elif request.user.is_partner:
        # Partner can only access users related to their university, excluding superusers
        if request.user.university:
            users = CustomUser.objects.filter(
                university=request.user.university, 
                is_superuser=False
            ).order_by('-date_joined')
        else:
            # If the partner has no associated university, deny access
            return HttpResponseForbidden("You are not associated with any university.")
    else:
        # If not superuser or partner, show only self data
        users = CustomUser.objects.filter(id=request.user.id).order_by('-date_joined')

    # Get filters from GET request
    search_query = request.GET.get('search', '').strip()
    status_filter = request.GET.get('status', '').strip()
    date_from = request.GET.get('date_from', '').strip()
    date_to = request.GET.get('date_to', '').strip()
    page_number = request.GET.get('page', 1)

    # Search functionality
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) | 
            Q(email__icontains=search_query) |
            Q(first_name__icontains=search_query)
        )

    # Status filter
    if status_filter:
        if status_filter == 'active':
            users = users.filter(is_active=True)
        elif status_filter == 'inactive':
            users = users.filter(is_active=False)

    # Date filters
    if date_from:
        users = users.filter(date_joined__gte=date_from)
    if date_to:
        users = users.filter(date_joined__lte=date_to)

    # Annotate the total courses enrolled by each user
    users = users.annotate(total_courses=Count('enrollments'))

    # Get the total count of users (before pagination and filtering)
    total_user_count = users.count()

    # Paginate the results
    paginator = Paginator(users, 10)  # Show 10 users per page
    page_obj = paginator.get_page(page_number)

    # Render the template with user data and the total count
    context = {
        'users': page_obj,
        'search_query': search_query,
        'total_user_count': total_user_count,
        'status_filter': status_filter,
        'date_from': date_from,
        'date_to': date_to,
    }

    return render(request, 'authentication/all_user.html', context)


@login_required
@ratelimit(key='ip', rate='100/h')
def dasbord(request):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)


    user = request.user
    required_fields = {
        'first_name': 'Nama Depan',
        'last_name': 'Nama Belakang',
        'email': 'Email',
        'phone': 'Nomor Telepon',
        'gender': 'Jenis Kelamin',
        'birth': 'Tanggal Lahir',
    }
    missing_fields = [label for field, label in required_fields.items() if not getattr(user, field)]

    if missing_fields:
        messages.warning(request, f"Harap lengkapi data berikut: {', '.join(missing_fields)}")
        return redirect('authentication:edit-profile', pk=user.pk)

    # Get page number from GET parameters
    courses_page = request.GET.get('courses_page', 1)

    # Initialize variables
    partner_courses = None
    partner_enrollments = None
    total_enrollments = 0
    total_courses = 0
    total_instructors = 0
    total_learners = 0
    total_partners = 0
    total_published_courses = 0

    try:
        publish_status = CourseStatus.objects.get(status='published')
    except CourseStatus.DoesNotExist:
        publish_status = None

    # Logic based on user role
    if request.user.is_superuser:
        # Superuser: Access to all data
        total_enrollments = Enrollment.objects.count()
        total_courses = Course.objects.count()
        total_instructors = Instructor.objects.count()
        total_learners = CustomUser.objects.filter(is_learner=True).count()
        total_partners = Partner.objects.count()
        total_published_courses = Course.objects.filter(status_course=publish_status).count() if publish_status else 0
        partner_courses = Course.objects.all()  # Superuser sees all courses
    elif request.user.is_partner:
        # Partner: Access to data related to their organization
        try:
            partner = Partner.objects.get(user=request.user)  # Assuming Partner has a ForeignKey to CustomUser
        except Partner.DoesNotExist:
            partner = None

        if partner:
            # Courses associated with the partner's organization
            partner_courses = Course.objects.filter(org_partner=partner)
            # Enrollments in the partner's courses
            partner_enrollments = Enrollment.objects.filter(course__org_partner=partner)
            # Total enrollments for the partner
            total_enrollments = partner_enrollments.count()
            # Total courses for the partner
            total_courses = partner_courses.count()
            # Total instructors associated with the partner's courses
            total_instructors = Instructor.objects.filter(courses__org_partner=partner).distinct().count()
            # Total learners enrolled in the partner's courses
            total_learners = CustomUser.objects.filter(
                enrollments__course__org_partner=partner,
                is_learner=True
            ).distinct().count()
            # Total published courses for the partner
            total_published_courses = partner_courses.filter(status_course=publish_status).count() if publish_status else 0
        else:
            # If partner not found, set defaults
            partner_courses = Course.objects.none()
            total_enrollments = 0
            total_courses = 0
            total_instructors = 0
            total_learners = 0
            total_published_courses = 0
    elif request.user.is_instructor:
        # Instructor: Access to data related to themselves only
        try:
            instructor = Instructor.objects.get(user=request.user)  # Assuming Instructor has a ForeignKey to CustomUser
        except Instructor.DoesNotExist:
            instructor = None

        if instructor:
            # Courses taught by this instructor
            partner_courses = Course.objects.filter(instructor=instructor)
            # Enrollments in the instructor's courses
            partner_enrollments = Enrollment.objects.filter(course__instructor=instructor)
            # Total enrollments in the instructor's courses
            total_enrollments = partner_enrollments.count()
            # Total courses taught by the instructor
            total_courses = partner_courses.count()
            # Total instructors (just the instructor themselves)
            total_instructors = 1
            # Total learners enrolled in the instructor's courses
            total_learners = CustomUser.objects.filter(
                enrollments__course__instructor=instructor,
                is_learner=True
            ).distinct().count()
            # Total published courses by the instructor
            total_published_courses = partner_courses.filter(status_course=publish_status).count() if publish_status else 0
        else:
            # If instructor not found, set defaults
            partner_courses = Course.objects.none()
            total_enrollments = 0
            total_courses = 0
            total_instructors = 0
            total_learners = 0
            total_published_courses = 0
    else:
        # Default case for users who are neither superuser, partner, nor instructor
        partner_courses = Course.objects.none()
        total_enrollments = 0
        total_courses = 0
        total_instructors = 0
        total_learners = 0
        total_published_courses = 0

    # Get the current date
    today = timezone.now().date()

    # Filter courses created today
    if partner_courses is not None and partner_courses.exists():
        courses_created_today = partner_courses.filter(
            created_at__date=today,
        ).order_by('created_at')
        # Pagination for courses created today
        courses_paginator = Paginator(courses_created_today, 5)  # 5 courses per page
        courses_created_today = courses_paginator.get_page(courses_page)
    else:
        courses_created_today = []

    # Context for the template
    context = {
        'courses_page': courses_page,
        'total_enrollments': total_enrollments,
        'total_courses': total_courses,
        'total_instructors': total_instructors,
        'total_learners': total_learners,
        'total_partners': total_partners,
        'total_published_courses': total_published_courses,
        'courses_created_today': courses_created_today,
    }

    return render(request, 'home/dasbord.html', context)

@login_required
@ratelimit(key='ip', rate='100/h')
def dashbord(request):
    user = request.user
    required_fields = {
        'first_name': 'Nama Depan',
        'last_name': 'Nama Belakang',
        'email': 'Email',
        'phone': 'Nomor Telepon',
        'gender': 'Jenis Kelamin',
        'birth': 'Tanggal Lahir',
    }
    missing_fields = [label for field, label in required_fields.items() if not getattr(user, field)]

    if missing_fields:
        messages.warning(request, f"Harap lengkapi data berikut: {', '.join(missing_fields)}")
        return redirect('authentication:edit-profile', pk=user.pk)

    search_query = request.GET.get('search', '')
    enrollments_page = request.GET.get('enrollments_page', 1)

    enrollments = Enrollment.objects.filter(user=user).order_by('-enrolled_at')

    if search_query:
        enrollments = enrollments.filter(
            Q(user__username__icontains=search_query) |
            Q(course__course_name__icontains=search_query)
        )

    total_enrollments = enrollments.count()

    active_courses = Course.objects.filter(
        id__in=enrollments.values('course'),
        status_course__status='published',
        start_enrol__lte=timezone.now(),
        end_enrol__gte=timezone.now()
    )

    completed_courses = CourseProgress.objects.filter(user=user, progress_percentage=100)

    enrollments_data = []
    for enrollment in enrollments:
        course = enrollment.course

        # Hitung progress
        materials = Material.objects.filter(section__courses=course)
        total_materials = materials.count()
        materials_read = MaterialRead.objects.filter(user=user, material__in=materials).count()
        materials_read_percentage = (Decimal(materials_read) / Decimal(total_materials) * Decimal('100')) if total_materials > 0 else Decimal('0')

        assessments = Assessment.objects.filter(section__courses=course)
        total_assessments = assessments.count()
        assessments_completed = AssessmentRead.objects.filter(user=user, assessment__in=assessments).count()
        assessments_completed_percentage = (Decimal(assessments_completed) / Decimal(total_assessments) * Decimal('100')) if total_assessments > 0 else Decimal('0')

        progress = ((materials_read_percentage + assessments_completed_percentage) / Decimal('2')) if (total_materials + total_assessments) > 0 else Decimal('0')

        course_progress, created = CourseProgress.objects.get_or_create(user=user, course=course)
        course_progress.progress_percentage = progress
        course_progress.save()

        # Ambil passing threshold dari GradeRange
        grade_range = GradeRange.objects.filter(course=course, name='Pass').first()
        passing_threshold = grade_range.min_grade if grade_range else Decimal('52.00')
        max_grade = grade_range.max_grade if grade_range else Decimal('100.00')

        # Hitung skor
        total_score = Decimal('0')
        total_max_score = Decimal('0')
        for assessment in assessments:
            score_value = Decimal('0')
            total_questions = assessment.questions.count()

            if total_questions > 0:
                total_correct_answers = 0
                for question in assessment.questions.all():
                    correct = QuestionAnswer.objects.filter(
                        question=question, user=user, choice__is_correct=True
                    ).count()
                    total_correct_answers += correct
                score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
            else:
                submissions = Submission.objects.filter(askora__assessment=assessment, user=user)
                if submissions.exists():
                    latest = submissions.order_by('-submitted_at').first()
                    score_obj = AssessmentScore.objects.filter(submission=latest).first()
                    if score_obj:
                        score_value = Decimal(score_obj.final_score)
            total_score += score_value
            total_max_score += Decimal(assessment.weight)

        overall_percentage = (total_score / total_max_score * Decimal('100')) if total_max_score > 0 else Decimal('0')
        certificate_eligible = progress == Decimal('100') and overall_percentage >= passing_threshold
        certificate_issued = getattr(enrollment, 'certificate_issued', False)

        enrollments_data.append({
            'enrollment': enrollment,
            'progress': float(progress),  # Convert to float for template display
            'certificate_eligible': certificate_eligible,
            'certificate_issued': certificate_issued,
            'overall_percentage': float(overall_percentage),
            'passing_threshold': float(passing_threshold),
        })

    enrollments_paginator = Paginator(enrollments_data, 5)
    enrollments_page_obj = enrollments_paginator.get_page(enrollments_page)

    return render(request, 'learner/dashbord.html', {
        'enrollments': enrollments_page_obj,
        'search_query': search_query,
        'enrollments_page': enrollments_page,
        'total_enrollments': total_enrollments,
        'active_courses': active_courses,
        'completed_courses': completed_courses,
    })

@login_required
@ratelimit(key='ip', rate='100/h')
def pro(request,username):
    if request.user.is_authenticated:
        username=CustomUser.objects.get(username=username)
        instructor = Instructor.objects.filter(user=username).first()

        return render(request,'home/profile.html',{

            'user': username,

            'instructor': instructor,  # This will be None if the user is not an instructor

        })
    return redirect("/login/?next=%s" % request.path)

@login_required
def edit_profile(request, pk):
    # Pastikan hanya pengguna sendiri yang bisa edit
    user = get_object_or_404(CustomUser, pk=pk)
    if user != request.user:
        messages.error(request, "Anda tidak memiliki izin untuk mengedit profil ini.")
        return redirect('authentication:dashbord')

    if request.method == "GET":
        form = Userprofile(instance=user)
        return render(request, 'home/edit_profile_form.html', {'form': form})

    elif request.method == "POST":
        form = Userprofile(request.POST, request.FILES, instance=user)
        if form.is_valid():
            form_instance = form.save(commit=False)
            # Pertahankan foto jika tidak ada file baru
            if not request.FILES.get('photo'):
                form_instance.photo = user.photo
            form_instance.save()
            # Cek apakah request adalah AJAX
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': True, 'message': 'Profil berhasil diperbarui!'})
            else:
                messages.success(request, "Profil Anda berhasil diperbarui.")
                return redirect('authentication:dashbord')
        else:
            # Untuk AJAX, kembalikan error sebagai JSON
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'success': False, 'errors': form.errors}, status=400)
            # Untuk non-AJAX, render ulang form
            return render(request, 'home/edit_profile_form.html', {'form': form})
#convert image before update

# Fungsi untuk memproses gambar menjadi format WebP
def process_image_to_webp(uploaded_photo):
    # Menggunakan PIL untuk membuka gambar yang diunggah
    img = Image.open(uploaded_photo)
    
    # Membuat buffer untuk menyimpan gambar dalam format WebP
    buffer = BytesIO()
    img.save(buffer, format="WEBP")
    webp_image = buffer.getvalue()  # Ambil data gambar dalam format WebP
    
    # Mengembalikan file gambar dalam format WebP
    return ContentFile(webp_image, name=uploaded_photo.name.split('.')[0] + '.webp')


#update image
@login_required
@ratelimit(key='ip', rate='100/h')
def edit_photo(request, pk):
    # Mendapatkan pengguna berdasarkan primary key (ID)
    user = get_object_or_404(CustomUser, pk=pk)

    if request.method == "GET":
        # Menampilkan formulir pengeditan foto
        form = UserPhoto(instance=user)
        return render(request, 'home/edit_photo.html', {'form': form})

    elif request.method == "POST":
        # Menyimpan jalur foto lama untuk penghapusan nanti
        old_photo_path = user.photo.path if user.photo else None
        
        # Membuat instance formulir dengan data POST dan file yang diunggah
        form = UserPhoto(request.POST, request.FILES, instance=user)

        if form.is_valid():
            # Simpan perubahan formulir tanpa menyimpan langsung ke DB
            user_profile = form.save(commit=False)

            # Cek jika ada file foto yang diunggah
            if 'photo' in request.FILES:
                uploaded_photo = request.FILES['photo']
                # Proses gambar menjadi format WebP
                processed_photo = process_image_to_webp(uploaded_photo)
                # Update foto pengguna
                user_profile.photo = processed_photo

            # Simpan perubahan pengguna
            user_profile.save()

            # Jika ada foto lama, hapus file lama tersebut
            if old_photo_path and os.path.exists(old_photo_path):
                os.remove(old_photo_path)

            # Redirect setelah berhasil menyimpan perubahan
            return redirect(reverse('authentication:edit-photo', args=[pk]))

        else:
            # Jika form tidak valid, tampilkan kembali form dengan status 400
            return render(request, 'home/edit_photo.html', {'form': form}, status=400)


@login_required
@ratelimit(key='ip', rate='100/h')
def edit_profile_save(request, pk):
    # Ensure the profile exists, fetching by pk
    profile = get_object_or_404(CustomUser, pk=pk)

    if request.method == "POST":
        # Create a form instance bound to the profile
        form = Userprofile(request.POST,request.FILES, instance=profile)
        if form.is_valid():
            form.save()
            # Render the updated profile details
            return render(request, 'home/profile_detail.html', {'user': profile})
        else:
            # Return the form with errors and a 400 status code
            return render(request, 'home/edit_profile_form.html', {'form': form}, status=400)

    # If the method is not POST, handle it gracefully (e.g., redirect)
    return JsonResponse({'error': 'Invalid request method'}, status=405)


#populercourse
@ratelimit(key='ip', rate='100/h')
@require_GET
def popular_courses(request):
    now = timezone.now().date()

    try:
        published_status = CourseStatus.objects.get(status='published')
    except CourseStatus.DoesNotExist:
        return JsonResponse({'error': 'Published status not found.'}, status=404)

    courses = Course.objects.filter(
        status_course=published_status,
        end_date__gte=now
    ).annotate(
        num_enrollments=Count('enrollments'),
        avg_rating=Coalesce(Avg('ratings__rating'), 0.0),
        num_ratings=Count('ratings'),
        unique_raters=Count('ratings__user', distinct=True)
    ).order_by('-num_enrollments').select_related(
        'instructor__user', 'org_partner__name', 'org_partner'
    )

    paginator = Paginator(courses, 4)
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.get_page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)

    courses_list = []
    for course in page_obj:
        avg_rating = course.avg_rating
        full_stars = int(avg_rating)
        half_star = (avg_rating % 1) >= 0.5
        empty_stars = 5 - full_stars - (1 if half_star else 0)

        courses_list.append({
            'id': course.id,
            'course_name': course.course_name,
            'slug': course.slug,
            'image': course.image.url if course.image else '',
            'instructor_name': f"{course.instructor.user.first_name} {course.instructor.user.last_name}".strip(),
            'instructor_photo': course.instructor.user.photo.url if course.instructor.user.photo else '',
            'org_name': course.org_partner.name.name,
            'org_kode': course.org_partner.name.kode,
            'org_slug': course.org_partner.name.slug,
            'org_logo': course.org_partner.logo.url if course.org_partner.logo else '',
            'num_enrollments': course.num_enrollments,
            'avg_rating': float(avg_rating),
            'num_ratings': course.unique_raters,
            'full_stars': full_stars,
            'half_star': half_star,
            'empty_stars': empty_stars
        })

    return JsonResponse({'courses': courses_list})


def home(request):
    if request.method != 'GET':
        return HttpResponseNotAllowed("Metode tidak diperbolehkan")

    published_status = CourseStatus.objects.filter(status='published').first()

    # Inisialisasi variabel default
    popular_categories = []
    popular_microcredentials = []
    partners = []
    instructors_page = None
    latest_articles = []

    total_instructors = 0
    total_partners = 0
    total_users = 0
    total_courses = 0

    if published_status:
        # Kategori populer dengan jumlah kursus aktif
        popular_categories = Category.objects.annotate(
            num_courses=Count(
                'category_courses',
                filter=Q(
                    category_courses__status_course=published_status,
                    category_courses__end_enrol__gte=timezone.now()
                )
            )
        ).order_by('-num_courses')[:4]

        # Microcredential aktif
        popular_microcredentials = MicroCredential.objects.filter(
            status='active'
        ).order_by('-created_at')[:6]

        # Mitra dengan urutan
        partners = Partner.objects.all().order_by('id')

        # Instruktur disetujui dengan urutan
        instructors = Instructor.objects.filter(status='Approved').order_by('id')

        if instructors.exists():
            instructor_paginator = Paginator(instructors, 6)
            page_number = request.GET.get('instructor_page')
            instructors_page = instructor_paginator.get_page(page_number)
            total_instructors = instructors.count()

        total_partners = partners.count()
        total_users = CustomUser.objects.count()
        total_courses = Course.objects.filter(
            status_course=published_status,
            end_enrol__gte=timezone.now()
        ).count()

        latest_articles = BlogPost.objects.filter(
            status='published'
        ).order_by('-date_posted')[:2]

    # Pagination untuk partners
    partner_paginator = Paginator(partners, 6)
    page_number = request.GET.get('partner_page')
    page_obj = partner_paginator.get_page(page_number)

    return render(request, 'home/index.html', {
        'popular_categories': popular_categories,
        'popular_microcredentials': popular_microcredentials,
        'partners': page_obj,
        'total_instructors': total_instructors,
        'total_partners': total_partners,
        'total_users': total_users,
        'total_courses': total_courses,
        'instructors': instructors_page,
        'latest_articles': latest_articles,
    })

logger = logging.getLogger(__name__)
@csrf_protect
@ratelimit(key='ip', rate='100/h')  # Bisa diperbarui ke 'user:ip' jika memungkinkan
@require_http_methods(["GET", "POST"])  # Gantikan pengecekan manual metode
def search(request):
    # Pengecekan Referer
    referer = request.headers.get('Referer', '')
    if not referer.startswith(settings.ALLOWED_REFERER):
        logger.warning(f"Invalid referer: {referer} from IP {request.META.get('REMOTE_ADDR')}")
        return HttpResponseForbidden("Akses ditolak: sumber tidak sah")

    # Handle penghapusan riwayat (POST request)
    if request.method == 'POST' and request.user.is_authenticated:
        if request.POST.get('clear_history') == '1':
            SearchHistory.objects.filter(user=request.user).delete()
            logger.info(f"User {request.user.id} deleted their search history.")
            messages.success(request, "Riwayat pencarian berhasil dihapus.")
            return redirect(reverse('authentication:home'))

    # Sanitasi dan validasi input
    query = html.escape(request.GET.get('q', '').strip()[:255])  # Batasi panjang query
    query = re.sub(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', '[email]', query)
    query = re.sub(r'\b\d{10,}\b', '[number]', query)

    try:
        page_number = int(request.GET.get('page', 1))
        if page_number < 1:
            page_number = 1
    except (ValueError, TypeError):
        page_number = 1

    results = {
        'courses': [],
        'instructors': [],
        'partners': [],
        'blog_posts': [],
    }
    search_history = []
    base_url = request.build_absolute_uri('/')

    if query:
        # Pencarian Courses
        results['courses'] = Course.objects.filter(
            Q(course_name__icontains=query) | 
            Q(description__icontains=query),
            status_course__status='published',
            end_enrol__gte=timezone.now()
        ).select_related('instructor', 'org_partner')[:5]

        # Pencarian Instructors
        results['instructors'] = Instructor.objects.filter(
            Q(user__email__icontains=query) | 
            Q(bio__icontains=query)
        ).select_related('user')[:5]

        # Pencarian Partners
        results['partners'] = Partner.objects.filter(
            Q(name__name__icontains=query) | 
            Q(description__icontains=query)
        ).select_related('name')[:5]

        # Pencarian Blog Posts
        blog_posts = BlogPost.objects.filter(
            Q(title__icontains=query) |
            Q(content__icontains=query) |
            Q(tags__name__icontains=query) |
            Q(related_courses__course_name__icontains=query),
            status='published'
        ).select_related('author', 'category').prefetch_related('tags', 'related_courses')[:50]

        # Simpan kata kunci pencarian
        if request.user.is_authenticated:
            if not SearchHistory.objects.filter(user=request.user, keyword=query).exists():
                SearchHistory.objects.create(user=request.user, keyword=query)
        else:
            if not request.session.session_key:
                request.session.create()
            cache_key = f"search_history_anonymous_{request.session.session_key}"
            history = cache.get(cache_key, [])
            if query not in history:
                history.append(query)
                history = history[-10:]  # Batasi 10 entri
                cache.set(cache_key, history, timeout=24*60*60)

    # Ambil riwayat pencarian
    if request.user.is_authenticated:
        search_history = SearchHistory.objects.filter(user=request.user).order_by('-search_date')[:10]
    else:
        cache_key = f"search_history_anonymous_{request.session.session_key}"
        search_history = cache.get(cache_key, [])

    # Pagination untuk blog posts
    paginator = Paginator(results['blog_posts'], 6)
    page_number = min(page_number, paginator.num_pages)  # Batasi halaman maksimum
    page_obj = paginator.get_page(page_number)
    results['blog_posts'] = page_obj

    return render(request, 'home/results.html', {
        'query': query,
        'results': results,
        'search_history': search_history,
        'base_url': base_url,
        'page_obj': page_obj,
    })


# Logout view
def logout_view(request):
    logout(request)
    return redirect('authentication:home')  # Redirect to home page after logout


# Login view
def login_view(request):
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            email = form.cleaned_data['email']
            password = form.cleaned_data['password']
            user = authenticate(request, username=email, password=password)

            if user is not None:
                login(request, user)
                next_url = request.POST.get('next') or request.GET.get('next')
                if next_url:
                    return redirect(next_url)
                #return redirect('home') 
                return redirect('authentication:home')  # Redirect to home after login
            else:
                return render(request, 'authentication/login.html', {'form': form, 'error': 'Invalid email or password'})

    else:
        form = LoginForm()

    return render(request, 'authentication/login.html', {'form': form})

# Register view
def register_view(request):
    if request.method == "POST":
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data["password1"])
            user.is_active = False
            user.save()

            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(str(user.pk).encode())

            current_site = get_current_site(request)
            mail_subject = 'Activate your account'
            html_message = render_to_string('authentication/email_activation/activate_email_message.html', {
                'user': user,
                'domain': current_site.domain,
                'uid': uid,
                'token': token,
            })
            # Versi teks biasa sebagai fallback
            plain_message = f"Hi {user.username},\nPlease activate your account by visiting: http://{current_site.domain}/activate/{uid}/{token}/"

            # Menggunakan EmailMultiAlternatives
            email = EmailMultiAlternatives(
                subject=mail_subject,
                body=plain_message,  # Teks biasa
                from_email='noreply@yourdomain.com',
                to=[user.email],
            )
            email.attach_alternative(html_message, "text/html")  # Menambahkan versi HTML
            email.send()

            return HttpResponse('Registration successful! Please check your email to activate your account.')
    else:
        form = RegistrationForm()
    return render(request, 'authentication/register.html', {'form': form})

# Account activation view
def activate_account(request, uidb64, token):
    try:
        # Decode uidb64 to get the user ID
        uid = urlsafe_base64_decode(uidb64).decode('utf-8')  # Decode back to string
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, CustomUser.DoesNotExist):
        user = None
    
    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True  # Set user to active
        user.save()
        login(request, user)  # Automatically log the user in after activation
        return redirect('authentication:home')  # Redirect to the home page after login
    else:
        return HttpResponse('Activation link is invalid or expired.')



# Custom Password Reset View
def custom_password_reset(request):
    form = PasswordResetForm(request.POST or None)

    if request.method == "POST" and form.is_valid():
        email = form.cleaned_data['email']

        # Cari pengguna berdasarkan email
        try:
            user = CustomUser.objects.get(email=email)  # Gunakan CustomUser langsung
            uid = urlsafe_base64_encode(str(user.pk).encode())
            token = default_token_generator.make_token(user)
        except CustomUser.DoesNotExist:
            # Tetap lanjutkan ke halaman done agar tidak membocorkan info
            return render(request, 'authentication/password_reset_done.html')

        # Tentukan protokol secara dinamis
        protocol = 'https' if request.is_secure() else 'http'
        domain = get_current_site(request).domain

        # Siapkan konteks untuk email
        context = {
            'protocol': protocol,
            'domain': domain,
            'uid': uid,
            'token': token,
        }

        # Render isi email dari template
        email_subject = "Password Reset Request"
        email_message = render_to_string('authentication/password_reset_email.html', context)

        # Kirim email sebagai HTML
        email = EmailMessage(
            subject=email_subject,
            body=email_message,
            from_email='no-reply@yourdomain.com',
            to=[email],
        )
        email.content_subtype = 'html'  # Pastikan email dirender sebagai HTML

        # Tangani error pengiriman email
        try:
            email.send()
        except Exception as e:
            # Log error jika perlu, tapi tetap tampilkan halaman sukses untuk UX
            return HttpResponse("Terjadi kesalahan saat mengirim email. Silakan coba lagi nanti.")

        # Tampilkan halaman konfirmasi
        return render(request, 'authentication/password_reset_done.html')

    # Tampilkan form jika bukan POST atau form tidak valid
    return render(request, 'authentication/password_reset.html', {'form': form})

# Custom Password Reset Done View
def custom_password_reset_done(request):
    return render(request, 'x/password_reset_done.html')

# Custom Password Reset Confirm View
def custom_password_reset_confirm(request, uidb64, token):
    try:
        uid = urlsafe_base64_decode(uidb64).decode('utf-8')
        user = CustomUser.objects.get(pk=uid)
    except (TypeError, ValueError, CustomUser.DoesNotExist):
        user = None
    
    if user and default_token_generator.check_token(user, token):
        if request.method == 'POST':
            form = SetPasswordForm(user, request.POST)
            if form.is_valid():
                form.save()
                return redirect('authentication:password_reset_complete')
            # Jika form tidak valid, tetap render form dengan error
        else:
            form = SetPasswordForm(user)

        return render(request, 'authentication/password_reset_confirm.html', {'form': form})
    
    else:
        return render(request, 'authentication/password_reset_invalid.html')

# Custom Password Reset Complete View
def custom_password_reset_complete(request):
    return render(request, 'authentication/password_reset_complete.html')