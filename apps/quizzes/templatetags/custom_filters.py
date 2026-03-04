from django import template

register = template.Library()

@register.filter
def enumerate(sequence):
    """Enumerate in template"""
    return enumerate(sequence)