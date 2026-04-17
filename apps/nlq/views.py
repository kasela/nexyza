from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.views.decorators.http import require_POST
from apps.analyser.models import FileUpload
from .models import NLQuery
from .engine import answer_question


@login_required
@require_POST
def ask(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    sub = getattr(request, 'subscription', None)
    if not (sub and sub.is_active):
        return HttpResponse(
            '<div class="p-4 bg-amber-900/20 border border-amber-700/30 rounded-xl text-amber-300 text-sm">'
            '🔒 Natural Language Query requires <strong>Pro</strong>. '
            '<a href="/billing/pricing/" class="underline">Upgrade →</a></div>'
        )

    question = request.POST.get('question', '').strip()
    if not question:
        return HttpResponse('<p class="text-red-400 text-sm">Please enter a question.</p>')

    try:
        result = answer_question(upload, question)
        NLQuery.objects.create(
            user=request.user, upload=upload, question=question,
            answer=result['answer'], sql=result['code'],
            chart_data=result['chart_data'], tokens_used=result['tokens_used'],
            error=result['error'],
        )
    except Exception as e:
        return HttpResponse(f'<div class="p-4 bg-red-900/20 rounded-xl text-red-300 text-sm">Error: {e}</div>')

    # Audit log
    try:
        from apps.audit.models import log_event, AuditEvent
        log_event(request, AuditEvent.ACTION_NLQ,
                  f"FileUpload:{upload.id}", {'question': question[:200], 'tokens': result.get('tokens_used',0)})
    except Exception:
        pass
    from django.template.loader import render_to_string
    return HttpResponse(render_to_string('nlq/partials/answer.html', {
        'question': question, 'result': result
    }, request=request))


@login_required
def history(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    queries = NLQuery.objects.filter(upload=upload, user=request.user)[:20]
    from django.template.loader import render_to_string
    return HttpResponse(render_to_string('nlq/partials/history.html',
                                          {'queries': queries}, request=request))
