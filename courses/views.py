import os
from io import BytesIO
from PIL import Image
from django.conf import settings
from django.core.files.base import ContentFile
from django.core.cache import cache
from django.shortcuts import render, redirect, get_object_or_404
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from .forms import CoursePriceForm,MicroCredentialForm,AskOraForm,CourseForm,CourseRerunForm, PartnerForm,PartnerFormUpdate,CourseInstructorForm, SectionForm,GradeRangeForm, ProfilForm,InstructorForm,InstructorAddCoruseForm,TeamMemberForm, MatrialForm,QuestionForm,ChoiceFormSet,AssessmentForm
from django.http import JsonResponse
from .models import Course,MicroCredentialEnrollment,MicroCredential,AskOra,PeerReview,AssessmentScore,Submission,CourseStatus,AssessmentSession,CourseComment,Comment, Choice,Score,CoursePrice,AssessmentRead,QuestionAnswer,Enrollment,PricingType, Partner,CourseProgress,MaterialRead,GradeRange,Category, Section,Instructor,TeamMember,Material,Question,Assessment
from django.contrib.auth.models import User, Universiti
from django.template.loader import render_to_string
from django.views.decorators.cache import cache_page
from django.urls import reverse
from django.contrib import messages
from django.db.models import F
from django.http import HttpResponseForbidden,HttpResponse
from django_ckeditor_5.widgets import CKEditor5Widget
from django import forms
from django.http import JsonResponse
from decimal import Decimal,ROUND_DOWN
from django.db.models import Sum
from datetime import datetime
from django.db.models import Count
from django.utils.text import slugify
from django.utils import timezone
from django.core.exceptions import ObjectDoesNotExist
from django.db.models import Prefetch
import time
import re
from datetime import timedelta
from django.db.models import Prefetch
from weasyprint import HTML
from django.template.loader import render_to_string
# views.py

def micro_detail(request,id,slug):
    microcredential = get_object_or_404(MicroCredential, id=id, slug=slug)
    return render(request,'micro/micro_detail.html',{'microcredential': microcredential})

def enroll_microcredential(request, slug):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Ambil microcredential berdasarkan slug
    microcredential = get_object_or_404(MicroCredential, slug=slug)

    # Cek apakah microcredential aktif dan dalam periode pendaftaran
    current_date = timezone.now().date()
    if microcredential.status != 'active':
        messages.error(request, "This MicroCredential is not currently active.")
        return redirect('courses:microcredential_detail', slug=slug)
    
    if microcredential.start_date and current_date < microcredential.start_date:
        messages.error(request, "Enrollment has not yet started for this MicroCredential.")
        return redirect('courses:microcredential_detail', slug=slug)
    
    if microcredential.end_date and current_date > microcredential.end_date:
        messages.error(request, "Enrollment has closed for this MicroCredential.")
        return redirect('courses:microcredential_detail', slug=slug)

    # Proses enrollment jika metode adalah POST
    if request.method == 'POST':
        enrollment, created = microcredential.enroll_user(request.user)
        if created:
            messages.success(request, f"You have successfully enrolled in {microcredential.title} and its required courses!")
        else:
            messages.info(request, f"You are already enrolled in {microcredential.title}.")
        return redirect('courses:microcredential_detail', slug=slug)

    # Tampilkan halaman konfirmasi enrollment
    context = {
        'microcredential': microcredential,
        'required_courses': microcredential.required_courses.all(),
        'current_date': current_date,
    }
    return render(request, 'learner/enroll_microcredential.html', context)


def microcredential_detail(request, slug):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Ambil microcredential berdasarkan slug
    microcredential = get_object_or_404(MicroCredential, slug=slug)

    # Cek apakah pengguna sudah terdaftar
    is_enrolled = microcredential.enrollments.filter(user=request.user).exists()

    # Ambil semua kursus yang diperlukan
    required_courses = microcredential.required_courses.all()

    # Hitung status kelulusan dan skor untuk setiap kursus
    course_progress = []
    total_user_score = Decimal(0)
    total_max_score = Decimal(0)
    all_courses_completed = True

    for course in required_courses:
        assessments = Assessment.objects.filter(section__courses=course)
        course_score = Decimal(0)
        course_max_score = Decimal(0)
        course_completed = True

        for assessment in assessments:
            score_value = Decimal(0)
            total_questions = assessment.questions.count()
            if total_questions > 0:  # Multiple choice
                total_correct_answers = 0
                answers_exist = False
                for question in assessment.questions.all():
                    answers = QuestionAnswer.objects.filter(question=question, user=request.user)
                    if answers.exists():
                        answers_exist = True
                    total_correct_answers += answers.filter(choice__is_correct=True).count()
                if not answers_exist:
                    course_completed = False
                if total_questions > 0:
                    score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
            else:  # AskOra
                askora_submissions = Submission.objects.filter(
                    askora__assessment=assessment,
                    user=request.user
                )
                if not askora_submissions.exists():
                    course_completed = False
                else:
                    latest_submission = askora_submissions.order_by('-submitted_at').first()
                    assessment_score = AssessmentScore.objects.filter(submission=latest_submission).first()
                    if assessment_score:
                        score_value = Decimal(assessment_score.final_score)

            score_value = min(score_value, Decimal(assessment.weight))
            course_score += score_value
            course_max_score += assessment.weight

        min_score = Decimal(microcredential.get_min_score(course))
        course_passed = course_completed and course_score >= min_score

        course_progress.append({
            'course': course,
            'user_score': course_score,
            'max_score': course_max_score,
            'min_score': min_score,
            'completed': course_completed,
            'passed': course_passed
        })

        total_user_score += course_score
        total_max_score += course_max_score
        if not course_passed:
            all_courses_completed = False

    microcredential_passed = all_courses_completed and total_user_score >= Decimal(microcredential.min_total_score)

    context = {
        'microcredential': microcredential,
        'course_progress': course_progress,
        'total_user_score': total_user_score,
        'total_max_score': total_max_score,
        'min_total_score': microcredential.min_total_score,
        'microcredential_passed': microcredential_passed,
        'current_date': timezone.now().date(),
        'is_enrolled': is_enrolled,  # Status enrollment
    }

    return render(request, 'learner/microcredential_detail.html', context)


def generate_microcredential_certificate(request, id):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Ambil microcredential berdasarkan ID
    microcredential = get_object_or_404(MicroCredential, id=id)

    # Cek apakah pengguna telah lulus microcredential (opsional)
    required_courses = microcredential.required_courses.all()
    total_user_score = Decimal(0)
    total_max_score = Decimal(0)
    all_courses_completed = True

    for course in required_courses:
        assessments = Assessment.objects.filter(section__courses=course)
        course_score = Decimal(0)
        course_max_score = Decimal(0)
        course_completed = True

        for assessment in assessments:
            score_value = Decimal(0)
            total_questions = assessment.questions.count()
            if total_questions > 0:
                total_correct_answers = 0
                answers_exist = False
                for question in assessment.questions.all():
                    answers = QuestionAnswer.objects.filter(question=question, user=request.user)
                    if answers.exists():
                        answers_exist = True
                    total_correct_answers += answers.filter(choice__is_correct=True).count()
                if not answers_exist:
                    course_completed = False
                if total_questions > 0:
                    score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
            else:
                askora_submissions = Submission.objects.filter(
                    askora__assessment=assessment,
                    user=request.user
                )
                if not askora_submissions.exists():
                    course_completed = False
                else:
                    latest_submission = askora_submissions.order_by('-submitted_at').first()
                    assessment_score = AssessmentScore.objects.filter(submission=latest_submission).first()
                    if assessment_score:
                        score_value = Decimal(assessment_score.final_score)

            score_value = min(score_value, Decimal(assessment.weight))
            course_score += score_value
            course_max_score += assessment.weight

        min_score = Decimal(microcredential.get_min_score(course))
        if not (course_completed and course_score >= min_score):
            all_courses_completed = False
        total_user_score += course_score
        total_max_score += course_max_score

    microcredential_passed = all_courses_completed and total_user_score >= Decimal(microcredential.min_total_score)

    if not microcredential_passed:
        return render(request, 'error_template.html', {'message': 'You have not yet completed this MicroCredential.'})

    # Render template sertifikat
    html_content = render_to_string('learner/microcredential_certificate.html', {
        'microcredential': microcredential,
        'user': request.user,
        'current_date': timezone.now().date(),
    })

    # Generate PDF
    pdf = HTML(string=html_content).write_pdf()
    filename = f"certificate_{microcredential.slug}.pdf"
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response

def deletemic(request, pk):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    if not request.user.is_superuser:
        # Jika pengguna bukan superuser, beri pesan dan arahkan ke halaman lain (misalnya halaman utama)
        messages.error(request, "You do not have permission to delete this microcredential.")
        return redirect('courses:microcredential-list')
    
    microcredential = get_object_or_404(MicroCredential, pk=pk)  # Get the MicroCredential by pk

    if request.method == 'POST':  # Confirm deletion after form submission
        microcredential.delete()
        return redirect('courses:microcredential-list')  # Redirect to the list after deletion

    return render(request, 'micro/delete_micro.html', {'microcredential': microcredential})



def editmic(request, pk):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    microcredential = get_object_or_404(MicroCredential, pk=pk)  # Get the MicroCredential by pk

    if not request.user.is_superuser:
        # Jika pengguna bukan superuser, beri pesan dan arahkan ke halaman lain (misalnya halaman utama)
        messages.error(request, "You do not have permission to edit this microcredential.")
        return redirect('courses:microcredential-list')  

    if request.method == 'POST':
        form = MicroCredentialForm(request.POST, request.FILES, instance=microcredential)  # Prepopulate form with existing data
        if form.is_valid():
            form.save()
            return redirect('courses:microcredential-list')  # Redirect to the list after saving
    else:
        form = MicroCredentialForm(instance=microcredential)

    return render(request, 'micro/edit_micro.html', {'form': form, 'microcredential': microcredential})
def course_autocomplete(request):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    query = request.GET.get('q', '')  # Get the search term
    courses = Course.objects.filter(course_name__icontains=query, status_course__status='published')  # Adjust based on your model
    
    results = [{'id': course.id, 'text': course.course_name} for course in courses]  # Prepare response
    
    return JsonResponse({'results': results})

def addmic(request):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    if not request.user.is_superuser:
        # Jika pengguna bukan superuser, beri pesan dan arahkan ke halaman lain (misalnya halaman utama)
        messages.error(request, "You do not have permission to add this microcredential.")
        return redirect('courses:microcredential-list')
    
    if request.method == 'POST':
        form = MicroCredentialForm(request.POST, request.FILES)  # Handle file uploads for the image field
        if form.is_valid():
            # Automatically set the author field to the logged-in user
            form.instance.author = request.user
            form.save()
            return redirect('courses:microcredential-list')  # Redirect to the list of microcredentials
    else:
        form = MicroCredentialForm()

    return render(request, 'micro/add_micro.html', {'form': form})
    
def detailmic(request, pk):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Fetch the MicroCredential object by its primary key
    microcredential = get_object_or_404(MicroCredential, pk=pk)

    return render(request, 'micro/detail_micro.html', {'microcredential': microcredential})


def listmic(request):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Pencarian berdasarkan query parameter 'search'
    search_query = request.GET.get('search', '')
    if search_query:
        # Filter berdasarkan pencarian
        microcredentials = MicroCredential.objects.filter(title__icontains=search_query)
    else:
        # Ambil semua microcredential jika tidak ada pencarian
        microcredentials = MicroCredential.objects.all()

    # Mengambil data microcredentials dan menghitung jumlah peserta yang terdaftar
    microcredentials = microcredentials.annotate(num_enrollments=Count('enrollments'))

    # Pagination: Menampilkan 10 microcredentials per halaman
    paginator = Paginator(microcredentials, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    return render(request, 'micro/list_micro.html', {'page_obj': page_obj, 'search_query': search_query})


def calculate_score_for_user_and_course(user, course):
    # Implementasikan logika untuk menghitung skor berdasarkan asesmen yang ada
    assessments = Assessment.objects.filter(course=course)
    total_score = 0
    total_max_score = 0

    for assessment in assessments:
        # Hitung skor untuk setiap asesmen berdasarkan jawaban yang benar
        total_correct_answers = 0
        total_questions = assessment.questions.count()

        for question in assessment.questions.all():
            answers = QuestionAnswer.objects.filter(question=question, user=user)
            correct_answers = answers.filter(choice__is_correct=True).count()
            total_correct_answers += correct_answers

        score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
        total_score += score_value
        total_max_score += assessment.weight

    if total_max_score > 0:
        percentage = (total_score / total_max_score) * 100
        # Simpan skor ke dalam Score
        score = Score(user=user, course=course, score=total_score, total_questions=total_max_score, percentage=percentage)
        score.save()
        return score
    return None

    
#ora create question
@csrf_exempt
def create_askora(request, idcourse, idsection, idassessment):
    # Cek apakah pengguna sudah login
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    # Tentukan course berdasarkan peran pengguna
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        messages.error(request, "Anda tidak memiliki izin untuk membuat pertanyaan di kursus ini.")
        return redirect('courses:home')  # Redirect ke halaman aman

    # Pastikan section milik course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Pastikan assessment milik section
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)

    # Menangani form jika metode adalah POST
    if request.method == 'POST':
        # Membuat form untuk AskOra
        question_form = AskOraForm(request.POST)

        # Validasi form
        if question_form.is_valid():
            # Menyimpan AskOra (pertanyaan)
            askora = question_form.save(commit=False)
            askora.assessment = assessment  # Tentukan assessment yang sesuai
            askora.save()  # Simpan pertanyaan

            messages.success(request, "question open response assement successfully to add")
            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)  # Redirect kembali ke halaman yang sama

    else:
        # Menangani GET request
        question_form = AskOraForm()

    return render(request, 'courses/create_ora.html', {
        'course': course,
        'section': section,
        'assessment': assessment,
        'question_form': question_form,
    })


