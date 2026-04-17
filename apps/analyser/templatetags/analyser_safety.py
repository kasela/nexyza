from django import template
from django.conf import settings
from apps.analyser.utils.safe_text import sanitize_text

register = template.Library()


@register.filter(name='safe_text')
def safe_text(value):
    return sanitize_text(value, limit=180, preview=False)


@register.filter(name='safe_preview')
def safe_preview(value):
    return sanitize_text(value, limit=48, preview=True)


@register.simple_tag(name='analyser_safe_mode')
def analyser_safe_mode():
    return getattr(settings, 'ANALYSER_SAFE_MODE', True)
