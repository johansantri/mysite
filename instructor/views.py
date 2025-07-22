from django.shortcuts import render, redirect
from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Prefetch
import csv
from django.core.mail import send_mail
from decimal import Decimal
from django.contrib import messages
from courses.models import InstructorCertificate,Course,CoursePrice, Enrollment,Section,GradeRange,CourseStatusHistory,QuestionAnswer, CourseProgress, PeerReview,MaterialRead, AssessmentRead, AssessmentScore,Material,Assessment, Submission, CustomUser, Instructor
from authentication.models import CustomUser, Universiti
# Create your views here.
from django.template.loader import render_to_string
from weasyprint import HTML
from django.core.files.base import ContentFile

def download_instructor_certificate(request, course_id):
    cert = get_object_or_404(InstructorCertificate, course_id=course_id)

    # Render HTML dan generate PDF
    html_string = render_to_string('instructor/instructor_template.html', {'cert': cert})
    pdf_file = HTML(string=html_string, base_url=request.build_absolute_uri()).write_pdf()

    # Simpan ke field `certificate_file`
    filename = f"instructor_certificate_{cert.id}.pdf"
    cert.certificate_file.save(filename, ContentFile(pdf_file), save=True)

    # Kembalikan response PDF
    response = HttpResponse(pdf_file, content_type='application/pdf')
    response['Content-Disposition'] = f'filename="{filename}"'
    return response


