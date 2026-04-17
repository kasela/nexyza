"""Snapshot creation and diff computation."""
from django.conf import settings


def create_snapshot(upload, label='', triggered_by='manual') -> 'DataSnapshot':
    from .models import DataSnapshot

    max_snaps = getattr(settings, 'VERSIONING_MAX_SNAPSHOTS', 50)
    existing = DataSnapshot.objects.filter(upload=upload)

    # Prune oldest if over limit
    if existing.count() >= max_snaps:
        oldest = existing.order_by('version').first()
        if oldest:
            oldest.delete()

    last = existing.order_by('-version').first()
    version = (last.version + 1) if last else 1

    # Compute diff
    diff = None
    if last:
        diff = compute_diff(last.analysis, upload.analysis_result or {})

    snap = DataSnapshot.objects.create(
        upload=upload,
        version=version,
        label=label,
        analysis=upload.analysis_result or {},
        row_count=upload.row_count,
        column_count=upload.column_count,
        diff_from_prev=diff,
        triggered_by=triggered_by,
    )
    return snap


def compute_diff(old_analysis: dict, new_analysis: dict) -> dict:
    """Compute column-level diffs between two analysis snapshots."""
    old_cols = {c['name']: c for c in old_analysis.get('columns', [])}
    new_cols = {c['name']: c for c in new_analysis.get('columns', [])}
    old_names = set(old_cols)
    new_names = set(new_cols)

    added    = sorted(new_names - old_names)
    removed  = sorted(old_names - new_names)
    changed  = []

    for name in old_names & new_names:
        oc, nc = old_cols[name], new_cols[name]
        col_changes = {}
        for field in ('mean', 'min', 'max', 'null_pct', 'unique_count'):
            ov, nv = oc.get(field), nc.get(field)
            if ov is not None and nv is not None and ov != nv:
                try:
                    pct = round((float(nv) - float(ov)) / abs(float(ov)) * 100, 1) if float(ov) != 0 else None
                except (TypeError, ZeroDivisionError):
                    pct = None
                col_changes[field] = {'old': ov, 'new': nv, 'pct_change': pct}
        if col_changes:
            changed.append({'name': name, 'changes': col_changes})

    return {
        'rows_old':    old_analysis.get('rows', 0),
        'rows_new':    new_analysis.get('rows', 0),
        'cols_old':    old_analysis.get('cols', 0),
        'cols_new':    new_analysis.get('cols', 0),
        'added':       added,
        'removed':     removed,
        'changed':     changed,
    }
