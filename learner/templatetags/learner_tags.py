from django import template

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