# View untuk Instructor mengajukan kurasi
@login_required
def instructor_submit_curation(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    
    # Pastikan pengguna adalah Instructor dan ditugaskan ke kursus ini
    if not request.user.is_instructor or course.instructor.user != request.user:
        raise PermissionDenied("You do not have permission to submit this course for curation.")

    # Ambil materi dan assessment terkait kursus
    materials = Material.objects.filter(section__courses=course)
    assessments = Assessment.objects.filter(section__courses=course)

    # Tentukan apakah Instructor boleh mengajukan
    can_submit = False
    message = None

    if course.status_course.status == 'draft':
        # Status draft: Instructor boleh mengajukan (baru pertama kali atau setelah penolakan)
        can_submit = True
    elif course.status_course.status in ['curation', 'published', 'archived']:
        # Status curation, published, atau archived: Instructor tidak boleh mengajukan
        if course.status_course.status == 'curation':
            message = "This course has already been submitted for curation and is under review."
        elif course.status_course.status == 'published':
            message = "This course has already been published and cannot be resubmitted."
        elif course.status_course.status == 'archived':
            message = "This course has been archived and cannot be resubmitted."
    else:
        message = "Invalid course status."

    # Ambil riwayat penolakan terakhir (status 'draft')
    latest_rejection = course.status_history.filter(status='draft').last()

    # Jika Instructor boleh mengajukan dan request adalah POST
    if can_submit and request.method == "POST":
        # Validasi: Pastikan ada materi dan assessment
        if not materials.exists() or not assessments.exists():
            messages.error(request, "Course must have materials and assessments before submitting for curation.")
            return redirect('courses:studio', id=course.id)

        message = request.POST.get('message')
        if not message:
            messages.error(request, "Please provide a message for your submission.")
            return redirect('courses:studio', id=course.id)

        # Ubah status ke 'curation'
        course.change_status('curation', request.user, message=message)
        messages.success(request, "Course has been submitted for curation.")
        return redirect('courses:studio', id=course.id)

    # Render template dengan informasi apakah form boleh ditampilkan
    return render(request, 'instructor/submit_curation.html', {
        'course': course,
        'can_submit': can_submit,
        'message': message,
        'history': course.status_history.all(),
        'latest_rejection': latest_rejection,  # Tambahkan riwayat penolakan terakhir ke konteks
    })


# View untuk Partner meninjau kurasi

@login_required
def partner_review_curation(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    # Pastikan pengguna adalah Partner dan memiliki hak atas kursus ini
    if not request.user.is_partner or course.org_partner.user != request.user:
        raise PermissionDenied("You do not have permission to review this course.")

    # Tentukan apakah Partner boleh mengajukan ke curation
    can_submit_to_curation = course.status_course.status == 'curation'

    if request.method == "POST":
        action = request.POST.get('action')
        message = request.POST.get('message')

        if not message:
            messages.error(request, "Please provide a message for your review.")
            return redirect('instructor:partner_review_curation', course_id=course.id)

        if action == 'accept':
            # Hanya izinkan mengajukan ke curation jika status saat ini adalah 'curation'
            if not can_submit_to_curation:
                messages.error(request, "Course cannot be submitted for curation from its current status.")
                return redirect('instructor:partner_review_curation', course_id=course.id)
            course.change_status('curation', request.user, message=message)
            messages.success(request, "Course has been accepted and submitted for Superuser review.")

        elif action == 'reject':
            # Partner boleh menolak ke 'draft', kecuali jika status adalah 'archived'
            if course.status_course.status == 'archived':
                messages.error(request, "Cannot reject an archived course. Please contact the Superuser to unarchive it first.")
                return redirect('instructor:partner_review_curation', course_id=course.id)
            course.change_status('draft', request.user, message=message)
            messages.success(request, "Course has been rejected and returned to Instructor for revisions.")
            # Kirim email notifikasi ke Instructor
            instructor_email = course.instructor.user.email if course.instructor else None
            if instructor_email:
                send_mail(
                    subject=f"Course Rejected: {course.course_name}",
                    message=f"Your course '{course.course_name}' has been rejected by the Partner.\nReason: {message}\nPlease revise and resubmit.",
                    from_email='noreply@yourdomain.com',
                    recipient_list=[instructor_email],
                    fail_silently=True,
                )
            # Kirim email notifikasi ke Superuser
            superusers = CustomUser.objects.filter(is_superuser=True)
            superuser_emails = [superuser.email for superuser in superusers if superuser.email]
            if superuser_emails:
                send_mail(
                    subject=f"Course Rejected to Draft by Partner: {course.course_name}",
                    message=f"The course '{course.course_name}' has been rejected by Partner and returned to Draft status.\nReason: {message}",
                    from_email='noreply@yourdomain.com',
                    recipient_list=superuser_emails,
                    fail_silently=True,
                )

        else:
            messages.error(request, "Invalid action.")
            return redirect('instructor:partner_review_curation', course_id=course.id)

        return redirect('courses:studio', id=course.id)

    return render(request, 'partner/review_curation.html', {
        'course': course,
        'history': course.status_history.all(),
        'can_submit_to_curation': can_submit_to_curation,
    })

# View untuk Superuser meninjau dan mempublikasikan
@login_required
def superuser_publish_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    # Pastikan pengguna adalah Superuser
    if not request.user.is_superuser:
        raise PermissionDenied("You do not have permission to publish this course.")

    # Ambil harga kursus terbaru
    course_price = CoursePrice.objects.filter(course=course, price_type__isnull=False).order_by('-id').first()
    price_info = {
        'price_type_description': (
            course_price.price_type.description if course_price and course_price.price_type and course_price.price_type.description
            else course_price.price_type.name if course_price and course_price.price_type
            else 'Not set'
        ),
        'partner_price': course_price.partner_price if course_price else 0,
        'discount_percent': course_price.discount_percent if course_price else 0,
    }

    # Siapkan data payment_model
    payment_model_choices = dict(Course.PAYMENT_MODEL_CHOICES)

    if request.method == "POST":
        action = request.POST.get('action')

        # Handle update payment_model
        if action == 'update_payment_model':
            new_payment_model = request.POST.get('payment_model')
            if new_payment_model in [choice[0] for choice in Course.PAYMENT_MODEL_CHOICES]:
                course.payment_model = new_payment_model
                course.save()
                messages.success(request, f"Payment model updated to '{payment_model_choices[new_payment_model]}'.")
            else:
                messages.error(request, "Invalid payment model selected.")
            return redirect('instructor:superuser_publish_course', course_id=course.id)

        # Handle existing actions
        message = request.POST.get('message')
        if action in ['superuser_reject', 'superuser_archive', 'superuser_reject_to_draft'] and not message:
            messages.error(request, "Please provide a message for your action.")
            return redirect('instructor:superuser_publish_course', course_id=course.id)

        if action == 'superuser_publish':
            if course.status_course.status != 'curation':
                messages.error(request, "Course can only be published from 'Curation' status.")
                return redirect('instructor:superuser_publish_course', course_id=course.id)
            if not course_price:
                messages.error(request, "Cannot publish course without a set price.")
                return redirect('instructor:superuser_publish_course', course_id=course.id)
            course.change_status('published', request.user, message=message or "Published by Superuser.")
            messages.success(request, "Course has been published to the catalog.")

        elif action == 'superuser_reject':
            if course.status_course.status != 'curation':
                messages.error(request, "Course can only be rejected to Partner from 'Curation' status.")
                return redirect('instructor:superuser_publish_course', course_id=course.id)
            course.change_status('curation', request.user, message=message)
            messages.success(request, "Course has been rejected and returned to Partner for revisions.")

        elif action == 'superuser_archive':
            if course.status_course.status == 'archived':
                messages.error(request, "Course is already archived.")
                return redirect('instructor:superuser_publish_course', course_id=course.id)
            course.change_status('archived', request.user, message=message)
            messages.success(request, "Course has been archived.")
            instructor_email = course.instructor.user.email if course.instructor else None
            partner_email = course.org_partner.user.email if course.org_partner else None
            recipient_list = [email for email in [instructor_email, partner_email] if email]
            if recipient_list:
                email_message = (
                    f"The course '{course.course_name}' has been archived by Superuser.\n"
                    f"Price Type: {price_info['price_type_description']}\n"
                    f"Partner Price: {price_info['partner_price']}\n"
                    f"Discount: {price_info['discount_percent']}%\n"
                    f"Reason: {message}"
                )
                send_mail(
                    subject=f"Course Archived: {course.course_name}",
                    message=email_message,
                    from_email='noreply@yourdomain.com',
                    recipient_list=recipient_list,
                    fail_silently=True,
                )

        elif action == 'superuser_reject_to_draft':
            if course.status_course.status == 'draft':
                messages.error(request, "Course is already in 'Draft' status.")
                return redirect('instructor:superuser_publish_course', course_id=course.id)
            course.change_status('draft', request.user, message=message)
            messages.success(request, "Course has been rejected and returned to Instructor as Draft.")
            instructor_email = course.instructor.user.email if course.instructor else None
            partner_email = course.org_partner.user.email if course.org_partner else None
            recipient_list = [email for email in [instructor_email, partner_email] if email]
            if recipient_list:
                email_message = (
                    f"The course '{course.course_name}' has been rejected by Superuser and returned to Draft status.\n"
                    f"Price Type: {price_info['price_type_description']}\n"
                    f"Partner Price: {price_info['partner_price']}\n"
                    f"Discount: {price_info['discount_percent']}%\n"
                    f"Reason: {message}"
                )
                send_mail(
                    subject=f"Course Rejected to Draft: {course.course_name}",
                    message=email_message,
                    from_email='noreply@yourdomain.com',
                    recipient_list=recipient_list,
                    fail_silently=True,
                )

        else:
            messages.error(request, "Invalid action.")
            return redirect('instructor:superuser_publish_course', course_id=course.id)

        return redirect('courses:studio', id=course.id)

    return render(request, 'partner/publish_course.html', {
        'course': course,
        'history': course.status_history.all(),
        'price_info': price_info,
        'payment_model_choices': Course.PAYMENT_MODEL_CHOICES,
        'current_payment_model': course.payment_model,
    })


@login_required
def studios(request, id):
       # Ambil kursus berdasarkan id
    course = get_object_or_404(Course.objects.select_related('status_course', 'org_partner', 'instructor', 'author', 'author__university'), id=id)

    # Ambil riwayat status kursus
    status_history = course.status_history.all()

    # Ambil materi dan assessment terkait kursus
    sections = Section.objects.filter(courses=course).prefetch_related('materials', 'assessments')
    materials = Material.objects.filter(section__courses=course)
    assessments = Assessment.objects.filter(section__courses=course)

    # Tentukan peran pengguna
    user = request.user
    is_instructor = user.is_instructor and course.instructor and course.instructor.user == user
    is_partner = user.is_partner and course.org_partner.user == user
    is_superuser = user.is_superuser

    # Logika untuk proses kurasi
    if request.method == "POST":
        action = request.POST.get('action')
        message = request.POST.get('message')

        # Instructor: Mengajukan kurasi (draft -> curation)
        if action == 'submit_curation' and is_instructor:
            if course.status_course.status != 'draft':
                messages.error(request, "Course can only be submitted for curation from 'Draft' status.")
            elif not materials.exists() or not assessments.exists():
                messages.error(request, "Course must have materials and assessments before submitting for curation.")
            elif not message:
                messages.error(request, "Please provide a message for your submission.")
            else:
                course.change_status('curation', user, message=message)
                messages.success(request, "Course has been submitted for curation.")
            return redirect('courses:studio', id=course.id)

        # Partner: Meninjau kurasi (accept -> curation, reject -> draft)
        elif action in ['partner_accept', 'partner_reject'] and is_partner:
            if course.status_course.status != 'curation':
                messages.error(request, "Course can only be reviewed in 'Curation' status.")
            elif not message:
                messages.error(request, "Please provide a message for your review.")
            else:
                if action == 'partner_accept':
                    course.change_status('curation', user, message=message)
                    messages.success(request, "Course has been accepted and submitted for Superuser review.")
                elif action == 'partner_reject':
                    course.change_status('draft', user, message=message)
                    messages.success(request, "Course has been rejected and returned to Instructor for revisions.")
            return redirect('courses:studio', id=course.id)

        # Superuser: Mempublikasikan atau menolak (publish -> published, reject -> curation)
        elif action in ['superuser_publish', 'superuser_reject'] and is_superuser:
            if course.status_course.status != 'curation':
                messages.error(request, "Course can only be published from 'Curation' status.")
            elif action == 'superuser_reject' and not message:
                messages.error(request, "Please provide a message for your rejection.")
            else:
                if action == 'superuser_publish':
                    course.change_status('published', user, message=message or "Published by Superuser.")
                    messages.success(request, "Course has been published to the catalog.")
                elif action == 'superuser_reject':
                    course.change_status('curation', user, message=message)
                    messages.success(request, "Course has been rejected and returned to Partner for revisions.")
            return redirect('courses:studio', id=course.id)

    # Siapkan konteks untuk template
    context = {
        'course': course,
        'status_history': status_history,
        'materials': materials,
        'assessments': assessments,
        'is_instructor': is_instructor,
        'is_partner': is_partner,
        'is_superuser': is_superuser,
        # Informasi author untuk laporan
        'author_full_name': course.author.username,
        'author_email': course.author.email,
        'author_university': course.author.university.name if course.author.university else 'N/A',
        'author_gender': course.author.gender or 'N/A',
    }

    return render(request, 'instructor/studio.html', context)

@login_required
def instructor_learning_report(request):
    if not request.user.is_instructor:
        raise PermissionDenied("You do not have permission to access this report.")

    try:
        instructor = Instructor.objects.get(user=request.user)
    except Instructor.DoesNotExist:
        raise PermissionDenied("Instructor profile not found.")

    course_id = request.GET.get('course_id')
    learner_id = request.GET.get('learner_id')
    courses = Course.objects.filter(instructor=instructor).select_related('instructor')

    all_learners = CustomUser.objects.filter(
        id__in=Enrollment.objects.filter(course__instructor=instructor).values_list('user_id', flat=True)
    ).select_related('university').distinct()

    if learner_id:
        courses = courses.filter(enrollments__user_id=learner_id)
    if course_id:
        courses = courses.filter(id=course_id)

    report_data = []

    grade_ranges = GradeRange.objects.filter(course__in=courses).all()
    grade_range_dict = {gr.course_id: gr for gr in grade_ranges if gr.name == 'Pass'}

    for course in courses:
        enrollments = Enrollment.objects.filter(course=course).select_related('user', 'user__university')
        if learner_id:
            enrollments = enrollments.filter(user_id=learner_id)

        sections = Section.objects.filter(courses=course).prefetch_related(
            Prefetch('materials', queryset=Material.objects.all()),
            Prefetch('assessments', queryset=Assessment.objects.all())
        )

        combined_content = []
        for section in sections:
            for material in section.materials.all():
                combined_content.append(('material', material, section))
            for assessment in section.assessments.all():
                combined_content.append(('assessment', assessment, section))
        total_content = len(combined_content)

        passing_threshold = grade_range_dict.get(course.id, None)
        passing_threshold = passing_threshold.min_grade if passing_threshold else Decimal('52.00')

        learner_ids = [enrollment.user_id for enrollment in enrollments]
        material_reads = MaterialRead.objects.filter(user__id__in=learner_ids, material__section__courses=course).select_related('material', 'user').order_by('read_at')
        assessment_reads = AssessmentRead.objects.filter(user__id__in=learner_ids, assessment__section__courses=course).select_related('assessment', 'user').order_by('completed_at')
        question_answers = QuestionAnswer.objects.filter(user__id__in=learner_ids, question__assessment__section__courses=course).select_related('question', 'user').order_by('answered_at')

        activities_by_learner = {learner_id: [] for learner_id in learner_ids}
        for mr in material_reads:
            activities_by_learner[mr.user_id].append(('material', mr.material.title, mr.read_at))
        for ar in assessment_reads:
            activities_by_learner[ar.user_id].append(('assessment', ar.assessment.name, ar.completed_at))
        for qa in question_answers:
            activities_by_learner[qa.user_id].append(('question', qa.question.text, qa.answered_at))

        for learner_id in activities_by_learner:
            activities_by_learner[learner_id].sort(key=lambda x: x[2])

        for enrollment in enrollments:
            learner = enrollment.user

            user_progress, created = CourseProgress.objects.get_or_create(user=learner, course=course)
            progress_percentage = user_progress.progress_percentage

            materials = Material.objects.filter(section__courses=course)
            total_materials = materials.count()
            materials_read = [mr for mr in material_reads if mr.user_id == learner.id]
            materials_read_percentage = (len(materials_read) / total_materials * 100) if total_materials > 0 else 0

            material_access_details = []
            learner_activities = activities_by_learner.get(learner.id, [])
            for i, activity in enumerate(learner_activities):
                if activity[0] == 'material':
                    material_name = activity[1]
                    access_time = activity[2]
                    if i + 1 < len(learner_activities):
                        next_activity_time = learner_activities[i + 1][2]
                        duration = (next_activity_time - access_time).total_seconds() / 60
                    else:
                        duration = None
                    material_access_details.append({
                        'material_name': material_name,
                        'access_time': access_time,
                        'duration': duration,
                    })

            assessments = Assessment.objects.filter(section__courses=course)
            total_assessments = assessments.count()
            assessments_completed = len([ar for ar in assessment_reads if ar.user_id == learner.id])
            assessments_completed_percentage = (assessments_completed / total_assessments * 100) if total_assessments > 0 else 0

            assessment_scores = []
            total_max_score = Decimal('0')
            total_score = Decimal('0')
            all_assessments_submitted = True

            for assessment in assessments:
                score_value = Decimal('0')
                total_correct_answers = 0
                total_questions = assessment.questions.count()

                if total_questions > 0:
                    answers_exist = False
                    for question in assessment.questions.all():
                        answers = [qa for qa in question_answers if qa.user_id == learner.id and qa.question_id == question.id]
                        if answers:
                            answers_exist = True
                        total_correct_answers += sum(1 for qa in answers if qa.choice.is_correct)
                    if not answers_exist:
                        all_assessments_submitted = False
                    if total_questions > 0:
                        score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
                else:
                    askora_submissions = Submission.objects.filter(
                        askora__assessment=assessment,
                        user=learner
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
                    'name': assessment.name,
                    'weight': assessment.weight,
                    'score': score_value,
                })
                total_max_score += Decimal(assessment.weight)
                total_score += score_value

            total_score = min(total_score, total_max_score)
            overall_percentage = (total_score / total_max_score * 100) if total_max_score > 0 else 0
            passing_criteria_met = overall_percentage >= passing_threshold
            status = "Pass" if all_assessments_submitted and passing_criteria_met else "Fail"

            assessment_scores.append({
                'name': 'Total',
                'weight': total_max_score,
                'score': total_score,
            })

            last_login = learner.last_login

            report_data.append({
                'learner': learner,
                'learner_full_name': learner.username,  # Gunakan username sebagai nama
                'learner_email': learner.email,
                'learner_university': learner.university.name if learner.university else 'N/A',
                'learner_gender': learner.gender or 'N/A',
                'course': course,
                'progress_percentage': progress_percentage,
                'materials_read': len(materials_read),
                'total_materials': total_materials,
                'materials_read_percentage': materials_read_percentage,
                'material_access_details': material_access_details,
                'assessments_completed': assessments_completed,
                'total_assessments': total_assessments,
                'assessments_completed_percentage': assessments_completed_percentage,
                'total_score': total_score,
                'threshold': passing_threshold,
                'assessment_details': assessment_scores,
                'status': status,
                'last_login': last_login,
            })

    paginator = Paginator(report_data, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    if 'export' in request.GET:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="instructor_learning_report.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Learner Name', 'Email', 'University', 'Gender',
            'Course', 'Progress (%)', 'Materials Read', 'Materials Read (%)',
            'Assessments Completed', 'Assessments Completed (%)', 'Total Score', 'Threshold', 'Status',
            'Last Login', 'Material Name', 'Access Time', 'Duration (Minutes)', 'Assessment Name', 'Weight', 'Score'
        ])

        for data in report_data:
            for material in data['material_access_details']:
                writer.writerow([
                    data['learner_full_name'], data['learner_email'], data['learner_university'], data['learner_gender'],
                    data['course'].course_name,
                    data['progress_percentage'],
                    f"{data['materials_read']}/{data['total_materials']}",
                    data['materials_read_percentage'],
                    f"{data['assessments_completed']}/{data['total_assessments']}",
                    data['assessments_completed_percentage'],
                    data['total_score'],
                    data['threshold'],
                    data['status'],
                    data['last_login'],
                    material['material_name'],
                    material['access_time'],
                    material['duration'] if material['duration'] is not None else 'N/A',
                    '', '', ''
                ])
            for assessment in data['assessment_details']:
                writer.writerow([
                    data['learner_full_name'], data['learner_email'], data['learner_university'], data['learner_gender'],
                    data['course'].course_name,
                    data['progress_percentage'],
                    f"{data['materials_read']}/{data['total_materials']}",
                    data['materials_read_percentage'],
                    f"{data['assessments_completed']}/{data['total_assessments']}",
                    data['assessments_completed_percentage'],
                    data['total_score'],
                    data['threshold'],
                    data['status'],
                    data['last_login'],
                    '', '', '',
                    assessment['name'],
                    assessment['weight'],
                    assessment['score'],
                ])

        return response

    context = {
        'report_data': page_obj,
        'instructor': instructor,
        'courses': courses,
        'all_learners': all_learners,
        'selected_course': course_id,
        'selected_learner': learner_id,
        'page_obj': page_obj,
    }

    return render(request, 'instructor/learning_report.html', context)

