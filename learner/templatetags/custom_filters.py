import random
from django import template

register = template.Library()

@register.filter
def randomize(value):
    """Mengacak urutan elemen dalam list"""
    if isinstance(value, list):
        random.shuffle(value)
    return value
