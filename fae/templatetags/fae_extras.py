from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """字典取值过滤器：{{ mydict|get_item:mykey }}"""
    if dictionary is None:
        return None
    return dictionary.get(key)
