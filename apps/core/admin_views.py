"""
Custom admin panel views — staff-only.
Provides user management, subscription overrides, system stats.
"""
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.db.models import Count, Q
from django.utils import timezone
from datetime import timedelta


@staff_member_required
def admin_dashboard(request):
    from apps.accounts.models import User
    from apps.analyser.models import FileUpload
    from apps.billing.models import Subscription
    from apps.audit.models import AuditEvent

    now = timezone.now()
    week_ago = now - timedelta(days=7)
    month_ago = now - timedelta(days=30)

    stats = {
        'total_users':      User.objects.count(),
        'new_users_week':   User.objects.filter(created_at__gte=week_ago).count(),
        'new_users_month':  User.objects.filter(created_at__gte=month_ago).count(),
        'pro_users':        Subscription.objects.filter(status__in=['active','on_trial']).count(),
        'total_uploads':    FileUpload.objects.count(),
        'uploads_week':     FileUpload.objects.filter(created_at__gte=week_ago).count(),
        'uploads_month':    FileUpload.objects.filter(created_at__gte=month_ago).count(),
        'total_analyses':   FileUpload.objects.filter(status='done').count(),
        'error_rate':       FileUpload.objects.filter(status='error').count(),
        'recent_events':    AuditEvent.objects.select_related('user').order_by('-timestamp')[:15],
    }

    # Top users by upload count
    # Daily upload counts for last 30 days
    from django.db.models.functions import TruncDate
    from django.db.models import Count as DCount
    import json as _json
    daily = (
        FileUpload.objects
        .filter(created_at__gte=month_ago)
        .annotate(date=TruncDate('created_at'))
        .values('date')
        .annotate(count=DCount('id'))
        .order_by('date')
    )
    stats['daily_uploads'] = _json.dumps([
        {'date': d['date'].strftime('%b %d'), 'count': d['count']}
        for d in daily
    ])

    top_users = User.objects.annotate(uc=Count('uploads')).order_by('-uc')[:10]

    return render(request, 'admin_panel/dashboard.html', {'stats': stats, 'top_users': top_users})


@staff_member_required
def admin_users(request):
    from apps.accounts.models import User
    from apps.billing.models import Subscription

    q = request.GET.get('q', '')
    status = request.GET.get('status', '')

    users = User.objects.select_related('subscription').annotate(uc=Count('uploads'))
    if q:
        users = users.filter(Q(email__icontains=q) | Q(first_name__icontains=q) | Q(last_name__icontains=q))
    if status == 'pro':
        users = users.filter(subscription__status__in=['active','on_trial'])
    elif status == 'free':
        users = users.exclude(subscription__status__in=['active','on_trial'])
    elif status == 'staff':
        users = users.filter(is_staff=True)

    users = users.order_by('-created_at')[:200]
    return render(request, 'admin_panel/users.html', {'users': users, 'q': q, 'status': status})


@staff_member_required
def admin_user_detail(request, user_id):
    from apps.accounts.models import User
    from apps.analyser.models import FileUpload
    from apps.audit.models import AuditEvent

    user = get_object_or_404(User, pk=user_id)
    uploads = FileUpload.objects.filter(user=user).order_by('-created_at')[:20]
    events  = AuditEvent.objects.filter(user=user).order_by('-timestamp')[:20]
    sub     = getattr(user, 'subscription', None)
    return render(request, 'admin_panel/user_detail.html', {
        'target_user': user, 'uploads': uploads, 'events': events, 'sub': sub,
    })


@staff_member_required
@require_POST
def admin_toggle_staff(request, user_id):
    from apps.accounts.models import User
    user = get_object_or_404(User, pk=user_id)
    if user == request.user:
        messages.error(request, "Can't modify your own staff status.")
        return redirect('core:admin_users')
    user.is_staff = not user.is_staff
    user.save(update_fields=['is_staff'])
    messages.success(request, f"{'Granted' if user.is_staff else 'Revoked'} staff access for {user.email}")
    return redirect('core:admin_user_detail', user_id=user_id)


@staff_member_required
@require_POST
def admin_grant_pro(request, user_id):
    """Manually grant/revoke Pro access for a user."""
    from apps.accounts.models import User
    from apps.billing.models import Subscription, Plan
    user = get_object_or_404(User, pk=user_id)
    sub, _ = Subscription.objects.get_or_create(user=user)
    action = request.POST.get('action', 'grant')
    if action == 'grant':
        sub.plan = Plan.PRO_MONTHLY
        sub.status = 'active'
        from datetime import timedelta
        sub.current_period_end = timezone.now() + timedelta(days=30)
        sub.save()
        messages.success(request, f'Pro access granted to {user.email} (30 days).')
    else:
        sub.plan = Plan.FREE
        sub.status = 'inactive'
        sub.save()
        messages.success(request, f'Pro access revoked from {user.email}.')
    return redirect('core:admin_user_detail', user_id=user_id)


@staff_member_required
@require_POST
def admin_delete_user(request, user_id):
    from apps.accounts.models import User
    from apps.analyser.models import FileUpload
    user = get_object_or_404(User, pk=user_id)
    if user == request.user:
        messages.error(request, "Can't delete your own account from here.")
        return redirect('core:admin_users')
    for upload in FileUpload.objects.filter(user=user):
        try: upload.file.delete(save=False)
        except: pass
    email = user.email
    user.delete()
    messages.success(request, f'User {email} permanently deleted.')
    return redirect('core:admin_users')
