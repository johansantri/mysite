from django import template

register = template.Library()

@register.filter
def add_class(field, css_class):
    """
    Menambahkan kelas CSS ke widget field form.
    """
    return field.as_widget(attrs={"class": css_class})