def edit_askora(request, idcourse, idaskora, idsection, idassessment):
    # Fetch the objects needed (course, section, assessment, and askora)
    course = get_object_or_404(Course, id=idcourse)
    section = get_object_or_404(Section, id=idsection)
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)
    askora = get_object_or_404(AskOra, id=idaskora, assessment=assessment)

    # Handle the form submission (POST)
    if request.method == 'POST':
        form = AskOraForm(request.POST, instance=askora)  # pre-populate with the existing data
        if form.is_valid():
            form.save()  # Save the updated AskOra
            messages.success(request, "AskOra question updated successfully!")
            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)
    else:
        form = AskOraForm(instance=askora)  # Populate the form with existing data

    # Render the template with the form
    return render(request, 'courses/edit_askora.html', {
        'course': course,
        'section': section,
        'assessment': assessment,
        'askora': askora,
        'question_form': form  # Pass the form to the template
    })


def delete_askora(request, idcourse, idaskora, idsection, idassessment):
    # Fetch the relevant objects
    course = get_object_or_404(Course, id=idcourse)
    section = get_object_or_404(Section, id=idsection)
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)
    askora = get_object_or_404(AskOra, id=idaskora, assessment=assessment)

    # Check if the user has permission to delete (optional, based on your logic)
    if request.user.is_authenticated:
        

        # Delete the AskOra object
        askora.delete()
        messages.error(request, "AskOra question deleted successfully.")

        # Redirect after deletion
        return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)

    # Redirect if not authenticated
    return redirect("/login/?next=%s" % request.path)


#add coment matrial course
def is_bot(request):
    """
    Mengecek apakah permintaan berasal dari bot.
    Dengan melihat user-agent dan header lainnya.
    """
    user_agent = request.META.get('HTTP_USER_AGENT', '').lower()
    if 'bot' in user_agent or 'crawler' in user_agent:
        return True  # Bot terdeteksi
    return False

def is_spam(request, user, content):
    """
    Memeriksa apakah komentar terdeteksi sebagai spam berdasarkan
    rate-limiting, bot detection dan blacklist keywords.
    """
    # 1. Cek Bot Detection
    if is_bot(request):
        return True  # Bot terdeteksi, komentar dianggap spam
    
    # 2. Cek Rate Limiting (Spam)
    time_limit = timedelta(seconds=30)  # Menentukan batas waktu antara komentar
    last_comment = Comment.objects.filter(user=user).order_by('-created_at').first()
    if last_comment and timezone.now() - last_comment.created_at < time_limit:
        return True  # Terlalu cepat mengirim komentar, dianggap spam
    
    # 3. Cek Kata Kunci yang Diblokir menggunakan metode model
    comment_instance = Comment(user=user, content=content)
    if comment_instance.contains_blacklisted_keywords():
        return True  # Mengandung kata terlarang, dianggap spam
    
    return False

def is_suspicious(request):
    """Check if the request is suspicious based on User-Agent or missing Referer."""
    user_agent = request.META.get('HTTP_USER_AGENT', '')
    referer = request.META.get('HTTP_REFERER', '')
    
    # Bot detection (simple heuristic)
    if 'bot' in user_agent.lower() or not referer:
        return True
    return False

def add_comment(request, material_id):
    # Pastikan pengguna terautentikasi
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Ambil objek material berdasarkan material_id yang diberikan
    material = get_object_or_404(Material, id=material_id)

    # Memastikan bahwa material terhubung dengan kursus dan bagian yang valid
    if material.section:
        if material.section.courses:
            course_slug = material.section.courses.slug
        else:
            # Jika tidak ada kursus yang terhubung, lakukan redirect
            return redirect('courses:course_list')
    else:
        return redirect('courses:course_list')  # Redirect jika bagian tidak ditemukan

    if request.method == 'POST':
        if is_suspicious(request):
            messages.warning(request, "Suspicious activity detected. Comment not posted.")
            return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course_slug}) + f"?material_id={material.id}")
        
        content = request.POST.get('content')
        parent_id = request.POST.get('parent_id')  # Ambil parent_id dari form

        parent_comment = None
        if parent_id:
            parent_comment = get_object_or_404(Comment, id=parent_id)  # Cari komentar induk berdasarkan parent_id

        # Memeriksa apakah komentar adalah spam
        if is_spam(request, request.user, content):
            messages.warning(request, "Komentar Anda terdeteksi sebagai spam!")
            return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course_slug}) + f"?material_id={material.id}")

        # Buat komentar baru atau balasan jika tidak terdeteksi sebagai spam
        Comment.objects.create(
            user=request.user,
            content=content,
            material=material,
            parent=parent_comment  # Menghubungkan balasan dengan komentar induk jika ada
        )

        # Redirect kembali ke halaman kursus
        messages.success(request, "Komentar berhasil diposting!")
        return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course_slug}) + f"?material_id={material.id}")

    # Jika bukan POST, hanya redirect ke halaman material yang sama
    return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course_slug}) + f"?material_id={material.id}")

#add coment course


def add_comment_course(request, course_id):
    #cek akses
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    course = get_object_or_404(Course, id=course_id)

    if request.method == 'POST':
        # Mengecek apakah request mencurigakan (bot detection)
        if is_suspicious(request):
            messages.warning(request, "Suspicious activity detected. Comment not posted.")
            return redirect('course_detail', course_id=course.id)

        content = request.POST.get('content')
        parent_id = request.POST.get('parent_id')
        parent_comment = None

        # Menentukan apakah ini komentar balasan
        if parent_id:
            parent_comment = get_object_or_404(CourseComment, id=parent_id)

        # Membuat objek komentar
        comment = CourseComment(
            user=request.user,
            content=content,
            course=course,
            parent=parent_comment
        )

        # Memeriksa apakah komentar mengandung kata kunci terlarang
        if comment.contains_blacklisted_keywords():
            messages.warning(request, "Your comment contains blacklisted content.")
            return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)

        # Memeriksa apakah komentar adalah spam berdasarkan cooldown
        if comment.is_spam():
            messages.warning(request, "You are posting too frequently. Please wait a moment before posting again.")
            return redirect('course_detail', course_id=course.id)

        comment.save()

        return redirect(request.META.get('HTTP_REFERER'))  # Kembali ke halaman sebelumnya

    return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)





def submit_assessment(request, assessment_id):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Ambil assessment berdasarkan ID
    assessment = get_object_or_404(Assessment, id=assessment_id)
    # Cek honeypot (bot jika terisi)
    honeypot = request.POST.get('honeypot')
    if honeypot:
        messages.error(request, "Spam terdeteksi. Pengiriman dibatalkan.")
        return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': assessment.section.courses.slug}) + f"?assessment_id={assessment.id}")
     # Periksa waktu pengisian form
    start_time = request.POST.get('start_time')
    if start_time:
        elapsed_time = timezone.now() - timezone.make_aware(datetime.datetime.strptime(start_time, '%Y-%m-%d %H:%M:%S'))
        if elapsed_time < timedelta(seconds=10):  # Cegah pengiriman terlalu cepat
            messages.error(request, "Pengiriman terlalu cepat. Coba lagi setelah beberapa detik.")
            return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': assessment.section.courses.slug}) + f"?assessment_id={assessment.id}")
    # Cek apakah user sudah pernah submit untuk assessment ini
    if Score.objects.filter(user=request.user.username, course=assessment.section.courses, section=assessment.section, submitted=True).exists():
        # Redirect dengan membawa assessment_id agar tetap pada posisi yang sama
        messages.info(request, "Anda sudah mengirimkan jawaban untuk ujian ini.")
        return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': assessment.section.courses.slug}) + f"?assessment_id={assessment.id}")

    # Cek apakah waktu ujian masih berlaku
    session = AssessmentSession.objects.filter(user=request.user, assessment=assessment).first()
    if not session:
        messages.error(request, "Sesi ujian tidak ditemukan.")
        return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': assessment.section.courses.slug}) + f"?assessment_id={assessment.id}")

    # Cek apakah waktu ujian sudah habis
    if timezone.now() > session.end_time:
        messages.warning(request, "Waktu ujian telah habis, Anda tidak dapat mengirimkan jawaban.")
        return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': assessment.section.courses.slug}) + f"?assessment_id={assessment.id}")

    if request.method == 'POST':
        correct_answers = 0
        total_questions = assessment.questions.count()

        # Proses setiap soal di assessment
        for question in assessment.questions.all():
            if QuestionAnswer.objects.filter(user=request.user, question=question).exists():
                continue

            user_answer = request.POST.get(f"question_{question.id}")
            if user_answer:
                choice = Choice.objects.get(id=user_answer)
                QuestionAnswer.objects.create(user=request.user, question=question, choice=choice)

                if choice.is_correct:
                    correct_answers += 1

        # Menghitung nilai berdasarkan jawaban yang benar
        score_percentage = (correct_answers / total_questions) * 100
        grade = calculate_grade(score_percentage, assessment.section.courses)

        # Menyimpan hasil score ke model Score
        score = Score.objects.create(
            user=request.user.username,
            course=assessment.section.courses,
            section=assessment.section,
            score=correct_answers,
            total_questions=total_questions,
            grade=grade,
            submitted=True
        )

        # Perbarui progress user
        user_progress, created = CourseProgress.objects.get_or_create(user=request.user, course=assessment.section.courses)
        user_progress.progress = score_percentage
        user_progress.save()

        messages.success(request, "Jawaban Anda telah berhasil disubmit. Terima kasih!")
        # Redirect ke halaman course setelah submit dengan mempertahankan assessment_id
        return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': assessment.section.courses.slug}) + f"?assessment_id={assessment.id}")

    return render(request, 'submit_assessment.html', {'assessment': assessment})

def calculate_overall_pass_fail(user, course):
    
    # Ambil semua asesmen untuk kursus ini
    assessments = Assessment.objects.filter(section__courses=course)
    total_max_score = 0  # Total skor maksimal dari semua asesmen
    total_score = 0  # Total skor yang didapatkan dari pengguna
    all_passed = True  # Untuk melacak apakah semua asesmen lulus

    # Hitung skor untuk setiap asesmen
    for assessment in assessments:
        total_questions = assessment.questions.count()  # Jumlah soal pada asesmen ini
        total_correct_answers = 0  # Jumlah jawaban benar dari pengguna

        for question in assessment.questions.all():
            # Mengambil jawaban yang dipilih oleh pengguna untuk pertanyaan ini
            answers = QuestionAnswer.objects.filter(question=question, user=user)
            
            # Cek apakah jawaban yang dipilih benar
            correct_answers = answers.filter(choice__is_correct=True).count()  # Jawaban benar
            total_correct_answers += correct_answers

        # Tentukan skor berdasarkan jumlah jawaban benar dan jumlah soal
        score_value = 0
        if total_questions > 0:
            # Menghitung skor berdasarkan jawaban benar dan total soal
            score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)

        # Tentukan status kelulusan per asesmen
        passing_threshold = 60  # Ambang batas kelulusan per asesmen (misalnya 60%)
        if (score_value / assessment.weight) * 100 < passing_threshold:
            all_passed = False  # Jika ada asesmen yang tidak lulus, status keseluruhan adalah "Fail"

        total_max_score += assessment.weight  # Bobot maksimal
        total_score += score_value  # Skor yang didapat pengguna

    # Hitung persentase keseluruhan
    if total_max_score > 0:
        overall_percentage = (total_score / total_max_score) * 100
    else:
        overall_percentage = 0

    # Ambil ambang batas kelulusan dari GradeRange
    grade_range = GradeRange.objects.filter(course=course).first()  # Ambil grade range untuk kursus ini

    if grade_range:
        passing_threshold = grade_range.min_grade
    else:
        passing_threshold = 60  # Default jika tidak ada GradeRange

    status = "Pass" if all_passed and overall_percentage >= passing_threshold else "Fail"

    return total_score, overall_percentage, status






