from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Filter untuk mengambil nilai dari dictionary berdasarkan key"""
    return dictionary.get(key)