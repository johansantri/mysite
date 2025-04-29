
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
    Menampilkan profil learner secara publik, termasuk kursus yang diselesaikan (lulus),
    informasi instructor jika ada, dan progres belajar.
    """
    learner = get_object_or_404(CustomUser, username=username)

    # Ambil semua enrollment dan prefetch relasi yang diperlukan
    enrollments = Enrollment.objects.filter(user=learner).select_related('course')

    # Jika learner juga instructor, ambil profil instructor-nya
    instructor = Instructor.objects.filter(user=learner).first()

    completed_courses_data = []

    for enrollment in enrollments:
        course = enrollment.course

        # Hitung progress materi
        materials = Material.objects.filter(section__courses=course).distinct()
        total_materials = materials.count()
        materials_read = MaterialRead.objects.filter(user=learner, material__in=materials).count()
        materials_read_percentage = (materials_read / total_materials * 100) if total_materials > 0 else 0

        # Hitung progress assessment
        assessments = Assessment.objects.filter(section__courses=course).distinct()
        total_assessments = assessments.count()
        assessments_completed = AssessmentRead.objects.filter(user=learner, assessment__in=assessments).count()
        assessments_completed_percentage = (assessments_completed / total_assessments * 100) if total_assessments > 0 else 0

        # Gabungkan progress keseluruhan
        progress = (materials_read_percentage + assessments_completed_percentage) / 2 if (total_materials + total_assessments) > 0 else 0

        # Simpan atau update ke model CourseProgress
        course_progress, _ = CourseProgress.objects.get_or_create(user=learner, course=course)
        course_progress.progress_percentage = progress
        course_progress.save()

        # Ambil ambang batas kelulusan
        grade_range = GradeRange.objects.filter(course=course, name='Pass').first()
        passing_threshold = grade_range.min_grade if grade_range else Decimal('52.00')

        # Hitung nilai akhir
        total_score = Decimal('0')
        total_max_score = Decimal('0')

        for assessment in assessments:
            score_value = Decimal('0')
            total_questions = assessment.questions.count()

            if total_questions > 0:
                correct_answers = QuestionAnswer.objects.filter(
                    user=learner, question__assessment=assessment, choice__is_correct=True
                ).count()
                score_value = (Decimal(correct_answers) / Decimal(total_questions)) * assessment.weight
            else:
                submission = Submission.objects.filter(askora__assessment=assessment, user=learner).order_by('-submitted_at').first()
                if submission:
                    assessment_score = AssessmentScore.objects.filter(submission=submission).first()
                    if assessment_score:
                        score_value = assessment_score.final_score

            total_score += min(score_value, assessment.weight)
            total_max_score += assessment.weight

        overall_percentage = (total_score / total_max_score * 100) if total_max_score > 0 else 0

        # Penentu apakah kursus dianggap selesai/lulus
        is_completed = progress == 100 and overall_percentage >= passing_threshold

        if is_completed:
            completed_courses_data.append({
                'enrollment': enrollment,
                'progress': progress,
                'overall_percentage': overall_percentage,
                'threshold': passing_threshold,
                'total_score': total_score,
            })

    context = {
        'learner': learner,
        'completed_courses': completed_courses_data,
        'instructor': instructor,
    }

    return render(request, 'learner/learner.html', context)