def calculate_total_score_and_status(user_id, course):
    # Ambil semua asesmen untuk kursus yang ditentukan
    assessments = Assessment.objects.filter(section__courses=course)
    print(f"Assessments for course {course.course_name}: {assessments.count()}")  # Debugging

    if not assessments.exists():
        return 0, 0, "No assessments available"  # Jika tidak ada asesmen

    total_score = 0
    total_weight = 0
    total_questions = 0  # Menyimpan total pertanyaan

    # Hitung total skor berdasarkan nilai yang diperoleh dari setiap asesmen
    for assessment in assessments:
        # Ambil nilai dari model Score yang relevan
        score_entry = Score.objects.filter(user=user_id, course=course, section=assessment.section).first()
        print(f"Score entry for assessment {assessment.name}: {score_entry}")  # Debugging
        if score_entry:
            total_score += score_entry.score  # Tambahkan skor yang diperoleh
            total_weight += assessment.weight  # Tambahkan bobot asesmen
            total_questions += score_entry.total_questions  # Tambahkan total pertanyaan

    if total_weight == 0 or total_questions == 0:
        return total_score, 0, "No assessments available"  # Jika tidak ada bobot atau pertanyaan

    overall_percentage = (total_score / total_questions) * 100  # Hitung persentase berdasarkan total pertanyaan

    # Ambil rentang nilai untuk kursus ini
    grade_ranges = GradeRange.objects.filter(course=course).order_by('min_grade')

    # Tentukan status kelulusan berdasarkan rentang nilai
    for grade_range in grade_ranges:
        if overall_percentage >= grade_range.min_grade and overall_percentage <= grade_range.max_grade:
            return total_score, overall_percentage, grade_range.name  # Mengembalikan total skor, persentase, dan nama grade

    # Jika tidak ada grade range yang sesuai, default ke "Fail"
    return total_score, overall_percentage, "Fail"

def calculate_grade(overall_percentage, course):
    # Ambil grade ranges untuk course ini
    grade_ranges = GradeRange.objects.filter(course=course).order_by('min_grade')

    # Memeriksa score_percentage dalam rentang grade yang ditemukan
    for grade_range in grade_ranges:
        # Periksa jika overall_percentage berada dalam rentang nilai yang valid
        if overall_percentage >= grade_range.min_grade and overall_percentage <= grade_range.max_grade:
            return grade_range.name  # Mengembalikan nama grade

    # Jika tidak ada grade range yang sesuai, default ke "Fail"
    return 'Fail'  # Default ke Fail jika tidak ada grade range yang sesuai

def start_assessment(request, assessment_id):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Get the assessment using the provided ID
    assessment = get_object_or_404(Assessment, id=assessment_id)

    # Check if the user already has a session for this assessment
    existing_session = AssessmentSession.objects.filter(user=request.user, assessment=assessment).first()

    if not existing_session:
        # If the session doesn't exist, create a new one with start_time set to now
        session = AssessmentSession(
            user=request.user,
            assessment=assessment,
            start_time=timezone.now()  # Set the start time to now
        )
        # Calculate the end time by adding the duration of the assessment to the start time
        session.end_time = session.start_time + timedelta(minutes=assessment.duration_in_minutes)
        session.save()  # Save the session

    # Get the associated course slug and username for redirecting
    username = request.user.username
    slug = assessment.section.courses.slug

    # Redirect back to the course or assessment page after starting
    return redirect(reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': assessment.section.courses.slug}) + f"?assessment_id={assessment.id}")


def course_learn(request, username, slug):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Ambil course berdasarkan slug
    course = get_object_or_404(Course, slug=slug)

    # Pastikan user yang mengakses adalah user yang benar
    if request.user.username != username:
        return redirect('authentication:course_list')

    # Cek apakah user sudah terdaftar di kursus ini
    if not Enrollment.objects.filter(user=request.user, course=course).exists():
        return redirect('courses:course_lms_detail', id=course.id, slug=course.slug)
    
    course_name = course.course_name

    # Ambil section, material, assessment, dan askora
    sections = Section.objects.filter(courses=course).prefetch_related(
        Prefetch('materials', queryset=Material.objects.all()),
        Prefetch('assessments', queryset=Assessment.objects.all().prefetch_related(
            Prefetch('questions', queryset=Question.objects.all().prefetch_related(
                Prefetch('choices', queryset=Choice.objects.all())
            )),
            Prefetch('ask_oras', queryset=AskOra.objects.all())
        ))
    )

    # Buat daftar konten gabungan dengan informasi section
    combined_content = []
    for section in sections:
        for material in section.materials.all():
            combined_content.append(('material', material, section))
        for assessment in section.assessments.all():
            combined_content.append(('assessment', assessment, section))

    total_content = len(combined_content)

    # Ambil ID konten saat ini dari parameter URL
    material_id = request.GET.get('material_id')
    assessment_id = request.GET.get('assessment_id')

    # Tentukan current_content
    current_content = None
    if not material_id and not assessment_id:
        current_content = combined_content[0] if combined_content else None
    elif material_id:
        material = get_object_or_404(Material, id=material_id)
        current_content = ('material', material, next((s for s in sections if material in s.materials.all()), None))
    elif assessment_id:
        assessment = get_object_or_404(Assessment, id=assessment_id)
        current_content = ('assessment', assessment, next((s for s in sections if assessment in s.assessments.all()), None))

    # Debugging untuk memastikan konten terdeteksi dengan benar
    print("Combined Content:", [(c[0], c[1].id, c[2].id) for c in combined_content])
    print("Current Content:", (current_content[0], current_content[1].id, current_content[2].id) if current_content else None)

    # Handle comments and pagination based on current_content
    comments = None
    page_comments = []
    if current_content:
        if current_content[0] == 'material':
            material = current_content[1]
            comments = Comment.objects.filter(material=material, parent=None).order_by('-created_at')
        elif current_content[0] == 'assessment':
            section = current_content[2]
            comments = Comment.objects.filter(material__section=section, parent=None).order_by('-created_at')

        if comments:
            paginator = Paginator(comments, 5)
            page_number = request.GET.get('page')
            page_comments = paginator.get_page(page_number)

    # Cek status assessment
    is_started = False
    is_expired = False
    remaining_time = 0
    if current_content and current_content[0] == 'assessment':
        assessment = current_content[1]
        session = AssessmentSession.objects.filter(user=request.user, assessment=assessment).first()
        if session:
            is_started = True
            remaining_time = int((session.end_time - timezone.now()).total_seconds())
            if remaining_time <= 0:
                is_expired = True
                remaining_time = 0
        else:
            is_started = False

    # Tentukan indeks konten saat ini
    current_index = -1
    if current_content:
        for i, content in enumerate(combined_content):
            if (content[0] == current_content[0] and 
                content[1].id == current_content[1].id and 
                content[2].id == current_content[2].id):
                current_index = i
                break
        if current_index == -1:
            print("Warning: Current content not found in combined_content, defaulting to first content")
            current_index = 0
            current_content = combined_content[0] if combined_content else None

    # Tentukan konten sebelumnya dan berikutnya
    previous_content = combined_content[current_index - 1] if current_index > 0 else None
    next_content = combined_content[current_index + 1] if current_index < len(combined_content) - 1 and current_index != -1 else None
    is_last_content = next_content is None

    # Buat URL untuk navigasi
    previous_url = "#" if not previous_content else f"?{previous_content[0]}_id={previous_content[1].id}"
    next_url = "#" if not next_content else f"?{next_content[0]}_id={next_content[1].id}"

    # Save track records
    if current_content:
        if current_content[0] == 'material':
            material = current_content[1]
            if not MaterialRead.objects.filter(user=request.user, material=material).exists():
                MaterialRead.objects.create(user=request.user, material=material)
        elif current_content[0] == 'assessment':
            assessment = current_content[1]
            if not AssessmentRead.objects.filter(user=request.user, assessment=assessment).exists():
                AssessmentRead.objects.create(user=request.user, assessment=assessment)

    # Lacak kemajuan pengguna
    user_progress, created = CourseProgress.objects.get_or_create(user=request.user, course=course)
    if current_content and (current_index + 1) > user_progress.progress_percentage / 100 * total_content:
        user_progress.progress_percentage = (current_index + 1) / total_content * 100
        user_progress.save()

    # Ambil skor terakhir dari pengguna
    score = Score.objects.filter(user=request.user.username, course=course).order_by('-date').first()
    user_grade = 'Fail'
    if score:
        score_percentage = (score.score / score.total_questions) * 100
        user_grade = calculate_grade(score_percentage, course)

    # Hitung skor assessment dan status
    assessments = Assessment.objects.filter(section__courses=course)
    assessment_scores = []
    total_max_score = 0
    total_score = 0  # Inisialisasi total_score
    all_assessments_submitted = True

    grade_range = GradeRange.objects.filter(course=course).all()
    if grade_range:
        passing_threshold = grade_range.filter(name='Pass').first().min_grade
        max_grade = grade_range.filter(name='Pass').first().max_grade
    else:
        return render(request, 'error_template.html', {'message': 'Grade range not found for this course.'})

    for assessment in assessments:
        score_value = Decimal(0)
        total_correct_answers = 0
        total_questions = assessment.questions.count()
        if total_questions > 0:  # Assessment adalah multiple choice
            answers_exist = False
            for question in assessment.questions.all():
                answers = QuestionAnswer.objects.filter(question=question, user=request.user)
                if answers.exists():
                    answers_exist = True
                total_correct_answers += answers.filter(choice__is_correct=True).count()
            if not answers_exist:
                all_assessments_submitted = False
            if total_questions > 0:
                score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
        else:  # Assessment adalah AskOra
            askora_submissions = Submission.objects.filter(
                askora__assessment=assessment,
                user=request.user
            )
            if not askora_submissions.exists():
                all_assessments_submitted = False
            else:
                latest_submission = askora_submissions.order_by('-submitted_at').first()
                assessment_score = AssessmentScore.objects.filter(submission=latest_submission).first()
                if assessment_score:
                    score_value = Decimal(assessment_score.final_score)

        score_value = min(score_value, Decimal(assessment.weight))
        assessment_scores.append({
            'assessment': assessment,
            'score': score_value,
            'weight': assessment.weight
        })
        total_max_score += assessment.weight
        total_score += score_value  # Tambahkan ke total_score

    total_score = min(total_score, total_max_score)  # Batasi dengan total_max_score
    overall_percentage = (total_score / total_max_score) * 100 if total_max_score > 0 else 0
    passing_criteria_met = overall_percentage >= passing_threshold
    status = "Pass" if all_assessments_submitted and passing_criteria_met else "Fail"

    # Persiapkan assessment_results
    assessment_results = [
        {'name': score['assessment'].name, 'max_score': score['weight'], 'score': score['score']}
        for score in assessment_scores
    ]
    assessment_results.append({'name': 'Total', 'max_score': total_max_score, 'score': total_score})

    # Debugging untuk memastikan skor
    print(f"Total Score: {total_score}, Assessment Results Total: {assessment_results[-1]['score']}")

    # Ambil data AskOra dan Submission
    askoras = AskOra.objects.filter(assessment__section__courses=course)
    try:
        submissions = Submission.objects.filter(
            askora__in=AskOra.objects.filter(assessment__section__courses=course),
            user=request.user
        )
    except Exception as e:
        print(f"Error fetching submissions: {e}")
        submissions = []

    # Ambil pertanyaan dan jawaban untuk assessment
    questions = Question.objects.filter(assessment__in=assessments)
    answered_questions = {q.id: QuestionAnswer.objects.filter(user=request.user, question=q).first() for q in questions}

    # Ambil submissions teman untuk direview
    peer_submissions = Submission.objects.filter(
        askora__in=AskOra.objects.filter(assessment__section__courses=course)
    ).exclude(user=request.user).prefetch_related('peer_reviews')

    peer_submissions_data = []
    for submission in peer_submissions:
        has_reviewed = submission.peer_reviews.filter(reviewer=request.user).exists()
        assessment_score, created = AssessmentScore.objects.get_or_create(submission=submission)
        peer_reviews = submission.peer_reviews.all()
        assessment_weight = float(submission.askora.assessment.weight)
        max_peer_score = 5.0

        # Cek apakah pengguna saat ini telah mengirimkan tugas untuk AskOra yang sama
        user_has_submitted = Submission.objects.filter(
            askora=submission.askora,
            user=request.user
        ).exists()

        if peer_reviews:
            total_score_reviews = sum(float(review.score) * float(review.weight) for review in peer_reviews)
            peer_review_count = peer_reviews.count()
            avg_peer_score = total_score_reviews / peer_review_count
            scaled_peer_score = (avg_peer_score / max_peer_score) * assessment_weight
            participant_score = assessment_weight
            final_score = (participant_score * 0.5) + (scaled_peer_score * 0.5)
        else:
            final_score = assessment_weight * 0.5

        try:
            assessment_score.final_score = final_score
            assessment_score.save()
        except Exception as e:
            print(f"Error saving assessment score: {e}")
            final_score = float(assessment_score.final_score or 0.0)

        peer_submissions_data.append({
            'submission': submission,
            'has_reviewed': has_reviewed,
            'final_score': final_score,
            'can_review': user_has_submitted
        })

    context = {
        'course': course,
        'course_name': course_name,
        'sections': sections,
        'current_content': current_content,
        'previous_url': previous_url,
        'next_url': next_url,
        'course_progress': user_progress.progress_percentage,
        'user_grade': user_grade,
        'assessment_results': assessment_results,
        'total_score': total_score,  # Skor total yang benar (97.00)
        'overall_percentage': overall_percentage,
        'total_weight': total_max_score,
        'status': status,
        'is_started': is_started,
        'is_expired': is_expired,
        'remaining_time': remaining_time,
        'max_grade': max_grade,
        'passing_threshold': passing_threshold,
        'is_last_content': is_last_content,
        'comments': page_comments,
        'material': current_content[1] if current_content and current_content[0] == 'material' else None,
        'assessment': current_content[1] if current_content and current_content[0] == 'assessment' else None,
        'answered_questions': answered_questions,
        'askoras': askoras,
        'submissions': submissions,
        'peer_submissions_data': peer_submissions_data,
    }

    return render(request, 'learner/course_learn.html', context)


def submit_peer_review(request, submission_id):
    submission = get_object_or_404(Submission, id=submission_id)
    if request.method == 'POST':
        if not PeerReview.objects.filter(submission=submission, reviewer=request.user).exists():
            try:
                peer_review = PeerReview(
                    submission=submission,
                    reviewer=request.user,
                    score=int(request.POST.get('score')),
                    comment=request.POST.get('comment'),
                    weight=1.0
                )
                peer_review.save()
                #print(f"Peer review saved for Submission {submission.id} by {request.user.username}")

                # Hitung skor akhir secara manual
                assessment_score, created = AssessmentScore.objects.get_or_create(submission=submission)
                peer_reviews = submission.peer_reviews.all()
                if peer_reviews:
                    total_score = sum(float(review.score) * float(review.weight) for review in peer_reviews)
                    peer_review_count = peer_reviews.count()
                    avg_peer_score = total_score / peer_review_count
                    participant_score = 5.0
                    assessment_score.final_score = (participant_score * 0.5) + (avg_peer_score * 0.5)
                else:
                    assessment_score.final_score = 2.5
                assessment_score.save()
                print(f"Final score updated: {assessment_score.final_score}")
            except Exception as e:
                print(f"Error in peer review process for Submission {submission.id}: {e}")
    
    assessment = submission.askora.assessment
    course_slug = assessment.section.courses.slug
    return redirect(
        reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course_slug}) + 
        f"?assessment_id={assessment.id}"
    )

