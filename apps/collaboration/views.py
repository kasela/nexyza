from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_POST
from django.template.loader import render_to_string
from apps.analyser.models import FileUpload
from .models import CollabSession, CollabComment, CollabAction


def _upload_for_user(request, upload_id):
    return get_object_or_404(FileUpload, pk=upload_id, user=request.user)


@login_required
def presence(request, upload_id):
    upload = _upload_for_user(request, upload_id)
    from django.utils import timezone
    from datetime import timedelta
    cutoff = timezone.now() - timedelta(minutes=5)
    sessions = CollabSession.objects.filter(
        upload=upload, is_active=True, last_seen__gte=cutoff
    ).select_related('user')
    data = [{'user_email': s.user.email, 'initials': s.user.email[0].upper(), 'tab': s.cursor_tab} for s in sessions]
    return JsonResponse({'viewers': data})


@login_required
def comments(request, upload_id):
    upload = _upload_for_user(request, upload_id)
    tab = request.GET.get('tab', '')
    qs = CollabComment.objects.filter(upload=upload).select_related('author')
    if tab:
        qs = qs.filter(tab=tab)
    data = [{
        'id': str(c.id),
        'author': c.author.email,
        'initials': c.author.email[0].upper(),
        'text': c.text,
        'tab': c.tab,
        'column_ref': c.column_ref,
        'chart_ref': c.chart_ref,
        'section_ref': c.section_ref,
        'is_resolved': c.is_resolved,
        'created_at': c.created_at.isoformat(),
    } for c in qs[:50]]
    return JsonResponse({'comments': data})


@login_required
@require_POST
def add_comment(request, upload_id):
    upload = _upload_for_user(request, upload_id)
    text = (request.POST.get('text') or '').strip()
    if not text:
        return JsonResponse({'ok': False, 'error': 'Comment text is required.'}, status=400)
    CollabComment.objects.create(
        upload=upload,
        author=request.user,
        tab=(request.POST.get('tab') or 'overview')[:30],
        column_ref=(request.POST.get('column_ref') or '')[:255],
        chart_ref=(request.POST.get('chart_ref') or '')[:255],
        section_ref=(request.POST.get('section_ref') or '')[:255],
        text=text[:1000],
    )
    return _panel_response(request, upload)


@login_required
@require_POST
def resolve_comment(request, upload_id, comment_id):
    upload = _upload_for_user(request, upload_id)
    CollabComment.objects.filter(pk=comment_id, upload=upload).update(is_resolved=True)
    return _panel_response(request, upload)


@login_required
def actions(request, upload_id):
    upload = _upload_for_user(request, upload_id)
    qs = CollabAction.objects.filter(upload=upload).select_related('creator', 'assignee')
    data = [{
        'id': str(a.id),
        'title': a.title,
        'detail': a.detail,
        'status': a.status,
        'due_date': a.due_date.isoformat() if a.due_date else '',
        'creator': a.creator.email,
        'assignee': a.assignee.email if a.assignee else '',
        'chart_ref': a.chart_ref,
        'section_ref': a.section_ref,
    } for a in qs[:50]]
    return JsonResponse({'actions': data})


@login_required
@require_POST
def add_action(request, upload_id):
    upload = _upload_for_user(request, upload_id)
    title = (request.POST.get('title') or '').strip()
    if not title:
        return JsonResponse({'ok': False, 'error': 'Action title is required.'}, status=400)
    due_date = (request.POST.get('due_date') or '').strip() or None
    CollabAction.objects.create(
        upload=upload,
        creator=request.user,
        title=title[:255],
        detail=(request.POST.get('detail') or '')[:2000],
        due_date=due_date,
        chart_ref=(request.POST.get('chart_ref') or '')[:255],
        section_ref=(request.POST.get('section_ref') or '')[:255],
    )
    return _panel_response(request, upload)


@login_required
@require_POST
def update_action_status(request, upload_id, action_id):
    upload = _upload_for_user(request, upload_id)
    status = (request.POST.get('status') or CollabAction.STATUS_OPEN).strip()
    if status not in {CollabAction.STATUS_OPEN, CollabAction.STATUS_IN_PROGRESS, CollabAction.STATUS_DONE}:
        return JsonResponse({'ok': False, 'error': 'Invalid status.'}, status=400)
    CollabAction.objects.filter(pk=action_id, upload=upload).update(status=status)
    return _panel_response(request, upload)


@login_required
def panel(request, upload_id):
    upload = _upload_for_user(request, upload_id)
    return _panel_response(request, upload)


def _panel_response(request, upload):
    comments_qs = CollabComment.objects.filter(upload=upload).select_related('author').order_by('-created_at')[:12]
    actions_qs = CollabAction.objects.filter(upload=upload).select_related('creator', 'assignee').order_by('status', '-created_at')[:12]
    html = render_to_string('analyser/partials/collaboration_panel.html', {
        'upload': upload,
        'comments_list': comments_qs,
        'actions_list': actions_qs,
    }, request=request)
    if request.headers.get('HX-Request') == 'true':
        return HttpResponse(html)
    return JsonResponse({'html': html})
