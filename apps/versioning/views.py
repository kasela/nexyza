from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from apps.analyser.models import FileUpload
from .models import DataSnapshot
from .engine import create_snapshot


@login_required
def version_history(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    snapshots = DataSnapshot.objects.filter(upload=upload).order_by('-version')
    return render(request, 'versioning/history.html', {'upload': upload, 'snapshots': snapshots})


@login_required
@require_POST
def save_snapshot(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    label  = request.POST.get('label', '')
    snap   = create_snapshot(upload, label=label, triggered_by='manual')
    messages.success(request, f'Snapshot v{snap.version} saved.')
    return redirect('versioning:history', pk=pk)


@login_required
def view_diff(request, pk, v1, v2):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    snap1  = get_object_or_404(DataSnapshot, upload=upload, version=v1)
    snap2  = get_object_or_404(DataSnapshot, upload=upload, version=v2)
    from .engine import compute_diff
    raw_diff = compute_diff(snap1.analysis, snap2.analysis)
    # Enrich for template
    changed_cols = []
    for ch in raw_diff.get('changed', []):
        mean_ch = ch['changes'].get('mean', {})
        changed_cols.append({
            'name':     ch['name'],
            'old_mean': round(float(mean_ch['old']), 4) if mean_ch.get('old') is not None else None,
            'new_mean': round(float(mean_ch['new']), 4) if mean_ch.get('new') is not None else None,
            'delta':    round(float(mean_ch['new']) - float(mean_ch['old']), 4)
                        if mean_ch.get('old') is not None and mean_ch.get('new') is not None else None,
        })
    diff = {
        'row_delta':    raw_diff['rows_new'] - raw_diff['rows_old'],
        'col_delta':    raw_diff['cols_new'] - raw_diff['cols_old'],
        'added':        raw_diff['added'],
        'removed':      raw_diff['removed'],
        'changed_cols': changed_cols,
    }
    return render(request, 'versioning/diff.html', {
        'upload': upload, 'snap1': snap1, 'snap2': snap2, 'diff': diff,
    })


@login_required
@require_POST
def restore_snapshot(request, pk, version):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    snap   = get_object_or_404(DataSnapshot, upload=upload, version=version)
    # Save current state before restoring
    create_snapshot(upload, label='Before restore', triggered_by='restore')
    upload.analysis_result = snap.analysis
    upload.row_count = snap.row_count
    upload.column_count = snap.column_count
    upload.save(update_fields=['analysis_result', 'row_count', 'column_count'])
    messages.success(request, f'Restored to v{version}.')
    return redirect('analyser:result', pk=pk)