def submit_answer(request, askora_id):
    askora = get_object_or_404(AskOra, id=askora_id)
    if request.method == 'POST' and askora.is_responsive():
        try:
            submission = Submission(
                askora=askora,
                user=request.user,
                answer_text=request.POST.get('answer_text'),
                answer_file=request.FILES.get('answer_file')
            )
            submission.save()
            print(f"Submission saved for AskOra {askora.id}")
        except Exception as e:
            print(f"Error saving submission: {e}")
    
    # Redirect ke course_learn dengan assessment_id
    assessment = askora.assessment
    course_slug = assessment.section.courses.slug  # Ganti .first() dengan akses langsung
    return redirect(
        reverse('courses:course_learn', kwargs={'username': request.user.username, 'slug': course_slug}) + 
        f"?assessment_id={assessment.id}"
    )


def generate_certificate(request, course_id):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    course = get_object_or_404(Course, id=course_id)

    # Ambil semua asesmen untuk kursus ini
    assessments = Assessment.objects.filter(section__courses=course)
    assessment_scores = []
    total_max_score = 0
    total_score = 0
    all_assessments_submitted = True

    # Ambil GradeRange yang terkait dengan kursus
    grade_range = GradeRange.objects.filter(course=course).all()
    if grade_range:
        passing_threshold = grade_range.filter(name='Pass').first().min_grade
        max_grade = grade_range.filter(name='Pass').first().max_grade
    else:
        return render(request, 'error_template.html', {'message': 'Grade range not found for this course.'})

    for assessment in assessments:
        score_value = Decimal(0)
        # Skor Multiple Choice
        total_correct_answers = 0
        total_questions = assessment.questions.count()
        if total_questions > 0:  # Assessment adalah multiple choice
            answers_exist = False
            for question in assessment.questions.all():
                answers = QuestionAnswer.objects.filter(question=question, user=request.user)
                if answers.exists():
                    answers_exist = True
                total_correct_answers += answers.filter(choice__is_correct=True).count()
            if not answers_exist:
                all_assessments_submitted = False
            if total_questions > 0:
                score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
        else:  # Assessment adalah AskOra (tidak ada questions)
            askora_submissions = Submission.objects.filter(
                askora__assessment=assessment,
                user=request.user
            )
            if not askora_submissions.exists():
                all_assessments_submitted = False
            else:
                latest_submission = askora_submissions.order_by('-submitted_at').first()
                assessment_score = AssessmentScore.objects.filter(submission=latest_submission).first()
                if assessment_score:
                    score_value = Decimal(assessment_score.final_score)

        score_value = min(score_value, Decimal(assessment.weight))
        assessment_scores.append({
            'assessment': assessment,
            'score': score_value,
            'weight': assessment.weight
        })
        total_max_score += assessment.weight
        total_score += score_value

    total_score = min(total_score, total_max_score)
    overall_percentage = (total_score / total_max_score) * 100 if total_max_score > 0 else 0
    passing_criteria_met = overall_percentage >= passing_threshold
    status = "Pass" if all_assessments_submitted and passing_criteria_met else "Fail"

    # Format hasil nilai per asesmen dan totalnya
    assessment_results = [
        {'name': score['assessment'].name, 'max_score': score['weight'], 'score': score['score']}
        for score in assessment_scores
    ]
    assessment_results.append({'name': 'Total', 'max_score': total_max_score, 'score': total_score})

    # Render HTML untuk sertifikat
    html_content = render_to_string('learner/certificate_template.html', {
        'passing_threshold': passing_threshold,
        'status': status,
        'course': course,
        'total_score': total_score,
        'user': request.user,
        'issue_date': timezone.now().strftime('%Y-%m-%d'),
        'assessment_results': assessment_results,
    })

    # Menghasilkan PDF dari HTML yang dirender
    pdf = HTML(string=html_content).write_pdf()
    filename = f"certificate_{course.slug}.pdf"
    response = HttpResponse(pdf, content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    return response




#re-runs course
def course_reruns(request, id):
    """ View for creating a re-run of a course, along with related data like CoursePrice, Assessments, and Materials """

    course = get_object_or_404(Course, id=id)

    # Check if the course status is "archive"
    try:
        archive_status = CourseStatus.objects.get(status='archived')
        draft_status = CourseStatus.objects.get(status='draft')
    except CourseStatus.DoesNotExist:
        # Handle the case where the 'archived' status doesn't exist
        messages.error(request, "The 'archived' status is missing. Please check your data.")
        return redirect('courses:studio', id=course.id)

    # Check if the course status is 'archived'
    if course.status_course != archive_status:
        messages.warning(request, "Only archived courses can be re-run.")
        return redirect('courses:studio', id=course.id)
    # Check if the user has permission to create a re-run for this course
    if not (request.user.is_superuser or request.user == course.org_partner.user or request.user == course.instructor.user):
        messages.error(request, "You do not have permission to create a re-run for this course.")
        return redirect('courses:studio', id=course.id)

    # If the request method is POST, the user is submitting the form to create the re-run
    if request.method == 'POST':
        form = CourseRerunForm(request.POST)

        if form.is_valid():
            today = timezone.now().date()

            # Check if a re-run already exists for today
            existing_rerun = Course.objects.filter(
                course_name=course.course_name,  # Same course name
                course_run__startswith="Run",  # Check if it's a re-run
                created_at__date=today  # Check if it's the same day
            ).exists()

            if existing_rerun:
                messages.error(request, "A re-run for this course has already been created today.")
                return redirect('courses:studio', id=course.id)

            # Process the creation of the new course re-run
            new_course = form.save(commit=False)
            new_course.course_name = form.cleaned_data['course_name_hidden']
            new_course.org_partner = form.cleaned_data['org_partner_hidden']
            new_course.status_course = draft_status
            new_course.slug = f"{slugify(new_course.course_name)}-{new_course.course_run.lower().replace(' ', '-')}"
            new_course.created_at = timezone.now()
            new_course.author = request.user  # Set the user who creates the new course
            
            # Set Instructor and other fields from the original course
            new_course.instructor = course.instructor
            new_course.language = course.language
            new_course.image = course.image
            new_course.description = course.description
            new_course.sort_description = course.sort_description
            new_course.hour = course.hour
            new_course.save()

            # Copy the CoursePrice related to the original course
            for course_price in course.prices.all():
                CoursePrice.objects.create(
                    course=new_course,
                    price_type=course_price.price_type,
                    partner=course_price.partner,
                    partner_price=course_price.partner_price,
                    discount_percent=course_price.discount_percent,
                    discount_amount=course_price.discount_amount,
                    ice_share_rate=course_price.ice_share_rate,
                    admin_fee=course_price.admin_fee,
                    sub_total=course_price.sub_total,
                    portal_price=course_price.portal_price,
                    normal_price=course_price.normal_price,
                    calculate_admin_price=course_price.calculate_admin_price,
                    platform_fee=course_price.platform_fee,
                    voucher=course_price.voucher,
                    user_payment=course_price.user_payment,
                    partner_earning=course_price.partner_earning,
                    ice_earning=course_price.ice_earning
                )

           
            # Copy the Sections and related Materials, Assessments for the new course
            for section in course.sections.all():
                # Create a new section title based on the original section's title and course_run
                new_section_title = f"{section.title}"

                # Check if the new section already exists for this course (avoid duplicates)
                existing_section = Section.objects.filter(
                    title=new_section_title, courses=new_course
                ).first()

                # If section doesn't exist, create a new one
                if not existing_section:
                    # If the original section has a parent, copy it over as well
                    parent_section = None
                    if section.parent:
                        # If the section has a parent, get the new parent section from the new course
                        parent_section = Section.objects.filter(
                            title=f"{section.parent.title}",
                            courses=new_course
                        ).first()

                    # Create the new section
                    new_section = Section.objects.create(
                        parent=parent_section,  # Link to the parent section if it exists
                        title=new_section_title,
                        slug=f"{section.slug}",  # Ensure the slug is unique
                        courses=new_course  # Link the new section to the new course
                    )

                    # Copy the materials associated with the section
                    for material in section.materials.all():
                        Material.objects.create(
                            section=new_section,  # Link the material to the new section
                            title=material.title,
                            description=material.description,
                            created_at=material.created_at  # Copy the creation date, if needed
                        )

                    # Copy the assessments associated with the section
                    for assessment in section.assessments.all():
                        new_assessment = Assessment.objects.create(
                            name=assessment.name,
                            section=new_section,  # Link the assessment to the new section
                            weight=assessment.weight,
                            description=assessment.description,
                            flag=assessment.flag,
                            grade_range=assessment.grade_range,
                            created_at=assessment.created_at  # Copy the creation date, if needed
                        )

                        # Copy the questions associated with the assessment
                        for question in assessment.questions.all():
                            new_question = Question.objects.create(
                                assessment=new_assessment,  # Link the question to the new assessment
                                text=question.text,
                                created_at=question.created_at  # Copy the creation date, if needed
                            )

                            # Copy the choices associated with the question
                            for choice in question.choices.all():
                                Choice.objects.create(
                                    question=new_question,  # Link the choice to the new question
                                    text=choice.text,
                                    is_correct=choice.is_correct  # Copy whether the choice is correct
                                )


            messages.success(request, f"Re-run of course '{new_course.course_name}' created successfully!")
            return redirect('courses:studio', id=new_course.id)

        else:
            messages.error(request, "There was an error with the form. Please correct the errors below.")
            print(form.errors)  # Optional: print form errors for debugging

    else:
        form = CourseRerunForm(instance=course)
        form.fields['course_name_hidden'].initial = course.course_name
        form.fields['org_partner_hidden'].initial = course.org_partner

    return render(request, 'courses/course_reruns.html', {'form': form, 'course': course})

#add course price
def add_course_price(request, id):
    print("🔄 Form submitted!")  # Debugging

    # Pastikan user sudah login
    if not request.user.is_authenticated:
        return redirect(f"/login/?next={request.path}")

    # Inisialisasi variabel course
    course = None

    # Memastikan hanya partner yang bisa menambahkan harga
    if hasattr(request.user, 'is_partner') and request.user.is_partner:
        # Pastikan kursus yang ingin diubah adalah milik partner ini
        course = get_object_or_404(Course, id=id, org_partner__user_id=request.user.id)
        # Periksa apakah partner sudah menambahkan harga atau tidak
        existing_price = CoursePrice.objects.filter(course=course, price_type__name="Beli Langsung").first()
    else:
        # Jika user bukan partner, tampilkan pesan error dan redirect ke halaman yang sesuai
        messages.error(request, "Anda tidak memiliki izin untuk menambahkan harga ke kursus ini.")
        return redirect('courses:studio',id=id)  # Redirect ke halaman studio tanpa perlu mengakses course.id

    # Jika request method POST, berarti user mengirimkan form
    if request.method == 'POST':
        print("✅ POST request received")  # Debugging
        print("📨 Data yang dikirim:", request.POST)  # Debugging, lihat isi form yang dikirim

        # Membuat instance form dengan data dari POST, dan memeriksa harga yang sudah ada jika ada
        form = CoursePriceForm(request.POST, user=request.user, course=course, instance=existing_price)
        
        # Jika form valid, simpan data harga
        if form.is_valid():
            print("✅ Form is valid")  # Debugging
            course_price = form.save(commit=False)
            course_price.course = course

            # Pastikan hanya partner yang menambahkan harga 'Beli Langsung'
            if hasattr(request.user, 'is_partner') and request.user.is_partner:
                try:
                    course_price.price_type = PricingType.objects.get(name="Beli Langsung")
                except PricingType.DoesNotExist:
                    messages.error(request, "Tipe harga 'Beli Langsung' tidak ditemukan! Tambahkan di database.")
                    return redirect(reverse('courses:add_course_price', args=[course.id]))

            # Simpan harga kursus
            course_price.save()
            messages.success(request, "✅ Harga kursus berhasil disimpan!")
            print("✅ Data berhasil disimpan!")  # Debugging
            return redirect(reverse('courses:add_course_price', args=[course.id]))  # Redirect setelah menyimpan

        else:
            print("❌ Form is NOT valid")  # Debugging
            print(form.errors)  # Debugging, lihat kenapa form tidak valid
            for error in form.errors.get("__all__", []):
                messages.error(request, error)
        
    else:
        # Jika form tidak di-submit, tampilkan form kosong atau dengan data yang sudah ada (jika ada)
        form = CoursePriceForm(user=request.user, course=course, instance=existing_price)

    return render(request, 'courses/course_price_form.html', {'form': form, 'course': course})


#instrcutor profile
def instructor_profile(request, username):
    # Fetch the instructor object
    instructor = get_object_or_404(Instructor, user__username=username)

    # Ensure that the instructor has a provider (Partner) with a slug in the related Universiti
    if not instructor.provider or not hasattr(instructor.provider.name, 'slug'):
        partner_slug = None
    else:
        partner_slug = instructor.provider.name.slug  # Access slug from Universiti model

    # Get the search term from the GET request (if any)
    search_term = request.GET.get('search', '')

    # Get the 'published' status from CourseStatus model
    published_status = CourseStatus.objects.get(status='published')  # Assuming 'status' field is used to store 'published'

    # Filter courses based on the search term, published status, and end_date
    courses = instructor.courses.filter(
        Q(course_name__icontains=search_term) &  # Search by course name
        Q(status_course=published_status) &      # Filter by 'published' status (corrected)
        Q(end_date__gte=datetime.now())          # Only courses that haven't ended yet
    ).order_by('start_date')  # Optional: Order by start date or any other field

    # Annotate each course with the total number of enrollments (participants)
    courses = courses.annotate(total_enrollments=Count('enrollments'))

    # Get the count of filtered courses
    courses_count = courses.count()

    # Calculate the total number of unique participants across all courses
    total_participants = courses.aggregate(total_participants=Count('enrollments__user', distinct=True))['total_participants']

    # Implement pagination: Show 6 courses per page
    paginator = Paginator(courses, 6)

    # Get the current page number from GET params (default to 1 if invalid)
    page_number = request.GET.get('page', 1)  # Default to page 1 if not specified

    # Ensure the page number is a positive integer
    try:
        page_number = int(page_number)
        if page_number < 1:
            page_number = 1  # If the page number is less than 1, set it to 1
    except ValueError:
        page_number = 1  # If the page number is not a valid integer, set it to 1

    # Get the page object
    try:
        page_obj = paginator.get_page(page_number)
    except EmptyPage:
        page_obj = paginator.get_page(1)  # If page number is out of range, show first page

    # Pass the instructor, courses, paginated courses, and courses count to the template
    return render(request, 'home/instructor_profile.html', {
        'instructor': instructor,
        'page_obj': page_obj,
        'courses_count': courses_count,  # Pass the count to the template
        'search_term': search_term,
        'partner_slug': partner_slug,  # Pass partner_slug to the template
        'total_participants': total_participants,  # Pass total participants to the template
    })
#ernroll
def enroll_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    response = course.enroll_user(request.user)
     # Check the response and use Django's messages framework to display the message
    if response["status"] == "success":
        messages.success(request, response["message"])  # Display success message
    elif response["status"] == "error":
        messages.error(request, response["message"])  # Display error message
    else:
        messages.info(request, response["message"])  # Display info message
    return redirect('courses:course_lms_detail',id=course.id, slug=course.slug)

def draft_lms(request, id):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)  # Redirect to login if not authenticated

    user = request.user
    course = None

    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=id)
    elif user.is_partner:
        course = get_object_or_404(Course, id=id, org_partner__user_id=user.id)
    elif user.is_instructor:
        course = get_object_or_404(Course, id=id, instructor__user_id=user.id)

    # If no course is found, redirect to the homepage
    if not course:
        return redirect('/')  # Redirect to the homepage if the course is not found

    # If the course is found, render the course page
    return render(request, 'courses/course_draft_view.html', {'course': course})


