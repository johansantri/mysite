# myapp/templatetags/extra_filters.py

from django import template
import random
from django.utils.translation import get_language_info
register = template.Library()
from authentication.utils import is_user_online


@register.filter
def get_language_name(language_code):
    """Mengambil nama bahasa berdasarkan kode bahasa"""
    try:
        return get_language_info(language_code)['name']
    except KeyError:
        return language_code  # Kembalikan kode bahasa jika tidak ditemukan
    
@register.filter
def randomize(queryset):
    """Mengacak urutan elemen dalam list atau queryset"""
    items = list(queryset)  # pastikan queryset diubah menjadi list
    random.shuffle(items)
    return items
   
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

@register.filter
def truncate_words(value, word_count=20):
    """
    Truncate a string to a specified number of words (default is 20).
    """
    words = value.split()
    if len(words) > word_count:
        return ' '.join(words[:word_count]) + '...'
    return value

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)

@register.filter
def index(lst, i):
    try:
        return lst[int(i)]
    except (IndexError, ValueError, TypeError):
        return ''

@register.filter
def add_class(field, css_class):
    return field.as_widget(attrs={"class": css_class})


#untuk singkat nama di item komentar
@register.filter
def initials(full_name):
    if not full_name:
        return ""
    parts = full_name.strip().split()
    if len(parts) == 1:
        # Kalau cuma 1 kata, ambil huruf pertama saja
        return parts[0][0].upper()
    # Ambil huruf pertama dari kata pertama & terakhir
    return (parts[0][0] + parts[-1][0]).upper()

#online user check
@register.simple_tag
def user_online(user):
    return is_user_online(user)