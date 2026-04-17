from django.utils.functional import SimpleLazyObject


def _get_branding(request):
    if not request.user.is_authenticated:
        return None
    try:
        return request.user.branding
    except Exception:
        return None


class WhiteLabelMiddleware:
    """Attach branding config to every request."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        request.branding = SimpleLazyObject(lambda: _get_branding(request))
        return self.get_response(request)