def course_lms_detail(request, id, slug):
    # Fetch the course by id and slug
    course = get_object_or_404(Course, id=id, slug=slug)
    
    # Get the 'published' CourseStatus
    try:
        published_status = CourseStatus.objects.get(status='published')
    except CourseStatus.DoesNotExist:
        return redirect('/')  # Redirect if the 'published' status doesn't exist
    
    # Check if the course's status is 'published'
    if course.status_course != published_status:
        return redirect('/')  # Redirect to homepage if not published
    
    # Check if the user is enrolled in the course
    if request.user.is_authenticated:
        is_enrolled = course.enrollments.filter(user=request.user).exists()
    else:
        is_enrolled = False

    # Get similar courses based on the category and level (only published courses with future end_date)
    similar_courses = Course.objects.filter(
        category=course.category,
        status_course=published_status,
        end_date__gte=timezone.now()
    ).exclude(id=course.id)[:5]

    # Get all comments for the course, excluding replies (parent is None)
    comments = CourseComment.objects.filter(course=course, parent=None).order_by('-created_at')

    # Get replies for each comment
    for comment in comments:
        comment.replies = CourseComment.objects.filter(parent=comment).order_by('-created_at')
        for reply in comment.replies:
            reply.sub_replies = CourseComment.objects.filter(parent=reply).order_by('-created_at')

    section_data = Section.objects.filter(
            parent=None, courses=course
        ).prefetch_related('materials', 'assessments')  # Add all necessary relationships

    

    # Render the course detail page with the similar courses, enrollment status, sections, materials, and assessments
    return render(request, 'home/course_detail.html', {
        'course': course,
        'is_enrolled': is_enrolled,
        'similar_courses': similar_courses,
        'comments': comments,
        'section_data': section_data,  # Pass sections, materials, and assessments
    })


def course_instructor(request, id):
    # Pastikan user sudah login
    if not request.user.is_authenticated:
        return redirect(f"/login/?next={request.path}")
    
    user = request.user
    course = None

    # Menentukan course berdasarkan role user
    if user.is_superuser:
        course = get_object_or_404(Course, id=id)
    elif user.is_partner:
        course = get_object_or_404(Course, id=id, org_partner__user_id=user.id)
    elif user.is_instructor:
        messages.error(request, "You do not have permission to manage this course.")
        return redirect('/courses')  # Instruktur tidak diizinkan untuk mengelola kursus ini

    # Jika course tidak ditemukan berdasarkan kondisi, redirect ke daftar kursus
    if not course:
        return redirect('/courses')

    # Menangani POST request untuk menambahkan instruktur
    if request.method == 'POST':
        form = CourseInstructorForm(request.POST, instance=course, request=request)
        if form.is_valid():
            form.save()
            messages.success(request, "Instructor has been successfully added to the course.")
            return redirect('courses:course_instructor', id=course.id)
    else:
        # Untuk GET request, menampilkan form yang sudah ada
        form = CourseInstructorForm(instance=course, request=request)

    return render(request, 'instructor/course_instructor.html', {'course': course, 'form': form})


# Fungsi untuk pencarian instruktur menggunakan Select2 (AJAX)
def search_instructors(request):
    query = request.GET.get('q', '')
    page_number = int(request.GET.get('page', 1))
    page_size = 10  # Membatasi jumlah instruktur yang ditampilkan per halaman

    # Filter instruktur berdasarkan pencarian username
    instructors = User.objects.filter(username__icontains=query, is_instructor=True)
    
    # Paginasi instruktur
    paginator = Paginator(instructors, page_size)
    page_obj = paginator.get_page(page_number)

    # Mengembalikan hasil pencarian dalam format JSON untuk Select2
    results = [{'id': instructor.id, 'text': instructor.username} for instructor in page_obj]

    return JsonResponse({
        'results': results, 
        'total_pages': paginator.num_pages,  # Menyediakan total halaman
        'current_page': page_obj.number      # Menyediakan halaman saat ini
    })

#create grade
#@login_required
def course_grade(request, id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    

    user = request.user
    course = None

  
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=id)
    elif user.is_partner:
        #course = Course.objects.filter(id=id, org_partner_id=request.user.id).first()
        course = get_object_or_404(Course, id=id, org_partner__user_id=user.id)
        #print(course)
    elif user.is_instructor:
        course = get_object_or_404(Course, id=id, instructor__user_id=user.id)
    # If no course is found, redirect to the courses list page
        #print(course)
    if not course:
        return redirect('/courses')
    
    course = get_object_or_404(Course, id=id)
     # Retrieve sections related to this course
    sections = Section.objects.filter(courses=course)  # Get all sections related to the course
   # Ensure grade ranges exist; create defaults if necessary
    grade_fail, created_fail = course.grade_ranges.get_or_create(
        name="Fail",
        defaults={"min_grade": 0, "max_grade": 59},
    )
    grade_pass, created_pass = course.grade_ranges.get_or_create(
        name="Pass",
        defaults={"min_grade": 60, "max_grade": 100},
    )

    # Compute widths for display
    total_grade_range = 100
    fail_width = (grade_fail.max_grade / total_grade_range) * 100
    pass_width = 100 - fail_width

    # Compute grade ranges
    fail_range_max = int(grade_fail.max_grade)
    pass_range_min = fail_range_max + 1

     # Retrieve the sections for the course
    sections = Section.objects.filter(courses=course)  # Get all sections related to this course

    # Retrieve all assessments associated with these sections
    assessments = Assessment.objects.filter(section__in=sections)
    total_weight = sum(assessment.weight for assessment in assessments)
    
    return render(request, 'courses/course_grade.html', {
        'course': course,
        'sections': sections,  # Pass the sections
        "fail_width": fail_width,
        "pass_width": pass_width,
        "fail_range_max": fail_range_max,
        "pass_range_min": pass_range_min,
        'assessments': assessments,  # Pass assessments to the template
        'total_weight': total_weight,
    })


#@login_required
def update_grade_range(request, id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    user = request.user
    course = None

     # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=id)
    elif user.is_partner:
        #course = Course.objects.filter(id=id, org_partner_id=request.user.id).first()
        course = get_object_or_404(Course, id=id, org_partner__user_id=user.id)
        #print(course)
    elif user.is_instructor:
        course = get_object_or_404(Course, id=id, instructor__user_id=user.id)
    # If no course is found, redirect to the courses list page
        #print(course)
    if not course:
        # Instructors can delete sections only for their own courses
        if course.instructor.user_id != request.user.id:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})



    if request.method == "POST":
        try:
            # Fetch course
            course = get_object_or_404(Course, id=id)

            # Get Fail and Pass widths from the AJAX request
            fail_width = Decimal(request.POST.get("fail_width", 50))  # Example: 40.0
            pass_width = Decimal(request.POST.get("pass_width", 50))  # Example: 60.0

            # Get Fail and Pass grade ranges
            grade_fail = course.grade_ranges.filter(name="Fail").first()
            grade_pass = course.grade_ranges.filter(name="Pass").first()

            if not grade_fail or not grade_pass:
                return JsonResponse({"success": False, "message": "Fail or Pass grade range not found!"})

            # Dynamically calculate and update ranges
            grade_fail.max_grade = int((fail_width / 100) * 100)  # Fail max_grade = % of total grade
            grade_pass.min_grade = grade_fail.max_grade + 1  # Pass starts right after Fail's max_grade
            grade_pass.max_grade = 100  # Pass always ends at 100

            # Save updates
            grade_fail.save()
            grade_pass.save()

            return JsonResponse({"success": True, "message": "Grade ranges updated dynamically!"})

        except Exception as e:
            return JsonResponse({"success": False, "message": str(e)})
    return JsonResponse({"success": False, "message": "Invalid request"})


#creat assesment type name
#@login_required
@csrf_exempt
def create_assessment(request, idcourse, idsection):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to create assessments for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    if request.method == 'POST':
        form = AssessmentForm(request.POST)
        if form.is_valid():
            # Convert new_weight to Decimal
            new_weight = Decimal(form.cleaned_data['weight'])
            # Calculate total weight for the course
            total_weight = Assessment.objects.filter(section__courses=course).aggregate(Sum('weight'))['weight__sum']
            total_weight = total_weight if total_weight is not None else Decimal('0')

            if total_weight + new_weight > Decimal('100'):
                messages.error(request, "Total bobot untuk penilaian dalam course ini tidak boleh melebihi 100")
                return render(request, 'courses/course_assessement.html', {'form': form, 'course': course, 'section': section})

            # Create the assessment instance but don't save it yet
            assessment = form.save(commit=False)
            # Set the section field
            assessment.section = section
            # Save the assessment
            assessment.save()
            messages.success(request, "Assessment created successfully!")
            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)
    else:
        form = AssessmentForm()

    return render(request, 'courses/course_assessement.html', {'form': form, 'course': course, 'section': section})

