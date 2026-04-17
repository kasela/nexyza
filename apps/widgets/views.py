import json
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from apps.analyser.models import FileUpload, ChartConfig
from .models import DashboardWidget


@login_required
def widget_board(request):
    """Full-screen widget dashboard."""
    widgets = DashboardWidget.objects.filter(user=request.user, is_visible=True)
    uploads = FileUpload.objects.filter(user=request.user, status='done')
    charts  = ChartConfig.objects.filter(upload__user=request.user).select_related('upload')
    return render(request, 'widgets/board.html', {
        'widgets': widgets,
        'uploads': uploads,
        'charts': charts,
        'widget_types': DashboardWidget.WIDGET_TYPES,
        'size_choices': DashboardWidget.SIZE_CHOICES,
    })


@login_required
@require_POST
def add_widget(request):
    last = DashboardWidget.objects.filter(user=request.user).order_by('-sort_order').first()
    config = {}
    wtype = request.POST.get('widget_type', 'chart')
    if wtype == 'kpi':
        config = {'column': request.POST.get('column',''), 'metric': request.POST.get('metric','mean')}
    elif wtype == 'text':
        config = {'content': request.POST.get('content','')}

    upload_id = request.POST.get('upload_id')
    chart_id  = request.POST.get('chart_id')
    upload = FileUpload.objects.filter(pk=upload_id, user=request.user).first() if upload_id else None
    chart  = ChartConfig.objects.filter(pk=chart_id, upload__user=request.user).first() if chart_id else None

    DashboardWidget.objects.create(
        user=request.user,
        title=request.POST.get('title', 'Widget'),
        widget_type=wtype,
        size=request.POST.get('size', '2x1'),
        sort_order=(last.sort_order + 1) if last else 0,
        upload=upload, chart_config=chart,
        config=config,
        refresh_mins=int(request.POST.get('refresh_mins', 0)),
    )
    messages.success(request, 'Widget added.')
    return redirect('widgets:board')


@login_required
@require_POST
def delete_widget(request, pk):
    get_object_or_404(DashboardWidget, pk=pk, user=request.user).delete()
    if request.htmx:
        return HttpResponse('')
    return redirect('widgets:board')


@login_required
@require_POST
def reorder_widgets(request):
    try:
        order = json.loads(request.body).get('order', [])
        for i, wid in enumerate(order):
            DashboardWidget.objects.filter(pk=wid, user=request.user).update(sort_order=i)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'ok': True})


@login_required
def widget_data(request, pk):
    """Return live data for a widget (used by auto-refresh)."""
    w = get_object_or_404(DashboardWidget, pk=pk, user=request.user)
    if w.widget_type == 'chart' and w.chart_config:
        from apps.analyser.charts import build_chart_data
        data = build_chart_data(w.upload, w.chart_config)
        return JsonResponse(data)
    if w.widget_type == 'kpi' and w.upload:
        analysis = w.upload.analysis_result or {}
        col_name = w.config.get('column','')
        metric   = w.config.get('metric','mean')
        col = next((c for c in analysis.get('columns',[]) if c['name']==col_name), None)
        val = col.get(metric) if col else None
        return JsonResponse({'value': val, 'column': col_name, 'metric': metric})
    return JsonResponse({'error': 'No data'}, status=404)
