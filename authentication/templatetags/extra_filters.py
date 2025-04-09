# myapp/templatetags/extra_filters.py

from django import template

register = template.Library()

@register.filter
def split(value, arg):
    """
    Splits a string by the given delimiter (arg) and returns a list.
    """
    return value.split(arg)
@register.filter
def trim(value):
    """
    Trims leading and trailing spaces from a string.
    """
    return value.strip() if value else value