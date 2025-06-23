from django import template
from django.db.models import Count
from django.urls import reverse
from courses.models import PeerReview, Submission,Course, Section, Material, Assessment,MaterialRead, AssessmentRead, QuestionAnswer, Submission, AssessmentScore, GradeRange, CourseProgress
import random
from decimal import Decimal


register = template.Library()


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
    

@register.simple_tag(takes_context=True)
def get_course_completion_status(context):
    """
    Calculate course completion status for the current user and course.
    
    Args:
        context: Template context containing request, course, next_url, etc.
    
    Returns:
        dict: Contains is_completed, certificate_url, and assessments_completed_percentage.
    """
    request = context['request']
    user = request.user
    course = context.get('course')
    next_url = context.get('next_url')
    if not course or next_url:
        return {
            'is_completed': False,
            'certificate_url': None,
            'assessments_completed_percentage': 0,
        }

    # Hitung progres seperti di dashbord
    materials = Material.objects.filter(section__courses=course)
    total_materials = materials.count()
    materials_read = MaterialRead.objects.filter(user=user, material__in=materials).count()
    materials_read_percentage = (Decimal(materials_read) / Decimal(total_materials) * 100) if total_materials > 0 else Decimal('0')

    assessments = Assessment.objects.filter(section__courses=course)
    total_assessments = assessments.count()
    assessments_completed = AssessmentRead.objects.filter(user=user, assessment__in=assessments).count()
    assessments_completed_percentage = (Decimal(assessments_completed) / Decimal(total_assessments) * 100) if total_assessments > 0 else Decimal('0')

    progress = ((materials_read_percentage + assessments_completed_percentage) / Decimal('2')) if (total_materials + total_assessments) > 0 else Decimal('0')

    # Hitung skor keseluruhan
    grade_range = GradeRange.objects.filter(course=course, name='Pass').first()
    passing_threshold = grade_range.min_grade if grade_range else Decimal('52.00')
    total_score = Decimal('0')
    total_max_score = Decimal('0')
    for assessment in assessments:
        score_value = Decimal('0')
        total_questions = assessment.questions.count()
        if total_questions > 0:
            total_correct_answers = QuestionAnswer.objects.filter(
                question__assessment=assessment, user=user, choice__is_correct=True
            ).count()
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

    # Tentukan status kelulusan
    is_completed = (
        progress >= 100 and
        assessments_completed_percentage == 100 and
        overall_percentage >= passing_threshold and
        next_url is None
    )

    # Gunakan URL generate_certificate yang sudah ada
    certificate_url = reverse('courses:generate_certificate', kwargs={'course_id': course.id}) if is_completed else None

    return {
        'is_completed': is_completed,
        'certificate_url': certificate_url,
        'assessments_completed_percentage': assessments_completed_percentage,
        'course_progress': progress,
    }