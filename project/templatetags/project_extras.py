from django import template

register = template.Library()


@register.filter
def split(value, arg):
    """按指定分隔符分割字符串"""
    if not value:
        return []
    return [s.strip() for s in str(value).split(arg) if s.strip()]
