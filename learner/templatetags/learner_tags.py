from django import template
from django.db.models import Count
from courses.models import PeerReview, Submission
register = template.Library()

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