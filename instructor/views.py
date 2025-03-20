from django.shortcuts import render, redirect
from django.shortcuts import render, redirect,get_object_or_404
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.core.paginator import Paginator
from django.db.models import Prefetch
import csv
from decimal import Decimal
from django.contrib import messages
from courses.models import Course, Enrollment,Section,GradeRange,QuestionAnswer, CourseProgress, PeerReview,MaterialRead, AssessmentRead, AssessmentScore,Material,Assessment, Submission, CustomUser, Instructor
from authentication.models import CustomUser, Universiti
# Create your views here.

# View untuk Instructor mengajukan kurasi
@login_required
def instructor_submit_curation(request, course_id):
    course = get_object_or_404(Course, id=course_id)
    
    # Pastikan pengguna adalah Instructor dan ditugaskan ke kursus ini
    if not request.user.is_instructor or course.instructor.user != request.user:
        raise PermissionDenied("You do not have permission to submit this course for curation.")

    if request.method == "POST":
        # Pastikan status saat ini adalah 'draft'
        if course.status_course.status != 'draft':
            messages.error(request, "Course can only be submitted for curation from 'Draft' status.")
            return redirect('instructor_course_detail', course_id=course.id)

        # Ubah status ke 'curation'
        course.change_status('curation', request.user, message="Submitted for curation by Instructor.")
        messages.success(request, "Course has been submitted for curation.")
        return redirect('instructor_course_detail', course_id=course.id)

    return render(request, 'instructor/submit_curation.html', {'course': course})

# View untuk Partner meninjau kurasi
@login_required
def partner_review_curation(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    # Pastikan pengguna adalah Partner dan memiliki hak atas kursus ini
    if not request.user.is_partner or course.org_partner.user != request.user:
        raise PermissionDenied("You do not have permission to review this course.")

    if request.method == "POST":
        # Pastikan status saat ini adalah 'curation'
        if course.status_course.status != 'curation':
            messages.error(request, "Course can only be reviewed in 'Curation' status.")
            return redirect('studios', course_id=course.id)

        action = request.POST.get('action')
        message = request.POST.get('message')

        if not message:
            messages.error(request, "Please provide a message for your review.")
            return redirect('partner_review_curation', course_id=course.id)

        if action == 'accept':
            # Partner menerima, tetap di 'curation', ajukan ke Superuser
            course.change_status('curation', request.user, message=f"Accepted by Partner: {message}")
            messages.success(request, "Course has been accepted and submitted for Superuser review.")
        elif action == 'reject':
            # Partner menolak, kembali ke 'draft'
            course.change_status('draft', request.user, message=f"Rejected by Partner: {message}")
            messages.success(request, "Course has been rejected and returned to Instructor for revisions.")
        else:
            messages.error(request, "Invalid action.")
            return redirect('partner_review_curation', course_id=course.id)

        return redirect('partner_course_detail', course_id=course.id)

    return render(request, 'partner/review_curation.html', {
        'course': course,
        'history': course.status_history.all()
    })

# View untuk Superuser meninjau dan mempublikasikan
@login_required
def superuser_publish_course(request, course_id):
    course = get_object_or_404(Course, id=course_id)

    # Pastikan pengguna adalah Superuser
    if not request.user.is_superuser:
        raise PermissionDenied("You do not have permission to publish this course.")

    if request.method == "POST":
        # Pastikan status saat ini adalah 'curation'
        if course.status_course.status != 'curation':
            messages.error(request, "Course can only be published from 'Curation' status.")
            return redirect('studios', course_id=course.id)

        action = request.POST.get('action')
        message = request.POST.get('message')

        if not message:
            messages.error(request, "Please provide a message for your review.")
            return redirect('superuser_publish_course', course_id=course.id)

        if action == 'publish':
            # Superuser menerima, ubah status ke 'published'
            course.change_status('published', request.user, message=f"Published by Superuser: {message}")
            messages.success(request, "Course has been published to the catalog.")
        elif action == 'reject':
            # Superuser menolak, kembali ke 'curation' untuk Partner
            course.change_status('curation', request.user, message=f"Rejected by Superuser: {message}")
            messages.success(request, "Course has been rejected and returned to Partner for revisions.")
        else:
            messages.error(request, "Invalid action.")
            return redirect('superuser_publish_course', course_id=course.id)

        return redirect('superuser_course_detail', course_id=course.id)

    return render(request, 'partner/publish_course.html', {
        'course': course,
        'history': course.status_history.all()
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