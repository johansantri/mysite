
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
from courses.models import Course,Instructor, Enrollment,Section,GradeRange,CourseStatusHistory,QuestionAnswer, CourseProgress, PeerReview,MaterialRead, AssessmentRead, AssessmentScore,Material,Assessment, Submission, CustomUser, Instructor
from authentication.models import CustomUser, Universiti
from django.http import HttpResponse
import csv
from django.db.models import Avg, Prefetch



def learner_detail(request, username):
    """
    Menampilkan nama, foto, daftar kursus yang lulus, informasi instructor, dan detail pengguna untuk akses publik
    """
    # Dapatkan learner berdasarkan username
    learner = get_object_or_404(CustomUser, username=username)

    # Ambil semua enrollment untuk learner
    enrollments = Enrollment.objects.filter(user=learner).select_related('course').prefetch_related(
        Prefetch('course__sections__materials', queryset=Material.objects.all()),
        Prefetch('course__sections__assessments', queryset=Assessment.objects.all())
    )

    # Ambil instructor jika ada
    instructor = Instructor.objects.filter(user=learner).first()

    # Siapkan data kursus yang lulus
    completed_courses_data = []
    for enrollment in enrollments:
        course = enrollment.course

        # Hitung progress berdasarkan material dan asesmen
        materials = Material.objects.filter(section__courses=course)
        total_materials = materials.count()
        materials_read = MaterialRead.objects.filter(user=learner, material__in=materials).count()
        materials_read_percentage = (materials_read / total_materials * 100) if total_materials > 0 else 0

        assessments = Assessment.objects.filter(section__courses=course)
        total_assessments = assessments.count()
        assessments_completed = AssessmentRead.objects.filter(user=learner, assessment__in=assessments).count()
        assessments_completed_percentage = (assessments_completed / total_assessments * 100) if total_assessments > 0 else 0

        progress = (materials_read_percentage + assessments_completed_percentage) / 2 if (total_materials + total_assessments) > 0 else 0

        # Update CourseProgress
        course_progress, created = CourseProgress.objects.get_or_create(user=learner, course=course)
        course_progress.progress_percentage = progress
        course_progress.save()

        # Ambil grade range untuk menentukan passing threshold
        grade_range = GradeRange.objects.filter(course=course).first()
        passing_threshold = grade_range.min_grade if grade_range else 0

        # Hitung skor total
        total_score = Decimal(0)
        total_max_score = Decimal(0)
        for assessment in assessments:
            score_value = Decimal(0)
            total_correct_answers = 0
            total_questions = assessment.questions.count()
            if total_questions > 0:  # Multiple choice
                for question in assessment.questions.all():
                    answers = QuestionAnswer.objects.filter(question=question, user=learner)
                    total_correct_answers += answers.filter(choice__is_correct=True).count()
                score_value = (Decimal(total_correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight) if total_questions > 0 else 0
            else:  # AskOra
                askora_submissions = Submission.objects.filter(askora__assessment=assessment, user=learner)
                if askora_submissions.exists():
                    latest_submission = askora_submissions.order_by('-submitted_at').first()
                    assessment_score = AssessmentScore.objects.filter(submission=latest_submission).first()
                    if assessment_score:
                        score_value = Decimal(assessment_score.final_score)
            total_score += score_value
            total_max_score += assessment.weight

        overall_percentage = (total_score / total_max_score) * 100 if total_max_score > 0 else 0

        # Tentukan apakah kursus lulus
        is_completed = progress == 100 and overall_percentage >= passing_threshold

        if is_completed:
            completed_courses_data.append({
                'enrollment': enrollment,
                'progress': progress,
                'overall_percentage': overall_percentage,
            })

    # Data untuk template
    context = {
        'learner': learner,
        'completed_courses': completed_courses_data,
        'instructor': instructor,
    }
    return render(request, 'learner/learner.html', context)