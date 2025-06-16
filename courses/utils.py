# utils.py
from decimal import Decimal
from django.core.exceptions import ValidationError  # Add this import
from .models import Assessment, GradeRange, QuestionAnswer, Submission, AssessmentScore,BlacklistedKeyword
from django.core.cache import cache
from django.utils.timezone import now
from datetime import timedelta

def user_has_passed_course(user, course):
    assessments = Assessment.objects.filter(section__courses=course).distinct()
    grade_range = GradeRange.objects.filter(course=course, name='Pass').first()
    passing_threshold = grade_range.min_grade if grade_range else Decimal('52.00')

    total_max_score = Decimal('0')
    total_score = Decimal('0')
    all_submitted = True

    for assessment in assessments:
        score = Decimal('0')
        total_questions = assessment.questions.count()
        correct_answers = 0

        if total_questions > 0:
            user_answers = QuestionAnswer.objects.filter(user=user, question__assessment=assessment)
            if not user_answers.exists():
                all_submitted = False
                continue

            for question in assessment.questions.all():
                user_q_answers = user_answers.filter(question=question)
                correct_answers += sum(1 for qa in user_q_answers if qa.choice.is_correct)

            score = (Decimal(correct_answers) / Decimal(total_questions)) * Decimal(assessment.weight)
        else:
            submission = Submission.objects.filter(user=user, askora__assessment=assessment).order_by('-submitted_at').first()
            if not submission:
                all_submitted = False
                continue
            assessment_score = AssessmentScore.objects.filter(submission=submission).first()
            if assessment_score:
                score = assessment_score.final_score

        score = min(score, Decimal(assessment.weight))
        total_max_score += Decimal(assessment.weight)
        total_score += score

    if total_max_score == 0:
        return False

    final_percentage = (total_score / total_max_score) * 100
    return all_submitted and final_percentage >= passing_threshold



def check_for_blacklisted_keywords(comment):
    blacklisted_keywords = BlacklistedKeyword.objects.all()
    
    for keyword in blacklisted_keywords:
        if keyword.keyword.lower() in comment.lower():
            return keyword.keyword  # Return kata yang dilanggar

    return None


def is_suspicious(request, threshold=5, time_window=60):
    """
    Detect suspicious activity based on request rate limiting.
    - `threshold`: The maximum number of requests allowed within `time_window` seconds.
    - `time_window`: The time window in seconds to check for frequent requests.
    """
    # Use the user IP or session key to track requests (session is a fallback for anonymous users)
    user_identifier = request.user.id if request.user.is_authenticated else request.session.session_key
    if not user_identifier:
        return False  # If no identifier is found, assume it's not suspicious
    
    # Cache key to track requests
    cache_key = f'user_activity_{user_identifier}'
    
    # Get the timestamp of the first request in this time window (cached)
    first_request_time = cache.get(cache_key)
    
    if not first_request_time:
        # If no first request time is found, store the current time
        cache.set(cache_key, now(), timeout=time_window)
        return False  # Not suspicious yet (first request)
    
    # If a request has occurred within the time window (e.g., 60 seconds)
    if (now() - first_request_time) < timedelta(seconds=time_window):
        # If they exceeded the threshold, mark it as suspicious
        request_count = cache.get(f'{cache_key}_count', 0) + 1
        cache.set(f'{cache_key}_count', request_count, timeout=time_window)
        
        if request_count > threshold:
            return True  # Suspicious if requests exceed the threshold
    else:
        # Reset the counter and the first request time if the time window has passed
        cache.set(cache_key, now(), timeout=time_window)
        cache.set(f'{cache_key}_count', 1, timeout=time_window)
    
    return False

#ambil ip client untuk di simpan di log
def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        return x_forwarded_for.split(',')[0]
    return request.META.get('REMOTE_ADDR')



