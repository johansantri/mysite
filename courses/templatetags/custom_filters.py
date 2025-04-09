from django import template
import random
register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Filter untuk mengambil nilai dari dictionary berdasarkan key"""
    return dictionary.get(key)
@register.filter
def randomize(queryset):
    # Konversi queryset ke list dan acak
    items = list(queryset)
    random.shuffle(items)
    return items

@register.filter
def split(value, delimiter=","):
    """Memisahkan string berdasarkan delimiter."""
    return value.split(delimiter)