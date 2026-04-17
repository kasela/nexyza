from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from .models import AuditEvent


@login_required
def audit_log(request):
    from django.utils import timezone
    from datetime import timedelta

    qs = AuditEvent.objects.filter(user=request.user).select_related('user')

    action_filter = request.GET.get('action', '')
    range_filter  = request.GET.get('range', '')

    if action_filter:
        qs = qs.filter(action=action_filter)

    if range_filter == 'today':
        qs = qs.filter(timestamp__date=timezone.now().date())
    elif range_filter == 'week':
        qs = qs.filter(timestamp__gte=timezone.now() - timedelta(days=7))
    elif range_filter == 'month':
        qs = qs.filter(timestamp__gte=timezone.now() - timedelta(days=30))

    events = qs[:500]
    return render(request, 'audit/log.html', {
        'events':        events,
        'action_filter': action_filter,
        'range_filter':  range_filter,
    })


@login_required
def admin_audit_log(request):
    """Full audit log — staff only."""
    if not request.user.is_staff:
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden()
    events = AuditEvent.objects.select_related('user').all()[:500]
    return render(request, 'audit/admin_log.html', {'events': events})
