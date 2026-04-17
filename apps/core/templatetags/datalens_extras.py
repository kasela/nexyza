from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def split(value, delimiter=','):
    """Split a string by delimiter."""
    return [v.strip() for v in str(value).split(delimiter)]


@register.filter
def get_item(dictionary, key):
    """Dict lookup by key in templates."""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None


@register.filter
def keys(dictionary):
    """Return dict keys."""
    if isinstance(dictionary, dict):
        return list(dictionary.keys())
    return []


@register.filter
def abs_val(value):
    """Absolute value."""
    try:
        return abs(int(value))
    except (TypeError, ValueError):
        return value


@register.filter
def replace(value, arg):
    """Replace underscores/chars. Usage: value|replace:"_" replaces _ with space."""
    return str(value).replace(str(arg), ' ')


@register.simple_tag
def file_type_icon(file_type):
    icons = {'csv': '📊', 'excel': '📗', 'json': '🔷'}
    return mark_safe(icons.get(file_type, '📄'))


import json as _json
from django.utils.safestring import mark_safe as _mark_safe

@register.filter
def jsonify(value):
    """Serialize value to JSON string safe for inline <script>."""
    data = _json.dumps(value, default=str, ensure_ascii=False)
    data = (data
            .replace('<', r'\u003c')
            .replace('>', r'\u003e')
            .replace('&', r'\u0026')
            .replace('\u2028', r'\u2028')
            .replace('\u2029', r'\u2029')
            .replace(' ', r'\u2028')
            .replace(' ', r'\u2029'))
    return _mark_safe(data)


@register.filter(name='getattr')
def getattr_filter(obj, attr):
    """Safe getattr for templates."""
    return getattr(obj, str(attr), None)


@register.filter
def sub(value, arg):
    try:
        return int(value) - int(arg)
    except (TypeError, ValueError):
        return 0
