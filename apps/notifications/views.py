from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages
from apps.analyser.models import FileUpload
from .models import NotificationRule, Notification
from .engine import check_rules


@login_required
def notification_center(request):
    notifs = list(Notification.objects.filter(user=request.user)[:100])
    rules  = NotificationRule.objects.filter(user=request.user).select_related('upload')
    uploads = FileUpload.objects.filter(user=request.user, status='done')
    unread = Notification.objects.filter(user=request.user, is_read=False).count()
    return render(request, 'notifications/center.html', {
        'notifications': notifs, 'rules': rules,
        'uploads': uploads, 'unread': unread,
    })


@login_required
@require_POST
def create_rule(request):
    upload_id = request.POST.get('upload_id')
    upload = get_object_or_404(FileUpload, pk=upload_id, user=request.user)
    NotificationRule.objects.create(
        user=request.user, upload=upload,
        name=request.POST.get('name', 'Alert'),
        column=request.POST.get('column', ''),
        metric=request.POST.get('metric', 'mean'),
        operator=request.POST.get('operator', 'gt'),
        threshold=float(request.POST.get('threshold', 0)),
    )
    messages.success(request, 'Alert rule created.')
    return redirect('notifications:center')


@login_required
@require_POST
def mark_read(request, pk):
    Notification.objects.filter(pk=pk, user=request.user).update(is_read=True)
    return JsonResponse({'ok': True})


@login_required
@require_POST
def mark_all_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return redirect('notifications:center')


@login_required
@require_POST
def delete_rule(request, pk):
    NotificationRule.objects.filter(pk=pk, user=request.user).delete()
    messages.success(request, 'Rule deleted.')
    return redirect('notifications:center')


@login_required
@require_POST
def check_now(request, pk):
    """Manually trigger rule-checking for an upload."""
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    triggered = check_rules(upload)
    messages.success(request, f'{len(triggered)} alert(s) triggered.' if triggered else 'No alerts triggered.')
    return redirect('notifications:center')
