from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from apps.analyser.models import FileUpload
from .models import JoinConfig
from .engine import execute_join, save_join_result


@login_required
def join_builder(request):
    uploads = FileUpload.objects.filter(user=request.user, status='done')
    recent_joins = JoinConfig.objects.filter(user=request.user)[:10]
    return render(request, 'joins/builder.html', {
        'uploads': uploads,
        'recent_joins': recent_joins,
        'join_types': JoinConfig.JOIN_CHOICES,
    })


@login_required
def get_columns(request, pk):
    """HTMX: return column options for a selected upload."""
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    cols = [c['name'] for c in (upload.analysis_result or {}).get('columns', [])]
    from django.http import HttpResponse
    side = request.GET.get('side', 'left')
    opts = ''.join(f'<option value="{c}">{c}</option>' for c in cols)
    return HttpResponse(f'<select name="{side}_key" class="input-field text-sm">'
                        f'<option value="">Select key column…</option>{opts}</select>')


@login_required
@require_POST
def execute(request):
    left_id  = request.POST.get('left_upload')
    right_id = request.POST.get('right_upload')
    left_key = request.POST.get('left_key', '')
    right_key = request.POST.get('right_key', '')
    join_type = request.POST.get('join_type', 'inner')
    name = request.POST.get('name', 'Joined Dataset')

    if not all([left_id, right_id, left_key, right_key]):
        messages.error(request, 'All fields required.')
        return redirect('joins:builder')

    left  = get_object_or_404(FileUpload, pk=left_id,  user=request.user)
    right = get_object_or_404(FileUpload, pk=right_id, user=request.user)

    try:
        result = execute_join(left, right, left_key, right_key, join_type)
        upload = save_join_result(request.POST.get('join_cfg', None), result['tmp_path'], name, request.user)

        JoinConfig.objects.create(
            user=request.user, name=name,
            left_upload=left, right_upload=right,
            left_key=left_key, right_key=right_key,
            join_type=join_type, result_upload=upload,
        )
        messages.success(request, f'Join complete — {result["rows"]:,} rows, {result["cols"]} columns.')
        return redirect('analyser:result', pk=upload.id)
    except Exception as e:
        messages.error(request, f'Join failed: {e}')
        return redirect('joins:builder')
