import json
from uuid import UUID

import pandas as pd
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils.text import slugify
from django.views.decorators.http import require_GET, require_POST

from .analysis_intents import infer_analysis_intents
from .derived_metrics import add_derived_metrics
from .drilldown import build_drilldown
from .engine import load_dataframe
from .filter_state import normalise_filter_state
from .models import AnalysisView, ChartConfig, FileUpload
from .charts import auto_generate_charts, build_chart_data
from .benchmarks import build_benchmark_summary, build_benchmark_suite
from .alerts import build_alerts
from .scenarios import build_scenario_result
from .services.alert_service import enrich_alerts_with_forecast
from .services.forecast_service import build_forecast_summary
from .dashboard_layout_engine import build_dashboard_layout
from .time_intelligence_engine import build_time_intelligence


@login_required
def analysis_studio(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    analysis = upload.analysis_result or {}
    cols = analysis.get('columns', [])
    semantic_map = {c['name']: c.get('semantic_type', 'text') for c in cols}

    derived_metrics = []
    time_intelligence = {}
    intents = infer_analysis_intents(None, semantic_map).to_dict()

    try:
        df = load_dataframe(upload.file.path, upload.file_type, sheet_name=upload.active_sheet or None)
        _df, derived_metrics = add_derived_metrics(df)
        profile = (analysis or {}).get('profile_json') or {}
        measures = profile.get('measures') or []
        time_cols = profile.get('time_columns') or []
        if measures:
            time_intelligence = build_time_intelligence(
                _df if _df is not None else df,
                measures[0],
                profile=profile,
                year_col=('Year' if 'Year' in df.columns else ''),
                period_col=(time_cols[0] if time_cols else ''),
            )
    except Exception:
        derived_metrics = []

    analysis['time_intelligence'] = time_intelligence

    charts = upload.chart_configs.all().order_by('sort_order', 'created_at')
    if not charts.exists() and upload.status == FileUpload.STATUS_DONE:
        auto_generate_charts(upload)
        analysis['time_intelligence'] = time_intelligence

    charts = upload.chart_configs.all().order_by('sort_order', 'created_at')

    combined_dates = analysis.get('combined_dates', [])
    combined_date_names = [c.get('display_name') or c.get('name') for c in combined_dates if c.get('display_name') or c.get('name')]
    target_candidates = [c['name'] for c in cols if 'target' in c['name'].lower() or 'budget' in c['name'].lower() or 'plan' in c['name'].lower()]
    numeric_columns = [c['name'] for c in cols if c.get('is_numeric') or c.get('semantic_type') in {'metric','currency','count','ratio','percentage'}]
    category_columns = [c['name'] for c in cols if c.get('semantic_type') in {'category','high_card'}]
    date_candidates = combined_date_names + [c['name'] for c in cols if c.get('semantic_type') in {'date', 'datetime', 'month', 'year', 'time_cat'} or 'date' in c['name'].lower() or 'month' in c['name'].lower() or 'period' in c['name'].lower()]
    dimension_candidates = combined_date_names + [c['name'] for c in cols if c.get('semantic_type') in {'category','date','year','month','time_cat'}]
    saved_views = upload.analysis_views.filter(user=request.user).order_by('-updated_at')

    default_chart = charts.first()

    profile_json = (analysis.get('profile_json') or {})
    dashboard_layout = build_dashboard_layout(charts, profile_json)

    forecast_summary = None
    benchmark_summary = None
    alerts = []
    scenario_result = None
    primary_metric = numeric_columns[0] if numeric_columns else None
    date_column = date_candidates[0] if date_candidates else ''
    target_column = target_candidates[0] if target_candidates else None
    if primary_metric:
        try:
            df = load_dataframe(upload.file.path, upload.file_type, sheet_name=upload.active_sheet or None)
            benchmark_bundle = build_benchmark_suite(df, primary_metric, time_column='Year' if 'Year' in df.columns else '', period_column=date_column, target_column=target_column or '', group_column=(category_columns[0] if category_columns else ''))
            preferred_mode = benchmark_bundle.get('preferred_mode') or 'average'
            benchmark_summary = build_benchmark_summary(df, primary_metric, mode=preferred_mode, time_column='Year' if 'Year' in df.columns else '', period_column=date_column, target_column=target_column or '', group_column=(category_columns[0] if category_columns else '')).to_dict()
            benchmark_summary['suite'] = benchmark_bundle.get('benchmarks') or {}
            alerts = build_alerts(df, primary_metric, target=target_column, benchmark_value=benchmark_summary.get('benchmark_value'))
            alerts, forecast_summary = enrich_alerts_with_forecast(alerts, upload, date_column=date_column, metric=primary_metric)
            base_value = benchmark_summary.get('current_value') or 0
            scenario_result = build_scenario_result(base_value=base_value, growth_pct=8.0, cost_pct=2.0, target_override=(benchmark_summary.get('benchmark_value') or 0))
        except Exception:
            pass
    default_chart_payload = {
        'id': str(default_chart.id),
        'title': default_chart.title,
        'chart_type': default_chart.chart_type,
        'aggregation': default_chart.aggregation,
        'size': default_chart.size,
        'x_axis': default_chart.x_axis,
        'y_axis': default_chart.y_axis,
        'group_by': default_chart.group_by,
    } if default_chart else None

    return render(request, 'analyser/analysis_studio.html', {
        'upload': upload,
        'analysis': analysis,
        'charts': charts,
        'intents': intents,
        'derived_metrics': derived_metrics,
        'target_candidates': target_candidates,
        'numeric_columns': numeric_columns,
        'category_columns': category_columns,
        'date_candidates': date_candidates,
        'dimension_candidates': dimension_candidates,
        'combined_date_names': combined_date_names,
        'target_candidates': target_candidates,
        'saved_views': saved_views,
        'default_chart_payload': default_chart_payload,
        'chart_type_choices': ChartConfig.CHART_TYPES,
        'color_choices': ChartConfig.COLOR_PALETTES,
        'size_choices': ChartConfig.SIZE_CHOICES,
        'agg_choices': ChartConfig.AGG_CHOICES,
        'forecast_summary': forecast_summary,
        'benchmark_summary': benchmark_summary,
        'alerts': alerts,
        'scenario_result': scenario_result,
        'primary_metric': primary_metric,
        'date_column': date_column,
        'comparison_modes': [
            ('', 'No comparison'),
            ('previous_period', 'Previous period'),
            ('target', 'Actual vs target'),
            ('segment_compare', 'Segment compare'),
            ('benchmark', 'Benchmark'),
        ],
        'dashboard_layout': dashboard_layout,
    })


@login_required
def board_report(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    analysis = upload.analysis_result or {}
    charts = list(upload.chart_configs.all().order_by('sort_order', 'created_at')[:12])
    profile_json = analysis.get('profile_json') or {}
    dashboard_layout = build_dashboard_layout(charts, profile_json)
    analysis_type = ((profile_json.get('analysis_classification') or {}).get('analysis_type') or analysis.get('analysis_type') or '').replace('_', ' ').strip()
    section_count = len(dashboard_layout.get('sections') or [])
    chart_count = len(charts)
    board_meta = {
        'analysis_type': analysis_type.title() if analysis_type else 'Board-ready dashboard',
        'section_count': section_count,
        'chart_count': chart_count,
        'row_count': profile_json.get('row_count') or upload.row_count,
        'column_count': profile_json.get('column_count') or upload.column_count,
        'primary_dimension': ((profile_json.get('analysis_classification') or {}).get('primary_dimension') or ''),
        'primary_measure': ((profile_json.get('analysis_classification') or {}).get('primary_measure') or ''),
        'secondary_measure': ((profile_json.get('analysis_classification') or {}).get('secondary_measure') or ''),
    }
    return render(request, 'analyser/board_report.html', {
        'upload': upload,
        'charts': charts,
        'analysis': analysis,
        'dashboard_layout': dashboard_layout,
        'board_meta': board_meta,
    })


@login_required
@require_POST
def save_analysis_view(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    payload = json.loads(request.body or '{}')
    title = (payload.get('title') or 'Untitled view').strip()[:120]
    obj, _ = AnalysisView.objects.update_or_create(
        upload=upload,
        user=request.user,
        title=title,
        defaults={
            'slug': slugify(title)[:140],
            'description': (payload.get('description') or '')[:500],
            'view_type': payload.get('view_type') or 'studio',
            'filters_json': payload.get('filters') or {},
            'kpi_config_json': payload.get('kpi_config') or {},
            'chart_order_json': payload.get('chart_order') or [],
            'layout_json': payload.get('layout') or {},
            'drill_state_json': payload.get('drill_state') or {},
            'selected_metrics_json': payload.get('selected_metrics') or [],
            'comparison_mode': payload.get('comparison_mode') or '',
            'is_default': bool(payload.get('is_default')),
        },
    )
    if obj.is_default:
        upload.analysis_views.exclude(pk=obj.pk).filter(user=request.user).update(is_default=False)
    return JsonResponse({
        'ok': True,
        'view': {
            'id': str(obj.id),
            'title': obj.title,
            'is_default': obj.is_default,
            'comparison_mode': obj.comparison_mode,
        }
    })


@login_required
@require_GET
def load_analysis_view(request, pk, view_id):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    view = get_object_or_404(AnalysisView, pk=view_id, upload=upload, user=request.user)
    return JsonResponse({
        'ok': True,
        'view': {
            'id': str(view.id),
            'title': view.title,
            'description': view.description,
            'filters': view.filters_json,
            'kpi_config': view.kpi_config_json,
            'chart_order': view.chart_order_json,
            'layout': view.layout_json,
            'drill_state': view.drill_state_json,
            'selected_metrics': view.selected_metrics_json,
            'comparison_mode': view.comparison_mode,
            'is_default': view.is_default,
        }
    })


@login_required
@require_POST
def delete_analysis_view(request, pk, view_id):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    view = get_object_or_404(AnalysisView, pk=view_id, upload=upload, user=request.user)
    view.delete()
    return JsonResponse({'ok': True})


@login_required
@require_POST
def cross_filter(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    payload = json.loads(request.body or '{}')
    state = normalise_filter_state(payload)
    df = load_dataframe(upload.file.path, upload.file_type, sheet_name=upload.active_sheet or None)
    original_rows = len(df)

    if state.dimension and state.dimension in df.columns and state.value:
        mask = df[state.dimension].astype(str) == state.value
        df = df.loc[mask].copy()

    numeric_cols = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    category_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
    primary_metric = numeric_cols[0] if numeric_cols else ''
    total_value = float(df[primary_metric].sum()) if primary_metric else float(len(df))

    top_dimension = ''
    top_labels = []
    if category_cols:
        top_dimension = state.dimension or category_cols[0]
        if top_dimension in df.columns:
            top_series = df[top_dimension].astype(str).value_counts().head(state.top_n)
            top_labels = top_series.index.tolist()

    impacted_ids = []
    for chart in upload.chart_configs.all():
        if state.dimension and chart.x_axis == state.dimension:
            impacted_ids.append(str(chart.id))

    return JsonResponse({
        'ok': True,
        'summary': {
            'rows_before': original_rows,
            'rows_after': int(len(df)),
            'primary_metric': primary_metric,
            'primary_value': round(total_value, 2),
            'top_dimension': top_dimension,
            'top_labels': top_labels,
        },
        'state': state.to_dict(),
        'impacted_chart_ids': impacted_ids,
    })


@login_required
@require_POST
def drilldown_data(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    payload = json.loads(request.body or '{}')
    df = load_dataframe(upload.file.path, upload.file_type, sheet_name=upload.active_sheet or None)

    parent_dimension = payload.get('parent_dimension') or ''
    parent_value = payload.get('parent_value') or ''
    if parent_dimension and parent_dimension in df.columns and parent_value:
        df = df.loc[df[parent_dimension].astype(str) == str(parent_value)].copy()

    metric = payload.get('metric') or ''
    aggregation = payload.get('aggregation') or 'sum'
    dimension = payload.get('dimension') or ''
    result = build_drilldown(df, dimension=dimension, metric=metric, aggregation=aggregation, limit=int(payload.get('limit', 12) or 12))
    result.update({
        'ok': True,
        'dimension': dimension,
        'metric': metric,
        'aggregation': aggregation,
        'parent_dimension': parent_dimension,
        'parent_value': parent_value,
    })
    return JsonResponse(result)


@login_required
@require_POST
def update_chart_inspector(request, pk, chart_id):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    chart = get_object_or_404(ChartConfig, pk=chart_id, upload=upload)
    payload = json.loads(request.body or '{}')

    for field in ['title', 'chart_type', 'aggregation', 'size', 'x_axis', 'y_axis', 'group_by', 'color']:
        if field in payload and payload[field] is not None:
            setattr(chart, field, str(payload[field]))

    config = dict(chart.config_json or {})
    for key in ['comparison_mode', 'rolling_window', 'top_n', 'show_annotations', 'target_column', 'benchmark_column']:
        if key in payload:
            config[key] = payload[key]
    chart.config_json = config
    chart.cached_data = build_chart_data(upload, chart)
    chart.save(update_fields=['title', 'chart_type', 'aggregation', 'size', 'x_axis', 'y_axis', 'group_by', 'color', 'config_json', 'cached_data', 'updated_at'])

    return JsonResponse({
        'ok': True,
        'chart': {
            'id': str(chart.id),
            'title': chart.title,
            'chart_type': chart.chart_type,
            'aggregation': chart.aggregation,
            'size': chart.size,
            'color': chart.color,
            'x_axis': chart.x_axis,
            'y_axis': chart.y_axis,
            'group_by': chart.group_by,
            'config_json': chart.config_json,
            'cached_data': chart.cached_data,
        }
    })


@login_required
def forecast_workspace(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    analysis = upload.analysis_result or {}
    cols = analysis.get('columns', [])
    numeric_columns = [c['name'] for c in cols if c.get('is_numeric')]
    date_candidates = [c['name'] for c in cols if c.get('semantic_type') in {'date', 'datetime', 'month', 'year'} or 'date' in c['name'].lower() or 'month' in c['name'].lower()]
    metric = request.GET.get('metric') or (numeric_columns[0] if numeric_columns else '')
    date_column = request.GET.get('date_column') or (date_candidates[0] if date_candidates else '')
    method = request.GET.get('method') or 'linear'
    periods = int(request.GET.get('periods') or 6)
    forecast_bundle = None
    benchmark_summary = None
    alerts = []
    scenario_result = None
    if metric and date_column:
        try:
            forecast_bundle = build_forecast_summary(upload, date_column=date_column, metric=metric, periods=periods, method=method)
        except Exception:
            forecast_bundle = None
    try:
        df = load_dataframe(upload.file.path, upload.file_type, sheet_name=upload.active_sheet or None)
        if metric:
            benchmark_mode = request.GET.get('benchmark') or 'average'
            benchmark_summary = build_benchmark_summary(df, metric, mode=benchmark_mode, time_column='Year' if 'Year' in df.columns else '', period_column=date_column, target_column=request.GET.get('target_column') or '', group_column=request.GET.get('group_by') or '').to_dict()
            benchmark_summary['suite'] = build_benchmark_suite(df, metric, time_column='Year' if 'Year' in df.columns else '', period_column=date_column, target_column=request.GET.get('target_column') or '', group_column=request.GET.get('group_by') or '').get('benchmarks') or {}
            alerts = build_alerts(df, metric, target=None, benchmark_value=(benchmark_summary or {}).get('benchmark_value'))
            scenario_result = build_scenario_result(base_value=(benchmark_summary or {}).get('current_value') or 0, growth_pct=float(request.GET.get('growth_pct') or 8), cost_pct=float(request.GET.get('cost_pct') or 2), target_override=(benchmark_summary or {}).get('benchmark_value'))
    except Exception:
        pass
    return render(request, 'analyser/forecast_workspace.html', {
        'upload': upload,
        'analysis': analysis,
        'numeric_columns': numeric_columns,
        'date_candidates': date_candidates,
        'metric': metric,
        'date_column': date_column,
        'method': method,
        'periods': periods,
        'forecast_bundle': forecast_bundle,
        'benchmark_summary': benchmark_summary,
        'alerts': alerts,
        'scenario_result': scenario_result,
    })


@login_required
@require_POST
def scenario_preview(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    payload = json.loads(request.body or '{}')
    base_value = float(payload.get('base_value') or 0)
    growth_pct = float(payload.get('growth_pct') or 0)
    cost_pct = float(payload.get('cost_pct') or 0)
    target_override = payload.get('target_override')
    target_override = float(target_override) if target_override not in (None, '', False) else None
    result = build_scenario_result(base_value=base_value, growth_pct=growth_pct, cost_pct=cost_pct, target_override=target_override)
    return JsonResponse({'ok': True, 'scenario': result, 'upload_id': str(upload.id)})
