from .models import log_event, AuditEvent

TRACKED_PATHS = {
    '/workspace/': (AuditEvent.ACTION_VIEW, 'upload'),
    '/audit/':   None,  # exclude audit log itself
}


class AuditMiddleware:
    """Passively logs view and export events without blocking."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        try:
            self._maybe_log(request, response)
        except Exception:
            pass
        return response

    def _maybe_log(self, request, response):
        if not request.user.is_authenticated:
            return
        path = request.path
        if response.status_code not in (200, 201):
            return

        if '/export/' in path and request.method == 'GET':
            parts = path.strip('/').split('/')
            try:
                pk = int(parts[1])
                fmt = parts[-1]
                log_event(request, AuditEvent.ACTION_EXPORT,
                          f"FileUpload:{pk}", {'format': fmt})
            except Exception:
                pass
        elif path.startswith('/accounts/login') and request.method == 'POST':
            log_event(request, AuditEvent.ACTION_LOGIN, '', {})
