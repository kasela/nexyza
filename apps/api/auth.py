from django.utils import timezone
from .models import APIKey


def authenticate_api_key(request):
    """Extract and validate API key from Authorization header or ?api_key= param."""
    from django.conf import settings
    prefix = settings.API_KEY_PREFIX

    auth_header = request.headers.get('Authorization', '')
    raw_key = None

    if auth_header.startswith('Bearer '):
        raw_key = auth_header[7:].strip()
    elif auth_header.startswith('Token '):
        raw_key = auth_header[6:].strip()
    else:
        raw_key = request.GET.get('api_key', '') or request.POST.get('api_key', '')

    if not raw_key:
        return None, 'No API key provided'

    if raw_key.startswith(prefix):
        raw_key = raw_key[len(prefix):]

    try:
        api_key = APIKey.objects.select_related('user').get(key=raw_key, is_active=True)
    except APIKey.DoesNotExist:
        return None, 'Invalid API key'

    if api_key.expires_at and api_key.expires_at < timezone.now():
        return None, 'API key expired'

    api_key.last_used = timezone.now()
    api_key.save(update_fields=['last_used'])

    sub = getattr(api_key.user, 'subscription', None)
    if not (sub and sub.is_active):
        return None, 'API access requires a Pro subscription'

    return api_key.user, None


def api_key_required(view_func):
    """Decorator for API views."""
    import functools
    from django.http import JsonResponse

    @functools.wraps(view_func)
    def wrapper(request, *args, **kwargs):
        user, error = authenticate_api_key(request)
        if error:
            return JsonResponse({'error': error}, status=401)

        # Rate limit check
        from django.conf import settings as s
        prefix = s.API_KEY_PREFIX
        raw_key = request.headers.get('Authorization', '')[7:].strip()
        if raw_key.startswith(prefix):
            raw_key = raw_key[len(prefix):]
        from .models import APIKey
        try:
            api_key_obj = APIKey.objects.get(key=raw_key, is_active=True)
            allowed, reason = api_key_obj.check_rate_limit()
            if not allowed:
                return JsonResponse({'error': reason}, status=429,
                                    headers={'Retry-After': '60',
                                             'X-RateLimit-Reset': '60'})
        except APIKey.DoesNotExist:
            pass  # already validated above

        request.api_user = user
        return view_func(request, *args, **kwargs)
    return wrapper