#edit assesment type name
#@login_required
@csrf_exempt
def edit_assessment(request, idcourse, idsection, idassessment):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to edit assessments for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Fetch the assessment based on its ID
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)

    if request.method == 'POST':
        form = AssessmentForm(request.POST, instance=assessment)  # Populate the form with current assessment data
        if form.is_valid():
            # Save without committing
            assessment = form.save(commit=False)

            # Check total weight
            total_weight = Assessment.objects.filter(section=section).exclude(id=idassessment).aggregate(Sum('weight'))['weight__sum'] or Decimal('0')
            if total_weight + Decimal(form.cleaned_data['weight']) > Decimal('100'):
                messages.error(request, "Total bobot untuk penilaian dalam section ini tidak boleh melebihi 100")
                return render(request, 'courses/course_assessement_edit.html', {
                    'form': form,
                    'course': course,
                    'section': section,
                    'assessment': assessment,
                })

            # Now save the assessment
            assessment.save()
            messages.warning(request, "Assessment updated successfully!")
            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)

    else:
        # Create an empty form or pre-populated form with existing data
        form = AssessmentForm(instance=assessment)

    return render(request, 'courses/course_assessement_edit.html', {
        'form': form,
        'course': course,
        'section': section,
        'assessment': assessment,
    })

#delete assesment type name
#@login_required
@csrf_exempt
def delete_assessment(request, idcourse, idsection, idassessment):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to delete assessments for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Fetch the assessment
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)

    if request.method == 'POST':
        # Perform the deletion
        assessment.delete()
        messages.success(request, "Assessment deleted successfully!")
        return redirect('courses:studio', id=course.id)

    # Render confirmation page for GET requests
    return render(request, 'courses/confirm_delete_assessment.html', {
        'course': course,
        'section': section,
        'assessment': assessment,
    })


#edit question and choice
#@login_required
@csrf_exempt
def edit_question(request, idcourse, idquestion, idsection, idassessment):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to edit questions for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Ensure the assessment belongs to the section
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)

    # Ensure the question belongs to the assessment
    question = get_object_or_404(Question, id=idquestion, assessment=assessment)

    # Pass the assessment to the forms
    form = QuestionForm(request.POST or None, instance=question, assessment=assessment)
    choice_formset = ChoiceFormSet(request.POST or None, instance=question)

    # Pass assessment to each form in the formset
    for choice_form in choice_formset.forms:
        choice_form.fields['text'].widget = (
            CKEditor5Widget("extends") if assessment.flag else forms.TextInput(attrs={'class': 'form-control'})
        )

    if request.method == 'POST':
        if form.is_valid() and choice_formset.is_valid():
            # Save the question form
            question = form.save(commit=False)
            question.section = section
            question.save()

            # Save the formset
            choice_formset.instance = question
            choice_formset.save()

            messages.success(request, "Question and choices updated successfully!")

            # Check if 'save and add another' button was clicked
            if 'save_and_add_another' in request.POST:
                return redirect('courses:create_question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)

            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)
        else:
            print("Form errors:", form.errors)
            print("Formset errors:", [choice_form.errors for choice_form in choice_formset.forms])
            messages.error(request, "There was an error updating the question. Please check your inputs.")

    return render(request, 'courses/edit_question.html', {
        'form': form,
        'choice_formset': choice_formset,
        'course': course,
        'section': section,
        'assessment': assessment,
    })

#delete question
@csrf_exempt
def delete_question(request, idcourse, idquestion, idsection, idassessment):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to delete questions for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Ensure the assessment belongs to the section
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)

    # Ensure the question belongs to the assessment
    question = get_object_or_404(Question, id=idquestion, assessment=assessment)

    if request.method == 'POST':
        try:
            # Deleting the question
            question.delete()
            messages.success(request, "Question deleted successfully.")
        except Exception as e:
            messages.error(request, f"Error deleting question: {e}")

        # Redirecting back to the page with the list of questions
        return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)

    return render(request, 'courses/view_question.html', {
        'course': course,
        'section': section,
        'assessment': assessment,
    })

#create question and choice
#@login_required
@csrf_exempt
def create_question_view(request, idcourse, idsection, idassessment):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to create questions for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Ensure the assessment belongs to the section
    assessment = get_object_or_404(Assessment, id=idassessment, section=section)

    # Initialize forms
    question_form = QuestionForm(request.POST or None, assessment=assessment)
    choice_formset = ChoiceFormSet(request.POST or None, instance=Question())

    # Pass assessment to each form in the formset
    for choice_form in choice_formset.forms:
        choice_form.fields['text'].widget = (
            CKEditor5Widget("extends") if assessment.flag else forms.TextInput(attrs={'class': 'form-control'})
        )

    if request.method == 'POST':
        if question_form.is_valid() and choice_formset.is_valid():
            # Save question instance
            question = question_form.save(commit=False)
            question.section = section
            question.assessment = assessment
            question.save()

            # Link and save choices
            choice_formset.instance = question
            choice_formset.save()

            messages.success(request, "Question and choices created successfully!")

            # Check if 'save and add another' button was clicked
            if 'save_and_add_another' in request.POST:
                return redirect('courses:create_question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)

            # Redirect to a view or list of questions
            return redirect('courses:view-question', idcourse=course.id, idsection=section.id, idassessment=assessment.id)
        else:
            messages.error(request, "There was an error saving the question. Please correct the errors below.")

    # For GET requests or if forms are invalid
    return render(request, 'courses/create_question.html', {
        'course': course,
        'section': section,
        'assessment': assessment,
        'question_form': question_form,
        'choice_formset': choice_formset,
    })



#view question
#@login_required
@csrf_exempt
def question_view(request, idcourse, idsection, idassessment):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
    else:
        # Unauthorized access
        messages.error(request, "You do not have permission to view questions for this course.")
        return redirect('courses:home')  # Redirect to a safe page

    # Ensure the section belongs to the course
    section = get_object_or_404(Section, id=idsection, courses=course)

    # Ensure the assessment belongs to the section
    assessment = get_object_or_404(
        Assessment.objects.prefetch_related(
            'questions__choices',  # prefetch related choices for multiple-choice questions
            'ask_oras'  # prefetch related ask_oras for open-response questions
        ),
        id=idassessment,
        section=section
    )

    return render(request, 'courses/view_question.html', {
        'course': course,
        'section': section,
        'assessment': assessment,
    })





#upprove user request
#@login_required
def instructor_check(request, instructor_id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Fetch the instructor object
    instructor = get_object_or_404(Instructor, id=instructor_id)
    
    # Check if the user has permission to approve (e.g., the user must be the provider)
    if request.user.is_partner and instructor.provider.user == request.user:
        # Update instructor status to "Approved"
        instructor.status = 'Approved'
        instructor.save()  # Save the status change

        # Now update the user's `is_partner` field to True
        user = instructor.user  # Get the related User object
        
        # Set is_partner to True
        user.is_instructor = True
        user.save()  # Save the user after the update

        # Success message
        messages.success(request, "Instructor has been approved.")
        
    else:
        # Error message if the user doesn't have permission
        messages.error(request, "You do not have permission to approve this instructor.")

    # Redirect to the instructor list or another page after approval
    return redirect('courses:instructor_view')  # Change this URL to your desired location


#instructor detail
#@login_required
def instructor_detail(request, id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    
    # Fetch the instructor object by the provided ID
    instructor = get_object_or_404(Instructor, id=id)

    # Ensure that the instructor has a provider (Partner) with a slug in the related Universiti
    if not instructor.provider or not hasattr(instructor.provider.name, 'slug'):
        # Handle the case where there is no provider or slug
        partner_slug = None
    else:
        partner_slug = instructor.provider.name.slug  # Access slug from Universiti model

    # Get the search term from the GET request (if any)
    search_term = request.GET.get('search', '')

    # Filter courses based on the search term
    courses = instructor.courses.filter(
        Q(course_name__icontains=search_term)  # Search by course name only
    ).order_by('start_date')  # Optional: Order by start date or any other field

    # Get the count of filtered courses
    courses_count = courses.count()

       # Hitung jumlah total siswa yang terdaftar di semua kursus yang diberikan instruktur ini
    total_students = Enrollment.objects.filter(course__in=courses).values('user').annotate(num_students=Count('user')).count()

    # Add a participant count for each course
    # We're using annotate to count the number of enrollments for each course
    courses = courses.annotate(participants_count=Count('enrollments'))

    # Implement pagination: Show 6 courses per page
    paginator = Paginator(courses, 6)

    # Get the current page number from GET params (default to 1 if invalid)
    page_number = request.GET.get('page', 1)  # Default to page 1 if not specified

    # Ensure the page number is a positive integer
    try:
        page_number = int(page_number)
        if page_number < 1:
            page_number = 1  # If the page number is less than 1, set it to 1
    except ValueError:
        page_number = 1  # If the page number is not a valid integer, set it to 1

    # Get the page object
    try:
        page_obj = paginator.get_page(page_number)
    except EmptyPage:
        page_obj = paginator.get_page(1)  # If page number is out of range, show first page

    # Create the context dictionary to pass to the template
    context = {
        'instructor': instructor,
        'page_obj': page_obj,  # Pass the paginated courses to the template
        'courses_count': courses_count,  # Total number of filtered courses
        'search_term': search_term,  # Pass the search query to the template
        'partner_slug': partner_slug,  # Pass the partner slug to the template
        'total_students': total_students,
    }

    # Render the instructor_detail template with the context
    return render(request, 'instructor/instructor_detail.html', context)
#view instructor
#@login_required

def instructor_view(request):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Get search query from GET parameters
    search_query = request.GET.get('q', '').strip()
    
    # Define base queryset based on user role
    if request.user.is_superuser:
        # Admin sees all instructors
        instructors = Instructor.objects.all().annotate(num_courses=Count('courses'))
    elif request.user.is_partner:
        # Partner sees instructors linked to their provider
        instructors = Instructor.objects.filter(provider__user=request.user).annotate(num_courses=Count('courses'))
    elif request.user.is_instructor:
        messages.error(request, "You do not have permission to view this instructor list.")
        return render(request, 'instructor/instructor_list.html', {'instructors': []})
    else:
        messages.error(request, "You do not have permission to view this instructor list.")
        return render(request, 'instructor/instructor_list.html', {'instructors': []})

    # Apply search filter if query exists
    if search_query:
        instructors = instructors.filter(
            Q(user__username__icontains=search_query) | Q(user__email__icontains=search_query)
        )  # Pencarian berdasarkan username atau email dari model User

    # Pagination
    items_per_page = 10  # Jumlah item per halaman
    paginator = Paginator(instructors, items_per_page)
    page_number = request.GET.get('page')

    try:
        instructors_page = paginator.page(page_number)
    except PageNotAnInteger:
        instructors_page = paginator.page(1)
    except EmptyPage:
        instructors_page = paginator.page(paginator.num_pages)

    # Context untuk template
    context = {
        'instructors': instructors_page,
        'search_query': search_query,
        'paginator': paginator,
    }

    return render(request, 'instructor/instructor_list.html', context)

#delete instructor
#@login_required
def delete_instructor(request, instructor_id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
   
    # Fetch the instructor object
    instructor = get_object_or_404(Instructor, id=instructor_id)
    
    # Ensure the user has permission to delete the instructor
    if request.user.is_partner and instructor.provider.user == request.user:
        instructor.delete()
        messages.success(request, "Instructor deleted successfully.")
    else:
        messages.error(request, "You do not have permission to delete this instructor.")

    # Redirect to the list of instructors
    return redirect('courses:instructor_view')


#intructor form for new request
#@login_required
def become_instructor(request):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Check if the user is already an instructor
    try:
        application = Instructor.objects.get(user=request.user)
        if application.status == "Pending":
            
            messages.info(request, "Your application is under review.")
        elif application.status == "Approved":
            messages.success(request, "You are already an instructor!")
        return redirect('authentication:dasbord')
    except Instructor.DoesNotExist:
        if request.method == "POST":
            form = InstructorForm(request.POST)
            if form.is_valid():
                application = form.save(commit=False)
                application.user = request.user
                application.save()
                messages.success(request, "Your application has been submitted!")
                return redirect('authentication:dasbord')
        else:
            form = InstructorForm()

    return render(request, 'home/become_instructor.html', {'form': form})

#add course team
#@login_required

def course_team(request, id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Fetch the course object
    user = request.user

    # Retrieve the course based on the provided ID

    course = get_object_or_404(Course, id=id)


    # Check if the user is either the instructor or an organization partner

    is_instructor = course.instructor is not None and course.instructor.user == user

    is_partner = course.org_partner is not None and course.org_partner.user == user
    is_superuser = user.is_superuser

    if not (is_instructor or is_partner or is_superuser):

        return redirect('/courses')  # Redirect if the user is not authorized


    if request.method == 'POST':

        form = TeamMemberForm(request.POST)

        if form.is_valid():

            email = form.cleaned_data['email']  # Get the email from the form

            try:

                user_instance = User.objects.get(email=email)  # Retrieve the User instance

                team_member = TeamMember(course=course, user=user_instance)

                team_member.save()  # Save the new team member

                return redirect('courses:course_team', id=course.id)

            except User.DoesNotExist:

                form.add_error('email', "No user found with this email.")  # Add an error if user not found

    else:

        form = TeamMemberForm()


    team_members = course.team_members.all()


    return render(request, 'courses/course_team.html', {

        'course': course,

        'form': form,

        'team_members': team_members,

    })
#remove team
#@login_required

def remove_team_member(request, member_id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Check if the user is authorized to access the course
    team_member = get_object_or_404(TeamMember, id=member_id)

    course_id = team_member.course.id


    # Check if the user is the instructor or the organization partner

    is_instructor = getattr(team_member.course.instructor, 'user', None) == request.user

    is_partner = getattr(team_member.course.org_partner, 'user', None) == request.user
    is_superuser = request.user.is_superuser
    
    if is_instructor or is_partner or is_superuser:

        team_member.delete()  # Remove the team member


    return redirect('courses:course_team', id=course_id)  # Redir

#course profile
@csrf_exempt  # Be cautious with this decorator; it's better to avoid using it if unnecessary
def course_profile(request, id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Get the course based on the user's role
    user = request.user
    course = None
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=id)
    elif user.is_partner:
        #course = Course.objects.filter(id=id, org_partner_id=request.user.id).first()
        course = get_object_or_404(Course, id=id, org_partner__user_id=user.id)
        print(course)
    elif user.is_instructor:
        course = get_object_or_404(Course, id=id, instructor__user_id=user.id)
    # If no course is found, redirect to the courses list page
        print(course)
    if not course:
        return redirect('/courses')

    # Handle POST request to update course data
    if request.method == 'POST':
        form = ProfilForm(request.POST,request.FILES, instance=course)
        if form.is_valid():
            form.save()  # Save the updated course data
            
            #print(reverse('course_profile', kwargs={'id': course.id}))
            return redirect('courses:course_profile', id=course.id)  # Redirect back to the updated course profile
    else:
        form = ProfilForm(instance=course)  # For GET requests, display the form with existing course data

    return render(request, 'courses/course_profile.html', {'course': course, 'form': form})




#add section
#@login_required
@csrf_exempt
def create_section(request, idcourse):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Get the course based on the user's role
    if request.method == "POST":
        # Check user permissions
        if request.user.is_superuser:
            course = get_object_or_404(Course, id=idcourse)
        elif request.user.is_partner:
            course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
        elif request.user.is_instructor:
            course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
        else:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})

        form = SectionForm(request.POST)
        if form.is_valid():
            section = form.save(commit=False)
            section.courses = course
            section.save()
            return JsonResponse({'status': 'success', 'message': 'Section created successfully!'})
        else:
            return JsonResponse({'status': 'error', 'message': 'Form is not valid', 'errors': form.errors})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})



# Delete section
#@login_required
@csrf_exempt
def delete_section(request, pk):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Fetch the section
    section = get_object_or_404(Section, pk=pk)
    course = section.courses  # Use the correct relationship field name

    # Check user roles
    if request.user.is_superuser:
        # Superusers can delete any section
        pass
    elif request.user.is_partner:
        # Partners can delete sections only for their associated courses
        if course.org_partner.user_id != request.user.id:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})
    elif request.user.is_instructor:
        # Instructors can delete sections only for their own courses
        if course.instructor.user_id != request.user.id:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})
    else:
        # Unauthorized user
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'})

    # If role check passes, delete the section
    if request.method == 'POST':
        section.delete()
        return JsonResponse({'status': 'success', 'message': 'Section deleted!'})
    else:
        return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})


