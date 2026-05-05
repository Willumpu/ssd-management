from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """从字典中获取键值"""
    if dictionary is None:
        return 0
    return dictionary.get(key, 0)


@register.filter
def sum_quantities(stocks):
    """计算库存列表的总数量"""
    if not stocks:
        return 0
    return sum(s.quantity for s in stocks)
