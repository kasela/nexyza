from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from .models import DataSource, PipelineRun
from .tasks import run_pipeline, _next_run


@login_required
def pipeline_list(request):
    sources = DataSource.objects.filter(user=request.user).prefetch_related('runs')
    return render(request, 'pipeline/list.html', {'sources': sources})


@login_required
@require_POST
def create_source(request):
    name  = request.POST.get('name', '').strip()
    url   = request.POST.get('source_url', '').strip()
    freq  = request.POST.get('frequency', 'daily')
    if not name:
        messages.error(request, 'Name required.'); return redirect('pipeline:list')
    source = DataSource.objects.create(
        user=request.user, name=name, source_url=url,
        source_type='url' if url else 'upload', frequency=freq,
    )
    source.next_run = _next_run(source)
    source.save(update_fields=['next_run'])
    messages.success(request, f'Pipeline "{name}" created.')
    return redirect('pipeline:list')


@login_required
@require_POST
def run_now(request, pk):
    source = get_object_or_404(DataSource, pk=pk, user=request.user)
    try:
        run_pipeline(source.id)
        messages.success(request, f'Pipeline "{source.name}" ran successfully.')
    except Exception as e:
        messages.error(request, f'Run failed: {e}')
    return redirect('pipeline:list')


@login_required
@require_POST
def toggle_source(request, pk):
    source = get_object_or_404(DataSource, pk=pk, user=request.user)
    source.is_active = not source.is_active
    source.save(update_fields=['is_active'])
    return redirect('pipeline:list')


@login_required
@require_POST
def delete_source(request, pk):
    get_object_or_404(DataSource, pk=pk, user=request.user).delete()
    messages.success(request, 'Pipeline deleted.')
    return redirect('pipeline:list')