# Update Section
# Update Section with Role-Based Access
#@login_required
@csrf_exempt
def update_section(request, pk):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Fetch the section
    section = get_object_or_404(Section, pk=pk)
    course = section.courses  # Use the correct relationship field name

    # Check user roles
    if request.user.is_superuser:
        # Superusers can update any section
        pass
    elif request.user.is_partner:
        # Partners can update sections only for their associated courses
        if course.org_partner.user_id != request.user.id:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})
    elif request.user.is_instructor:
        # Instructors can update sections only for their own courses
        if course.instructor.user_id != request.user.id:
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})
    else:
        # Unauthorized user
        return JsonResponse({'status': 'error', 'message': 'Permission denied.'})

    if request.method == "POST":
        # Handle form submission
        form = SectionForm(request.POST, instance=section)
        if form.is_valid():
            # Save the updated section
            form.save()
            return JsonResponse({'status': 'success', 'message': 'Section updated successfully!'})
        else:
            # Return specific form errors for debugging
            return JsonResponse({'status': 'error', 'message': 'Form is not valid', 'errors': form.errors})
    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'})



#add matrial course
#@login_required
@csrf_exempt
def add_matrial(request, idcourse, idsection):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=idcourse)
    elif request.user.is_partner:
        # Ensure the course is associated with the partner
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
    elif request.user.is_instructor:
        # Ensure the course is associated with the instructor
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id,instructor__status='Approved')
    else:
        messages.error(request, "You do not have permission to add materials to this course.")
        return redirect('courses:home')  # Redirect to a safe page for unauthorized users

    # Fetch the section (update the field name to 'courses')
    section = get_object_or_404(Section, id=idsection, courses=course)

    if request.method == 'POST':
        # Handle form submission
        form = MatrialForm(request.POST)  # Include file uploads

        if form.is_valid():
            # Save the material and associate it with the course and section
            material = form.save(commit=False)
            material.section = section
            material.courses = course
            material.save()

            messages.success(request, "Material successfully added to the course.")
            return redirect('courses:studio', id=course.id)
        else:
            # Provide error feedback
            messages.error(request, "Failed to add material. Please check the form for errors.")
            print(form.errors)  # Debugging (optional)

    else:
        # Initialize an empty form for GET requests
        form = MatrialForm()

    # Render the form template
    return render(request, 'courses/course_matrial.html', {
        'form': form,
        'course': course,
        'section': section,
    })


#edit matrial course
#@login_required
@csrf_exempt
def edit_matrial(request, idcourse, idmaterial):
    # Check the role of the user and determine access permissions
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Superuser can access and edit any material
    if request.user.is_superuser:
        # Superuser can access any material, get the associated course via section
        material = get_object_or_404(Material, id=idmaterial)
        course = get_object_or_404(Course, id=idcourse)
    
    # Partner can only access materials related to their course
    elif request.user.is_partner:
        course = get_object_or_404(Course, id=idcourse, org_partner__user_id=request.user.id)
        # Ensure the material belongs to the course's section
        material = get_object_or_404(Material, id=idmaterial, section__courses=course)
    
    # Instructor can only access and edit materials related to their courses
    elif request.user.is_instructor:
        course = get_object_or_404(Course, id=idcourse, instructor__user_id=request.user.id)
        # Ensure the material belongs to the course's section
        material = get_object_or_404(Material, id=idmaterial, section__courses=course)
    
    else:
        # Unauthorized access for users who are not superuser, partner, or instructor
        messages.error(request, "You do not have permission to edit materials in this course.")
        return redirect('courses:home')

    # Handle POST request to update the material
    if request.method == 'POST':
        form = MatrialForm(request.POST, request.FILES, instance=material)
        if form.is_valid():
            form.save()  # Save the updated material
            messages.success(request, "Successfully updated material.")
            return redirect('courses:studio', id=course.id)  # Redirect to the course studio page
        else:
            messages.error(request, "Failed to update material. Please check the form for errors.")
            print(form.errors)  # Debugging (optional)
    else:
        # For GET requests, populate the form with existing material
        form = MatrialForm(instance=material)

    # Render the template with the form and context
    return render(request, 'courses/edit_matrial_course.html', {
        'form': form,
        'course': course,
        'material': material,
    })





#delete matrial course
#@login_required
@csrf_exempt
def delete_matrial(request, pk):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    # Ensure the request is a POST request
    if request.method == 'POST':
        # Fetch the material and its section
        material = get_object_or_404(Material, id=pk)
        section = material.section
        course = section.courses  # Adjust this if the field name is different

        # Check user roles
        if request.user.is_superuser:
            # Superuser can delete any material
            pass
        elif request.user.is_partner:
            # Partner can delete material only for their associated courses
            if not course.org_partner or course.org_partner.user_id != request.user.id:
                return JsonResponse({'status': 'error', 'message': 'Permission denied. You do not own this course.'})
        elif request.user.is_instructor:
            # Instructor can delete material only for their own courses
            if not course.instructor or course.instructor.user_id != request.user.id:
                return JsonResponse({'status': 'error', 'message': 'Permission denied. This is not your course.'})
        else:
            # Unauthorized user
            return JsonResponse({'status': 'error', 'message': 'Permission denied.'})

        # Delete the material if the role check passes
        material.delete()
        return JsonResponse({'status': 'success', 'message': 'Material deleted successfully!'})
    else:
        # Handle invalid request methods
        return JsonResponse({'status': 'error', 'message': 'Invalid request method. Only POST requests are allowed.'})



#course view 
#@login_required




def courseView(request):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    user = request.user
    course_filter = request.GET.get('filter', 'all')  # Get filter from query string

    # Filter courses based on the user's role and selected filter
    if user.is_superuser:
        courses = Course.objects.all()
    elif user.is_partner:
        courses = Course.objects.filter(org_partner__user=user)
    elif user.is_instructor:
        courses = Course.objects.filter(instructor__user=user, instructor__status='Approved')
    else:
        courses = Course.objects.none()

    # Apply the filter for the course status
    if course_filter == 'draft':
        courses = courses.filter(status_course__status='draft')
    elif course_filter == 'published':
        courses = courses.filter(status_course__status='published')
    elif course_filter == 'archive':
        courses = courses.filter(status_course__status='archived')
    elif course_filter == 'curation':
        courses = courses.filter(status_course__status='curation')

    # Get search query if any
    search_query = request.GET.get('search', '').strip()
    if search_query:
        courses = courses.filter(course_name__icontains=search_query)

    # Annotate instructor_email and org_partner_name
    courses = courses.annotate(
        instructor_email=F('instructor__user__email'),
        org_partner_name=F('org_partner__name__name')
    )

    # Correctly annotate the enrolment count based on the relationship (e.g., 'enrollments')
    courses = courses.annotate(
        enrolment_count=Count('enrollments')  # This counts related 'enrollments' (adjust based on your model)
    )

    # Paginate the courses
    paginator = Paginator(courses, 10)  # 10 courses per page
    page_number = request.GET.get('page', 1)
    try:
        page_obj = paginator.page(page_number)
    except PageNotAnInteger:
        page_obj = paginator.page(1)
    except EmptyPage:
        page_obj = paginator.page(paginator.num_pages)

    # Handle DoesNotExist gracefully and fetch CourseStatus
    try:
        draft_status = CourseStatus.objects.get(status='draft')
        published_status = CourseStatus.objects.get(status='published')
        archive_status = CourseStatus.objects.get(status='archived')
        curation_status = CourseStatus.objects.get(status='curation')
    except ObjectDoesNotExist:
        draft_status = published_status = archive_status = curation_status = None
        # Handle the case where CourseStatus entries are missing
        # You could redirect the user or show a message in the template

    # Filter courses based on status_course IDs (only if the CourseStatus objects exist)
    # Ensure these counts are based on the filtered courses, not the whole set.
    draft_count = courses.filter(status_course=draft_status).count() if draft_status else 0
    published_count = courses.filter(status_course=published_status).count() if published_status else 0
    archive_count = courses.filter(status_course=archive_status).count() if archive_status else 0
    curation_count = courses.filter(status_course=curation_status).count() if curation_status else 0

    # If there's a search query, update the counts to reflect only the filtered (search) results
    if search_query:
        draft_count = courses.filter(status_course=draft_status).count() if draft_status else 0
        published_count = courses.filter(status_course=published_status).count() if published_status else 0
        archive_count = courses.filter(status_course=archive_status).count() if archive_status else 0
        curation_count = courses.filter(status_course=curation_status).count() if curation_status else 0

    # Pass the filtered courses count to the template
    return render(request, 'courses/course_view.html', {
        'page_obj': page_obj,
        'course_filter': course_filter,
        'all_count': courses.count(),
        'draft_count': draft_count,
        'published_count': published_count,
        'archive_count': archive_count,
        'curation_count': curation_count
    })






def filter_courses_by_query(request, posts):
    """Filter courses based on search query."""
    query = request.GET.get('q')
    if query is not None and query !='':
        posts = posts.filter(Q(course_name__icontains=query) | Q(status_course__icontains=query)).distinct()
    return posts

def paginate_courses(request, posts):
    """Paginate the course list."""
    paginator = Paginator(posts, 5)
    page_number = request.GET.get('page')
    return paginator.get_page(page_number)


#create course
#@login_required

