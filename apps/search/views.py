from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.db.models import Q
from django.shortcuts import render
from apps.analyser.models import FileUpload
from apps.analyser.models import ChartConfig


@login_required
def search(request):
    q = request.GET.get('q', '').strip()
    fmt = request.GET.get('fmt', 'html')

    if len(q) < 2:
        if fmt == 'json':
            return JsonResponse({'results': [], 'query': q})
        return render(request, 'search/results.html', {'results': [], 'query': q, 'groups': {}})

    results = []

    # ── Files ─────────────────────────────────────────────────────────────────
    uploads = FileUpload.objects.filter(
        user=request.user, status='done'
    ).filter(
        Q(original_name__icontains=q) |
        Q(ai_insights__icontains=q) |
        Q(label__icontains=q)
    )[:20]

    for u in uploads:
        # Also search column names in analysis_result
        col_match = False
        if u.analysis_result:
            cols = [c['name'].lower() for c in u.analysis_result.get('columns', [])]
            col_match = any(q.lower() in c for c in cols)

        snippet = ''
        if u.ai_insights and q.lower() in u.ai_insights.lower():
            idx = u.ai_insights.lower().find(q.lower())
            start = max(0, idx - 60)
            snippet = '…' + u.ai_insights[start:idx + 80] + '…'

        results.append({
            'type': 'file',
            'title': u.original_name,
            'subtitle': f"{u.row_count:,} rows · {u.column_count} cols · {u.file_type.upper()}",
            'snippet': snippet,
            'url': f'/workspace/{u.id}/',
            'icon': '📊' if u.file_type == 'csv' else ('📗' if u.file_type == 'excel' else '🔷'),
            'id': u.id,
            'col_match': col_match,
        })

    # ── Charts ────────────────────────────────────────────────────────────────
    charts = ChartConfig.objects.filter(
        upload__user=request.user
    ).filter(
        Q(title__icontains=q) |
        Q(x_axis__icontains=q) |
        Q(y_axis__icontains=q)
    ).select_related('upload')[:10]

    for c in charts:
        results.append({
            'type': 'chart',
            'title': c.title,
            'subtitle': f"{c.chart_type} · {c.upload.original_name}",
            'snippet': '',
            'url': f'/workspace/{c.upload_id}/charts/',
            'icon': '📈',
            'id': c.id,
        })

    # ── Column search ─────────────────────────────────────────────────────────
    # Find uploads where a column name matches the query
    col_uploads = []
    for u in FileUpload.objects.filter(user=request.user, status='done').exclude(id__in=[r['id'] for r in results if r['type']=='file'])[:100]:
        if not u.analysis_result:
            continue
        matching_cols = [c['name'] for c in u.analysis_result.get('columns', []) if q.lower() in c['name'].lower()]
        if matching_cols:
            col_uploads.append({
                'type': 'column',
                'title': f'Column "{matching_cols[0]}" in {u.original_name}',
                'subtitle': f"{', '.join(matching_cols[:3])} · {u.row_count:,} rows",
                'snippet': '',
                'url': f'/workspace/{u.id}/',
                'icon': '🔍',
                'id': u.id,
            })
    results.extend(col_uploads[:5])

    # ── NLQ question history ──────────────────────────────────────────────────
    try:
        from apps.nlq.models import NLQHistory
        nlqs = NLQHistory.objects.filter(
            upload__user=request.user
        ).filter(
            Q(question__icontains=q) | Q(answer__icontains=q)
        ).select_related('upload')[:5]
        for n in nlqs:
            results.append({
                'type':     'nlq',
                'title':    n.question[:80],
                'subtitle': f'NLQ · {n.upload.original_name}',
                'snippet':  n.answer[:120] if n.answer else '',
                'url':      f'/workspace/{n.upload_id}/',
                'icon':     '💬',
                'id':       n.id,
            })
    except Exception:
        pass

    # ── Reports ───────────────────────────────────────────────────────────────
    try:
        from apps.reportbuilder.models import Report
        reports = Report.objects.filter(user=request.user).filter(
            Q(title__icontains=q)
        )[:5]
        for r in reports:
            results.append({
                'type':     'report',
                'title':    r.title,
                'subtitle': f'Report · {r.sections.count()} sections',
                'snippet':  '',
                'url':      f'/reports/builder/{r.id}/',
                'icon':     '📑',
                'id':       r.id,
            })
    except Exception:
        pass

    # ── Catalog assets ────────────────────────────────────────────────────────
    try:
        from apps.catalog.models import DataAsset
        assets = DataAsset.objects.filter(owner=request.user).filter(
            Q(name__icontains=q) |
            Q(description__icontains=q) |
            Q(tags__icontains=q) |
            Q(domain__icontains=q)
        )[:5]
        for a in assets:
            results.append({
                'type':     'catalog',
                'title':    a.name,
                'subtitle': f'Catalog · {a.domain or a.get_source_type_display()}',
                'snippet':  a.description[:100] if a.description else '',
                'url':      f'/catalog/{a.id}/',
                'icon':     '📚',
                'id':       a.id,
            })
    except Exception:
        pass

    if fmt == 'json':
        return JsonResponse({'results': results, 'query': q, 'total': len(results)})

    # Group by type for HTML view
    type_labels = {
        'file':    '📊 Files',
        'chart':   '📈 Charts',
        'column':  '🔍 Columns',
        'nlq':     '💬 NLQ History',
        'report':  '📑 Reports',
        'catalog': '📚 Catalog',
    }
    groups = {}
    for r in results:
        groups.setdefault(r['type'], []).append(r)

    if request.htmx:
        from django.template.loader import render_to_string
        return HttpResponse(render_to_string('search/dropdown.html',
                            {'results': results[:8], 'query': q}, request=request))

    return render(request, 'search/results.html', {
        'results':      results,
        'groups':       groups,
        'type_labels':  type_labels,
        'query':        q,
        'total':        len(results),
    })
