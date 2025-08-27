from django import template
from django.db.models import Count
from django.urls import reverse
from courses.models import PeerReview, LTIResult,Submission,Course, Section, Material, Assessment,MaterialRead, AssessmentRead, QuestionAnswer, Submission, AssessmentScore, GradeRange, CourseProgress
import random
import re
from decimal import Decimal
import logging


register = template.Library()

@register.filter
def split_by_equal(value):
    """Split string by '=' and return list."""
    return value.split('=')

@register.filter
def split(value, key):
    return value.split(key)

@register.filter
def split_lines(value):
    return value.strip().splitlines()

@register.filter
def linepartition(value, separator="="):
    """Split string into (before, sep, after) like Python's str.partition()"""
    return value.partition(separator)

@register.filter
def make_iframes_responsive(value):
    # Tambahkan wrapper div responsive pada semua iframe
    pattern = r'(<iframe.*?</iframe>)'
    replacement = r'<div class="ratio ratio-16x9">\1</div>'
    return re.sub(pattern, replacement, value, flags=re.DOTALL)

@register.filter
def shuffled(value):
    result = list(value)
    random.shuffle(result)
    return result

@register.filter
def dict_get(dictionary, key):
    """
    Safely get a value from a dictionary using a key.
    Returns None if the key doesn't exist.
    """
    return dictionary.get(key)

@register.filter
def get_question_answer(dictionary, question_id):
    """
    Get the answer object for a given question ID from the answered_questions dictionary.
    Returns None if no answer exists.
    """
    return dictionary.get(question_id)


@register.filter
def dict_get(dictionary, key):
    return dictionary.get(key)


@register.filter
def dict_get(d, key):
    return d.get(key)


@register.filter
def subtract(value, arg):
    return value - arg

@register.simple_tag
def get_review_progress(submission):
    total_participants = Submission.objects.filter(
        askora__assessment=submission.askora.assessment
    ).values('user').distinct().count()
    
    reviews_received = PeerReview.objects.filter(
        submission=submission
    ).aggregate(
        count=Count('id'),
        reviewers=Count('reviewer', distinct=True)
    )
    
    return {
        'received': reviews_received['count'] or 0,
        'reviewers': reviews_received['reviewers'] or 0,
        'total': total_participants - 1,  # exclude submitter
        'completed': reviews_received['reviewers'] >= (total_participants - 1)
    }


@register.filter
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return ''
    
logger = logging.getLogger(__name__)


