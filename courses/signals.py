from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import CourseProgress, Score, UserMicroProgress, GradeRange,Material,MaterialRead,Assessment,AssessmentRead
from decimal import Decimal
import logging
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Score)
def update_course_progress_with_score(sender, instance, created, **kwargs):
    """
    Update CourseProgress dan UserMicroProgress dengan nilai dari Score.
    """
    if not created:
        logger.debug(f"Skipping progress update for non-new Score instance {instance.id}")
        return

    user = instance.user
    course = instance.course
    score = instance.score
    total_questions = instance.total_questions

    # Validasi bahwa user adalah objek User
    if not isinstance(user, User):
        logger.error(f"Invalid user type in Score instance {instance.id}: {type(user)}, value: {user}")
        return

    try:
        # Dapatkan atau buat CourseProgress
        course_progress, created = CourseProgress.objects.get_or_create(
            user=user,
            course=course,
            defaults={'progress_percentage': 0}
        )

        # Hitung progres materi
        materials = Material.objects.filter(section__courses=course)
        total_materials = materials.count()
        materials_read = MaterialRead.objects.filter(user=user, material__in=materials).count()
        materials_read_percentage = (Decimal(materials_read) / Decimal(total_materials) * Decimal('100')) if total_materials > 0 else Decimal('0')

        # Hitung progres asesmen
        assessments = Assessment.objects.filter(section__courses=course)
        total_assessments = assessments.count()
        assessments_completed = AssessmentRead.objects.filter(user=user, assessment__in=assessments).count()
        assessments_completed_percentage = (Decimal(assessments_completed) / Decimal(total_assessments) * Decimal('100')) if total_assessments > 0 else Decimal('0')

        # Gabungkan progres keseluruhan
        overall_progress = ((materials_read_percentage + assessments_completed_percentage) / Decimal('2')) if (total_materials + total_assessments) > 0 else Decimal('0')

        # Simpan progres ke CourseProgress
        course_progress.progress_percentage = float(overall_progress)
        course_progress.save()
        logger.info(f"Updated CourseProgress for user {user.username}, course {course.id}, progress {overall_progress}%")

        # Perbarui UserMicroProgress
        user_micro_progress, _ = UserMicroProgress.objects.get_or_create(
            user=user,
            course=course,
            defaults={'progress_percentage': 0, 'score': 0}
        )
        user_micro_progress.progress_percentage = float(overall_progress)
        user_micro_progress.score = score
        user_micro_progress.save()
        logger.info(f"Updated UserMicroProgress for user {user.username}, course {course.id}, score {score}")

        # Ambil ambang batas kelulusan
        grade_range = GradeRange.objects.filter(course=course, name='Pass').first()
        passing_threshold = grade_range.min_grade if grade_range else Decimal('52.00')

        # Hitung skor asesmen sebagai persentase
        score_percentage = (Decimal(score) / Decimal(total_questions) * Decimal('100')) if total_questions > 0 else Decimal('0')

        # Tentukan apakah kursus selesai/lulus
        user_micro_progress.completed = (overall_progress >= Decimal('100') and score_percentage >= passing_threshold)
        if user_micro_progress.completed and not user_micro_progress.completed_at:
            user_micro_progress.completed_at = timezone.now()
        user_micro_progress.save()
        logger.debug(f"UserMicroProgress completed status for user {user.username}: {user_micro_progress.completed}")

    except Exception as e:
        logger.error(f"Error updating progress for user {user.username}, course {course.id}: {str(e)}")