@login_required
def instructor_learner_detail_report(request):
    if not request.user.is_instructor:
        raise PermissionDenied("You do not have permission to access this report.")

    try:
        instructor = Instructor.objects.get(user=request.user)
    except Instructor.DoesNotExist:
        raise PermissionDenied("Instructor profile not found.")

    learner_id = request.GET.get('learner_id')
    if not learner_id:
        return redirect('instructor_learning_report')

    # Ambil data peserta dengan informasi universitas menggunakan select_related
    learner = get_object_or_404(CustomUser.objects.select_related('university'), id=learner_id)
    courses = Course.objects.filter(instructor=instructor, enrollments__user=learner).select_related('instructor')

    report_data = []

    grade_ranges = GradeRange.objects.filter(course__in=courses).all()
    grade_range_dict = {gr.course_id: gr for gr in grade_ranges if gr.name == 'Pass'}

    for course in courses:
        sections = Section.objects.filter(courses=course).prefetch_related(
            Prefetch('materials', queryset=Material.objects.all()),
            Prefetch('assessments', queryset=Assessment.objects.all())
        )

        combined_content = []
        for section in sections:
            for material in section.materials.all():
                combined_content.append(('material', material, section))
            for assessment in section.assessments.all():
                combined_content.append(('assessment', assessment, section))
        total_content = len(combined_content)

        passing_threshold = grade_range_dict.get(course.id, None)
        passing_threshold = passing_threshold.min_grade if passing_threshold else Decimal('52.00')

        material_reads = MaterialRead.objects.filter(user=learner, material__section__courses=course).select_related('material').order_by('read_at')
        assessment_reads = AssessmentRead.objects.filter(user=learner, assessment__section__courses=course).select_related('assessment').order_by('completed_at')
        question_answers = QuestionAnswer.objects.filter(user=learner, question__assessment__section__courses=course).select_related('question').order_by('answered_at')

        learner_activities = []
        for mr in material_reads:
            learner_activities.append(('material', mr.material.title, mr.read_at))
        for ar in assessment_reads:
            learner_activities.append(('assessment', ar.assessment.name, ar.completed_at))
        for qa in question_answers:
            learner_activities.append(('question', qa.question.text, qa.answered_at))
        learner_activities.sort(key=lambda x: x[2])

        user_progress, created = CourseProgress.objects.get_or_create(user=learner, course=course)
        progress_percentage = user_progress.progress_percentage

        materials = Material.objects.filter(section__courses=course)
        total_materials = materials.count()
        materials_read_percentage = (len(material_reads) / total_materials * 100) if total_materials > 0 else 0

        material_access_details = []
        for i, activity in enumerate(learner_activities):
            if activity[0] == 'material':
                material_name = activity[1]
                access_time = activity[2]
                if i + 1 < len(learner_activities):
                    next_activity_time = learner_activities[i + 1][2]
                    duration = (next_activity_time - access_time).total_seconds() / 60
                else:
                    duration = None
                material_access_details.append({
                    'material_name': material_name,
                    'access_time': access_time,
                    'duration': duration,
                })

        assessments = Assessment.objects.filter(section__courses=course)
        total_assessments = assessments.count()
        assessments_completed = len(assessment_reads)
        assessments_completed_percentage = (assessments_completed / total_assessments * 100) if total_assessments > 0 else 0

        assessment_scores = []
        askora_submissions_details = []
        total_max_score = Decimal('0')
        total_score = Decimal('0')
        all_assessments_submitted = True

        for assessment in assessments:
            score_value = Decimal('0')
            total_questions = assessment.questions.count()

            if total_questions > 0:
                answers_exist = False
                total_correct_answers = 0
                for question in assessment.questions.all():
                    answers = [qa for qa in question_answers if qa.question_id == question.id]
                    if answers:
                        answers_exist = True
                    total_correct_answers += sum(1 for qa in answers if qa.choice.is_correct)
                if not answers_exist:
                    all_assessments_submitted = False
                if total_questions > 0:
                    score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
            else:
                askora_submissions = Submission.objects.filter(
                    askora__assessment=assessment,
                    user=learner
                ).select_related('askora').prefetch_related(
                    Prefetch('peer_reviews', queryset=PeerReview.objects.select_related('reviewer'))
                )
                if not askora_submissions.exists():
                    all_assessments_submitted = False
                else:
                    latest_submission = askora_submissions.order_by('-submitted_at').first()
                    assessment_score = AssessmentScore.objects.filter(submission=latest_submission).first()
                    if assessment_score:
                        score_value = Decimal(assessment_score.final_score)

                    peer_reviews = latest_submission.peer_reviews.all()
                    peer_reviews_data = [
                        {
                            'reviewer': pr.reviewer.username,
                            'score': pr.score,
                            'weight': pr.weight,
                            'comment': pr.comment,
                            'reviewed_at': pr.reviewed_at
                        }
                        for pr in peer_reviews
                    ]
                    askora_submissions_details.append({
                        'assessment_name': assessment.name,
                        'submission': latest_submission.content,
                        'submitted_at': latest_submission.submitted_at,
                        'final_score': assessment_score.final_score if assessment_score else None,
                        'peer_reviews': peer_reviews_data,
                    })

            score_value = min(score_value, Decimal(assessment.weight))
            assessment_scores.append({
                'name': assessment.name,
                'weight': assessment.weight,
                'score': score_value,
            })
            total_max_score += Decimal(assessment.weight)
            total_score += score_value

        total_score = min(total_score, total_max_score)
        overall_percentage = (total_score / total_max_score * 100) if total_max_score > 0 else 0
        passing_criteria_met = overall_percentage >= passing_threshold
        status = "Pass" if all_assessments_submitted and passing_criteria_met else "Fail"

        assessment_scores.append({
            'name': 'Total',
            'weight': total_max_score,
            'score': total_score,
        })

        report_data.append({
            'course': course,
            'progress_percentage': progress_percentage,
            'materials_read': len(material_reads),
            'total_materials': total_materials,
            'materials_read_percentage': materials_read_percentage,
            'material_access_details': material_access_details,
            'assessments_completed': assessments_completed,
            'total_assessments': total_assessments,
            'assessments_completed_percentage': assessments_completed_percentage,
            'total_score': total_score,
            'threshold': passing_threshold,
            'assessment_details': assessment_scores,
            'askora_submissions_details': askora_submissions_details,
            'status': status,
        })

    if 'export' in request.GET:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="learner_detail_report_{learner.username}.csv"'

        writer = csv.writer(response)
        writer.writerow([
            'Learner Name', 'Email', 'University', 'Gender',
            'Course', 'Progress (%)', 'Materials Read', 'Materials Read (%)',
            'Assessments Completed', 'Assessments Completed (%)', 'Total Score', 'Threshold', 'Status',
            'Material Name', 'Access Time', 'Duration (Minutes)', 'Assessment Name', 'Weight', 'Score',
            'AskOra Assessment', 'Submission Content', 'Submitted At', 'Final Score', 'Peer Reviewer', 'Peer Score', 'Peer Comment'
        ])

        for data in report_data:
            for material in data['material_access_details']:
                writer.writerow([
                    learner.username, learner.email, learner.university.name if learner.university else 'N/A', learner.gender or 'N/A',
                    data['course'].course_name,
                    data['progress_percentage'],
                    f"{data['materials_read']}/{data['total_materials']}",
                    data['materials_read_percentage'],
                    f"{data['assessments_completed']}/{data['total_assessments']}",
                    data['assessments_completed_percentage'],
                    data['total_score'],
                    data['threshold'],
                    data['status'],
                    material['material_name'],
                    material['access_time'],
                    material['duration'] if material['duration'] is not None else 'N/A',
                    '', '', '', '', '', '', ''
                ])
            for assessment in data['assessment_details']:
                writer.writerow([
                    learner.username, learner.email, learner.university.name if learner.university else 'N/A', learner.gender or 'N/A',
                    data['course'].course_name,
                    data['progress_percentage'],
                    f"{data['materials_read']}/{data['total_materials']}",
                    data['materials_read_percentage'],
                    f"{data['assessments_completed']}/{data['total_assessments']}",
                    data['assessments_completed_percentage'],
                    data['total_score'],
                    data['threshold'],
                    data['status'],
                    '', '', '',
                    assessment['name'],
                    assessment['weight'],
                    assessment['score'],
                    '', '', '', ''
                ])
            for askora in data['askora_submissions_details']:
                for peer_review in askora['peer_reviews']:
                    writer.writerow([
                        learner.username, learner.email, learner.university.name if learner.university else 'N/A', learner.gender or 'N/A',
                        data['course'].course_name,
                        data['progress_percentage'],
                        f"{data['materials_read']}/{data['total_materials']}",
                        data['materials_read_percentage'],
                        f"{data['assessments_completed']}/{data['total_assessments']}",
                        data['assessments_completed_percentage'],
                        data['total_score'],
                        data['threshold'],
                        data['status'],
                        '', '', '',
                        '', '', '',
                        askora['assessment_name'],
                        askora['submission'],
                        askora['submitted_at'],
                        askora['final_score'],
                        peer_review['reviewer'],
                        peer_review['score'],
                        peer_review['comment']
                    ])

        return response

    context = {
        'learner': learner,
        'report_data': report_data,
        'instructor': instructor,
        'last_login': learner.last_login,
        'learner_full_name': learner.username,  # Gunakan username sebagai nama
        'learner_email': learner.email,
        'learner_university': learner.university.name if learner.university else 'N/A',
        'learner_gender': learner.gender or 'N/A',  # Tidak menggunakan get_gender_display karena gen menggunakan nilai yang sama
    }

    return render(request, 'instructor/learner_detail_report.html', context)