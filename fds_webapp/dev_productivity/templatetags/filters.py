from django import template

register = template.Library()

@register.filter(name='mul')
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except Exception:
        return 0



