from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone
from .models import CourseProgress, Score, UserMicroProgress, GradeRange,Material,MaterialRead,Assessment,AssessmentRead
from decimal import Decimal


@receiver(post_save, sender=Score)
def update_course_progress_with_score(sender, instance, created, **kwargs):
    """
    Update CourseProgress dengan nilai dari Score
    dan memastikan skor dan progres diperbarui dengan benar.
    """
    user = instance.user
    course = instance.course
    score = instance.score  # Ambil nilai skor dari Score

    # Dapatkan atau buat CourseProgress untuk user dan course tertentu
    course_progress, created = CourseProgress.objects.get_or_create(user=user, course=course)

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

    # Perbarui UserMicroProgress jika diperlukan
    user_micro_progress, _ = UserMicroProgress.objects.get_or_create(user=user, course=course)
    user_micro_progress.progress_percentage = float(overall_progress)
    user_micro_progress.score = score  # Pastikan score juga diperbarui
    user_micro_progress.save()

    # Ambil ambang batas kelulusan
    grade_range = GradeRange.objects.filter(course=course, name='Pass').first()
    passing_threshold = grade_range.min_grade if grade_range else Decimal('52.00')

    # Hitung apakah kursus dianggap selesai/lulus
    overall_percentage = (Decimal(score) / Decimal(100)) * Decimal('100')
    user_micro_progress.completed = (overall_progress == Decimal('100') and overall_percentage >= passing_threshold)

    if user_micro_progress.completed:
        user_micro_progress.completed_at = timezone.now()

    # Simpan perubahan di UserMicroProgress
    user_micro_progress.save()