def course_create_view(request):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    if request.user.is_partner or request.user.is_superuser or request.user.is_instructor:
        if request.method == 'POST':
            form = CourseForm(request.POST, user=request.user)  # Pass the logged-in user to the form

            if form.is_valid():
                course = form.save(commit=False)  # Create a Course instance but don't save to the database yet

                # Set the author to the logged-in user
                course.author = request.user
                
                # If the user is a partner or superuser, set the org_partner
                if request.user.is_superuser or request.user.is_partner:
                    partner = form.cleaned_data['org_partner']  # Get the selected partner from the form
                    course.org_partner = partner  # Set the partner for the course

                # If the user is an instructor, set the instructor
                if request.user.is_instructor:
                    instructor = Instructor.objects.get(user=request.user)  # Assuming a one-to-one relationship
                    course.instructor = instructor

                # Set status_course programmatically (e.g., default to 'draft')
                draft_status = CourseStatus.objects.get(status='draft')  # Assuming 'draft' exists in CourseStatus
                course.status_course = draft_status  # Set the default status

                # Save the course instance to the database
                course.save()

                return redirect('/courses')  # Redirect to a course list page or success page
            else:
                print(form.errors)  # Print form errors to the console for debugging
        else:
            form = CourseForm(user=request.user)  # Pass the logged-in user to the form

    else:
        return redirect('/courses')

    return render(request, 'courses/course_add.html', {'form': form})

#studio detail courses

def studio(request, id):
    # Check if the user is authenticated
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)
    user = request.user
    course = None

  
    # Determine the course based on the user's role
    if request.user.is_superuser:
        course = get_object_or_404(Course, id=id)
    elif user.is_partner:
        #course = Course.objects.filter(id=id, org_partner_id=request.user.id).first()
        course = get_object_or_404(Course, id=id, org_partner__user_id=user.id)
        #print(course)
    elif user.is_instructor:
        course = get_object_or_404(Course, id=id, instructor__user_id=user.id)
    # If no course is found, redirect to the courses list page
        #print(course)
    if not course:
        return redirect('/courses')

    # Fetch sections related to the specific course
    #section = Section.objects.filter(parent=None, courses_id=course.id)
    #section = Section.objects.filter(parent=None, courses=course).prefetch_related('materials')
    #section = Section.objects.filter(parent=None, courses=course).prefetch_related('questions')
    section = Section.objects.filter(
    parent=None, courses=course
).prefetch_related('materials', 'assessments')  # Add all necessary relationships

    # Render the page with the course and sections data
    return render(request, 'courses/course_detail.html', {'course': course, 'section': section})



#update_partner

def convert_image_to_webp(uploaded_image):
    """
    Konversi gambar yang diunggah ke format WebP dan kembalikan ContentFile
    """
    img = Image.open(uploaded_image)

    # Pastikan gambar berada dalam mode RGB
    img = img.convert('RGB')

    # Simpan gambar ke buffer dalam format WebP
    buffer = BytesIO()
    img.save(buffer, format='WEBP', quality=85)  # Adjust kualitas sesuai kebutuhan
    buffer.seek(0)

    # Kembalikan file dalam format ContentFile
    return ContentFile(buffer.read(), name='logo.webp')


def update_partner(request, partner_id):
    # Ambil partner dan pastikan user memiliki otoritas
    partner = get_object_or_404(Partner, pk=partner_id)

    # Cek otoritas user
    if not request.user.is_authenticated or (request.user != partner.user and not request.user.is_superuser):
        return redirect("/login/?next=%s" % request.path)

    old_logo = partner.logo.path if partner.logo else None  # Simpan path logo lama

    if request.method == "POST":
        form = PartnerFormUpdate(request.POST, request.FILES, instance=partner, user=request.user)
        if form.is_valid():
            partner_instance = form.save(commit=False)

            # Jika ada logo baru yang diunggah, konversi ke WebP
            if 'logo' in request.FILES:
                uploaded_logo = request.FILES['logo']
                converted_logo = convert_image_to_webp(uploaded_logo)
                partner_instance.logo = converted_logo

            # Simpan perubahan ke instance Partner
            partner_instance.save()

            # Hapus logo lama jika ada dan sudah diganti
            if old_logo and old_logo != partner.logo.path:
                if os.path.exists(old_logo):
                    os.remove(old_logo)

            return redirect('courses:partner_detail', partner_id=partner.id)
    else:
        form = PartnerFormUpdate(instance=partner, user=request.user)

    return render(request, 'partner/update_partner.html', {'form': form, 'partner': partner})
#partner view
#@cache_page(60 * 5)

def partnerView(request):
    if not request.user.is_authenticated:
        return redirect("/login/?next=%s" % request.path)

    # Get the search query from the GET request
    query = request.GET.get('q', '')

    # Superusers see all partners, others see only their own
    posts = Partner.objects.all() if request.user.is_superuser else Partner.objects.filter(user_id=request.user.id)

    # Apply the search filter if the query is provided
    if query:
        posts = posts.filter(
            Q(name__name__icontains=query) |  # Filter by the 'name' field inside the related Univer model
            Q(user__email__icontains=query) |  # Filter by email of the related User model
            Q(phone__icontains=query)  # Filter by phone number
        )

    # Pagination: Ensure to paginate before fetching data
    paginator = Paginator(posts, 10)  # Show 10 posts per page
    page_number = request.GET.get('page')
    page = paginator.get_page(page_number)

    # Context to send to template
    context = {
        'count': posts.count(),  # Total number of partners
        'page': page,  # Current page object for pagination
        'query': query  # Pass the query to the template for display in search input
    }

    return render(request, 'partner/partner_view.html', context)


#detail_partner
def partner_detail(request, partner_id):
    # Retrieve the partner using the provided partner_id
    partner = get_object_or_404(Partner, id=partner_id)

    # Get the search query and category filter from the request
    search_query = request.GET.get('search', '')
    selected_category = request.GET.get('category', '')
    sort_by = request.GET.get('sort_by', 'name')

    # Filter courses related to the partner
    related_courses = Course.objects.filter(org_partner_id=partner.id)

    # Apply search filter if provided
    if search_query:
        related_courses = related_courses.filter(course_name__icontains=search_query)

    # Apply category filter if provided
    if selected_category:
        related_courses = related_courses.filter(category__name=selected_category)

    # Annotate each course with the number of enrollments (learners)
    related_courses = related_courses.annotate(learner_count=Count('enrollments'))

    # Sort the courses based on the sort_by value
    if sort_by == 'name':
        related_courses = related_courses.order_by('course_name')
    elif sort_by == 'date':
        related_courses = related_courses.order_by('created_at')
    elif sort_by == 'learners':
        related_courses = related_courses.order_by('-learner_count')
    elif sort_by == 'status':
        related_courses = related_courses.order_by('status_course')

    # Count the total number of related courses
    total_courses = related_courses.count()

    # Group courses by category (if category field exists)
    grouped_courses = {}
    for course in related_courses:
        category_name = course.category.name if course.category else 'Uncategorized'
        if category_name not in grouped_courses:
            grouped_courses[category_name] = []
        grouped_courses[category_name].append(course)

    # Fetch categories that have courses linked to this partner
    categories_with_courses = Category.objects.filter(category_courses__org_partner_id=partner.id).distinct()

    # --- Calculate unique learners across all courses ---
    # Count unique users who are enrolled in any of the courses of this partner
    unique_learners = Enrollment.objects.filter(course__in=related_courses).values('user').distinct().count()

    # Pagination setup
    page_number = request.GET.get('page')
    paginator = Paginator(related_courses, 10)
    page_obj = paginator.get_page(page_number)

    # Context data, including learner_count for each course and unique learner count
    context = {
        'partner': partner,
        'page_obj': page_obj,
        'total_courses': total_courses,
        'search_query': search_query,
        'grouped_courses': grouped_courses,
        'selected_category': selected_category,
        'categories': categories_with_courses,  # Only categories with courses
        'sort_by': sort_by,
        'unique_learners': unique_learners  # Add unique learners to the context
    }

    return render(request, 'partner/partner_detail.html', context)


#org partner from lms
def org_partner(request, slug):
    partner = get_object_or_404(Partner, name__slug=slug)
    search_query = request.GET.get('search', '')
    selected_category = request.GET.get('category', '')
    sort_by = request.GET.get('sort_by', 'name')

    try:
        published_status = CourseStatus.objects.get(status='published')
    except CourseStatus.DoesNotExist:
        published_status = None

    if published_status:
        # Optimalkan dengan select_related untuk mengambil relasi category
        related_courses = Course.objects.filter(
            org_partner_id=partner.id,
            status_course=published_status,
            end_date__gte=datetime.now()
        ).select_related('category')  # Optimalkan dengan select_related

        # Filter pencarian
        if search_query:
            related_courses = related_courses.filter(course_name__icontains=search_query)

        # Filter berdasarkan kategori
        if selected_category:
            related_courses = related_courses.filter(category__name=selected_category)

        # Sorting berdasarkan parameter
        if sort_by == 'learners':
            related_courses = related_courses.annotate(total_enrollments=Count('enrollments')).order_by('-total_enrollments')
        elif sort_by == 'date':
            related_courses = related_courses.order_by('created_at')
        else:
            related_courses = related_courses.order_by('course_name')

        # Hanya ambil data yang diperlukan
        related_courses = related_courses.annotate(total_enrollments=Count('enrollments'))

    else:
        related_courses = Course.objects.none()

    # Pagination
    page_number = request.GET.get('page')
    paginator = Paginator(related_courses, 10)  # 10 per halaman
    page_obj = paginator.get_page(page_number)

    # Hitung total peserta unik
    unique_learners = related_courses.aggregate(
        unique_users=Count('enrollments__user', distinct=True)
    )['unique_users']

    context = {
        'partner': partner,
        'page_obj': page_obj,
        'total_courses': related_courses.count(),
        'unique_learners': unique_learners,
        'search_query': search_query,
        'selected_category': selected_category,
        'categories': Category.objects.all(),
        'sort_by': sort_by,
    }

    return render(request, 'partner/org_partner.html', context)

# search user optimized with index and pagination
def search_users(request):
    query = request.GET.get('q', '')
    
    if query:
        users = User.objects.filter(
            Q(email__icontains=query) & Q(is_active=True)
        ).only('id', 'email')  # Ensure only necessary fields are fetched
    else:
        users = User.objects.filter(is_active=True).only('id', 'email')

    # Apply pagination
    paginator = Paginator(users, 20)  # Show 20 users per page
    page_number = request.GET.get('page')  # Get the page number from the query params
    page_obj = paginator.get_page(page_number)
    
    # Prepare data for response
    users_data = [{'id': user.id, 'text': user.email} for user in page_obj]
    
    return JsonResponse({
        'users': users_data,
        'page': page_obj.number,
        'total_pages': paginator.num_pages,
        'total_users': paginator.count,
    })

# search partner optimized with pagination
def search_partner(request):
    query = request.GET.get('q', '')
    
    if query:
        partners = Universiti.objects.filter(
            Q(name__icontains=query) | Q(email__icontains=query)
        ).only('id', 'name', 'email')
    else:
        partners = Universiti.objects.filter(Q(name__icontains=query)).only('id', 'name')

    paginator = Paginator(partners, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    partners_data = [{'id': universiti.id, 'text': universiti.name} for universiti in page_obj]

    return JsonResponse({
        'partners': partners_data,
        'page': page_obj.number,
        'total_pages': paginator.num_pages,
        'total_partners': paginator.count,
    })





def partner_create_view(request):
    if not request.user.is_superuser:
     return redirect('/')

    if request.method == 'POST':
        form = PartnerForm(request.POST)  # Pass the logged-in user to the form
        if form.is_valid():
            form = form.save(commit=False)
            form.author_id = request.user.id
            form.save()  # Save the course with the selected partner
                  # Now update the user's `is_partner` field to True
            user = form.user  # Get the related User object

            # Set is_partner to True
            user.is_partner = True
            user.save()  # Save the user after the update
            return redirect('/partner')  # Redirect to a course list page or success page
    else:
        form = PartnerForm()  # Pass the logged-in user to the form
    #print(request.POST)
    return render(request, 'partner/partner_add.html', {'form': form})


#contoh ajax
def course_create(request):
    data = dict()
    
    # Check if it's a POST request
    if request.method == 'POST':
        form = CourseForm(request.POST)
        
        if form.is_valid():
            # Save the new course if the form is valid
            form.save()
            data['form_is_valid'] = True
            
            # Fetch the updated course list after adding a new course
            courses = Course.objects.all()  # Corrected from Course.all() to Course.objects.all()
            data['course_list'] = render_to_string('courses/course_list.html', {'courses': courses})
        else:
            # Form is not valid, send this info back
            data['form_is_valid'] = False
    else:
        # For GET request, create an empty form
        form = CourseForm()
    
    # Render the course creation form
    context = {'form': form}
    data['html_form'] = render_to_string('courses/course_create.html', context, request=request)
    
    return JsonResponse(data)

# Delete Book
def course_delete(request, pk):
    courses = get_object_or_404(Course, pk=pk)
    data = dict()
    if request.method == 'POST':
        courses.delete()
        data['form_is_valid'] = True
        books = Course.objects.all()
        data['course_list'] = render_to_string('courses/course_list.html', {'courses': courses})
    return JsonResponse(data)

# View to fetch the list of books (for initial load)
@cache_page(60 * 15)
def course_list(request):
    courses = Course.objects.all()[:100]
    return render(request, 'courses/course_list.html', {'courses': courses})

