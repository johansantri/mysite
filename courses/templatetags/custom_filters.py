from django import template
import random
from datetime import datetime
from courses.models import Course  # ✅ Tambahkan ini
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

@register.filter
def mask_phone(value):
    """
    Menyembunyikan semua angka kecuali 4 angka terakhir.
    """
    if not value or len(value) < 4:
        return '****'
    return '*' * (len(value) - 4) + value[-4:]

@register.filter
def mask_year(date_value):
    """
    Menampilkan bulan dan tanggal, menyembunyikan tahun (diganti ****).
    Bisa terima date object atau string.
    """
    if not date_value:
        return ''
    
    # Coba parsing kalau berupa string
    if isinstance(date_value, str):
        try:
            date_value = datetime.strptime(date_value, '%Y-%m-%d')
        except ValueError:
            return 'Invalid date'

    return date_value.strftime('%b %d, ****')


#untuk filter course bahasa
@register.filter
def get_language_name(language_code):
    """Mengembalikan nama bahasa berdasarkan kode bahasa."""
    choice_language = dict(Course.choice_language)
    return choice_language.get(language_code, language_code)  # Mengembalikan kode bahasa jika tidak ditemukan
#dan juga ini
@register.filter
def dict_get(dictionary, key):
    return dictionary.get(key, '')