@register.simple_tag(takes_context=True)
def get_course_completion_status(context):
    request = context['request']
    user = request.user
    course = context.get('course')

    if not course:
        #logger.warning("No course provided in get_course_completion_status")
        return {
            'is_completed': False,
            'certificate_url': None,
            'assessments_completed_percentage': 0,
            'course_progress': 0,
            'overall_percentage': 0,
            'passing_threshold': 0
        }

    # Ambil passing threshold dari GradeRange
    grade_range = GradeRange.objects.filter(course=course, name__iexact='Pass').first()
    passing_threshold = float(grade_range.min_grade) if grade_range else 52.0

    # Hitung progres materi
    materials = Material.objects.filter(section__courses=course)
    total_materials = materials.count()
    materials_read = MaterialRead.objects.filter(user=user, material__in=materials).count()

    # Hitung progres assessment
    assessments = Assessment.objects.filter(section__courses=course)
    total_assessments = assessments.count()
    assessments_completed = 0
    total_score = Decimal(0)
    total_max_score = Decimal(0)
    all_assessments_submitted = True

    for assessment in assessments:
        score_value = Decimal(0)
        weight = Decimal(assessment.weight or 1)

        # Cek apakah assessment adalah LTI
        lti_result = LTIResult.objects.filter(user=user, assessment=assessment, score__isnull=False).first()
        if lti_result:
            # Asumsi skor LTI dalam skala 0.0-1.0; jika dalam skala 0-100, normalisasi
            lti_score = Decimal(lti_result.score)
            if lti_score > 1:  # Jika skor dalam skala 0-100
                lti_score = lti_score / Decimal(100)
            score_value = min(lti_score * weight, weight)  # Batasi skor maksimum ke bobot
            assessments_completed += 1
            #logger.debug(f"LTIResult for user {user.id}, assessment {assessment.id}: raw_score={lti_result.score}, normalized_score={lti_score}, weight={weight}, score_value={score_value}")
        elif assessment.questions.exists():  # Pilihan ganda
            has_answers = QuestionAnswer.objects.filter(
                user=user, question__assessment=assessment
            ).exists()

            if not has_answers:
                all_assessments_submitted = False
                #logger.debug(f"No answers for quiz assessment {assessment.id} by user {user.id}")
                continue

            total_questions = assessment.questions.count()
            correct_answers = QuestionAnswer.objects.filter(
                user=user,
                question__assessment=assessment,
                choice__is_correct=True
            ).count()

            assessments_completed += 1
            score_value = (Decimal(correct_answers) / Decimal(total_questions)) * weight if total_questions > 0 else Decimal(0)
            #logger.debug(f"Quiz assessment {assessment.id}: correct={correct_answers}, total={total_questions}, weight={weight}, score_value={score_value}")
        else:  # ORA / manual
            submission = Submission.objects.filter(
                user=user, askora__assessment=assessment
            ).order_by('-submitted_at').first()

            if not submission:
                all_assessments_submitted = False
                #logger.debug(f"No submission for ORA assessment {assessment.id} by user {user.id}")
                continue

            score_obj = AssessmentScore.objects.filter(submission=submission).first()
            if not score_obj:
                all_assessments_submitted = False
               #logger.debug(f"No score for ORA submission in assessment {assessment.id} by user {user.id}")
                continue

            assessments_completed += 1
            score_value = Decimal(score_obj.final_score)
            #logger.debug(f"ORA assessment {assessment.id}: score={score_value}, weight={weight}")

        total_score += score_value
        total_max_score += weight

    assessments_completed_percentage = (
        (assessments_completed / total_assessments) * 100 if total_assessments > 0 else 0
    )

    # Hitung persentase keseluruhan dan batasi ke 100%
    overall_percentage = (
        min(float((total_score / total_max_score) * 100), 100.0) if total_max_score > 0 else 0
    )

    is_completed = all_assessments_submitted and overall_percentage >= passing_threshold

    certificate_url = (
        reverse('courses:generate_certificate', kwargs={'course_id': course.id})
        if is_completed else None
    )

    #logger.info(f"Course completion status for user {user.id}, course {course.id}: "
                #f"is_completed={is_completed}, assessments_completed={assessments_completed}/{total_assessments}, "
                #f"total_score={total_score}, total_max_score={total_max_score}, "
               #f"overall_percentage={overall_percentage}, passing_threshold={passing_threshold}")

    return {
        'is_completed': is_completed,
        'certificate_url': certificate_url,
        'assessments_completed_percentage': round(assessments_completed_percentage, 2),
        'course_progress': float(context.get('course_progress', 0)),
        'overall_percentage': round(overall_percentage, 2),
        'passing_threshold': passing_threshold
    }


    
@register.simple_tag(takes_context=True)
def is_content_read(context, content_type, content_id):
    """
    Check if a material or assessment has been read/opened or completed by the user.
    
    Args:
        context: Template context (includes request).
        content_type: 'material' or 'assessment'.
        content_id: ID of the material or assessment.
    
    Returns:
        bool: True if content is read/opened or completed, False otherwise.
    """
    user = context['request'].user
    if not user.is_authenticated:
        return False
    if content_type == 'material':
        return MaterialRead.objects.filter(user=user, material_id=content_id).exists()
    elif content_type == 'assessment':
        # Cek LTIResult untuk assessment LTI
        if LTIResult.objects.filter(user=user, assessment_id=content_id, score__isnull=False).exists():
            #logger.debug(f"LTIResult found for user {user.id}, assessment {content_id}")
            return True
        # Cek QuestionAnswer untuk kuis
        if QuestionAnswer.objects.filter(user=user, question__assessment_id=content_id).exists():
            #logger.debug(f"QuestionAnswer found for user {user.id}, assessment {content_id}")
            return True
        # Cek Submission untuk ORA
        if Submission.objects.filter(user=user, askora__assessment_id=content_id).exists():
            #logger.debug(f"Submission found for user {user.id}, assessment {content_id}")
            return True
        # Fallback ke AssessmentRead untuk menandai bahwa assessment telah dibuka
        assessment_read = AssessmentRead.objects.filter(user=user, assessment_id=content_id).exists()
        #logger.debug(f"AssessmentRead for user {user.id}, assessment {content_id}: {assessment_read}")
        return assessment_read
    return False