from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    return dictionary.get(key)
@register.filter
def get_item(dictionary, key):
    """Get the value from dictionary by key."""
    return dictionary.get(key)

@register.filter
def get_item(dictionary, key):
    """Mengambil item dari dictionary berdasarkan key"""
    return dictionary.get(key)

@register.inclusion_tag('partner/comment_tree.html', takes_context=True)
def render_comment_tree(context, comment):
    request = context['request']
    return {
        'comment': comment,
        'replies': comment.get_replies(),
        'request': request,
    }