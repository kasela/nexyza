"""
All chart-related views: auto-gen, gallery, CRUD, data API, drag-reorder.
"""
import json
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST, require_GET
from django.contrib import messages
from django.views.decorators.csrf import csrf_exempt

from .models import FileUpload, ChartConfig
from .charts import build_chart_data, auto_generate_charts
from .chart_services import (
    ChartPayloadError,
    build_preview_data,
    create_chart_from_post,
    error_payload,
    update_chart_from_post,
)
from .engine import load_dataframe
from .executive_summary import build_executive_summary
from .decision_intelligence_engine import build_decision_dashboard
from .insight_explanation_engine import attach_explanations
from .metric_type_rendering_engine import attach_metric_rendering
from .chart_confidence_engine import attach_confidence
from .governance_audit_engine import attach_governance, build_dashboard_audit_meta
from .chart_curation_engine import curate_dashboard_charts
from .ai_policy import get_ai_access_context
from .gallery_ui import build_share_ui, decorate_narrative_dashboard
from .benchmarks import build_benchmark_suite, build_benchmark_summary
from .time_intelligence_engine import build_time_intelligence
from .dashboard_memory_engine import build_dashboard_memory, apply_memory_to_analysis
from .premium_presentation_engine import build_presentation_polish
from .scenario_simulation_engine import build_scenario_state, build_scenario_context, available_segment_values
from apps.collaboration.models import CollabComment, CollabAction
from .connector_models import ScheduledAnalyticsRun, AnalysisSnapshot
from .scheduled_delivery_engine import normalize_recipients, schedule_next_run


# ── Chart Gallery (main page) ─────────────────────────────────────────────────

@login_required
def chart_gallery(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    charts = upload.chart_configs.all().order_by('sort_order', 'created_at')
    analysis = upload.analysis_result or {}
    cols = analysis.get('columns', [])

    # Auto-generate rule-based charts on first visit (no AI call here)
    if not charts.exists() and upload.status == FileUpload.STATUS_DONE:
        from .charts import _rule_based
        _rule_based(upload)
        charts = upload.chart_configs.all().order_by('sort_order', 'created_at')

    # Semantic repair pass: if a target-vs-actual dataset is missing critical views,
    # rebuild auto charts so KPI, variance, and ranking visuals reach the gallery.
    profile = (analysis.get('profile_json') or {}) if isinstance(analysis, dict) else {}
    semantics = (profile.get('business_semantics') or {}) if isinstance(profile, dict) else {}
    primary_archetype = (semantics.get('primary_archetype') or '').strip().lower()
    if charts.exists() and upload.status == FileUpload.STATUS_DONE and primary_archetype == 'target_vs_actual':
        auto_charts = charts.filter(is_auto=True)
        available_types = set(auto_charts.values_list('chart_type', flat=True))
        has_kpi = 'kpi' in available_types
        has_variance = 'variance_bar' in available_types or 'bullet' in available_types or 'progress_ring' in available_types
        has_ranking = 'horizontal_bar' in available_types or 'bar' in available_types
        needs_repair = (not has_kpi) or (not has_variance) or (not has_ranking)
        if needs_repair:
            from .charts import _rule_based
            _rule_based(upload)
            charts = upload.chart_configs.all().order_by('sort_order', 'created_at')

    executive_summary = build_executive_summary(analysis, chart_count=charts.count())
    benchmark_summary = {}
    scenario_context = {}
    scenario_options = {'dimensions': [], 'selected_dimension': '', 'values': []}
    try:
        profile = analysis.get('profile_json') or {}
        measures = profile.get('measures') or []
        time_cols = profile.get('time_columns') or []
        target_cols = profile.get('target_columns') or []
        dims = profile.get('dimensions') or []
        if measures:
            df = load_dataframe(upload.file.path, upload.file_type, sheet_name=upload.active_sheet or None)
            scenario_state = build_scenario_state(request, upload, analysis)
            scenario_options = available_segment_values(df, scenario_state, profile)
            scenario_context = build_scenario_context(df, scenario_state, profile)
            scenario_df = df
            if scenario_context.get('active'):
                from .scenario_simulation_engine import apply_scenario_to_df
                scenario_df = apply_scenario_to_df(df, scenario_state, profile)
            suite = build_benchmark_suite(scenario_df, measures[0], time_column=('Year' if 'Year' in scenario_df.columns else ''), period_column=(time_cols[0] if time_cols else ''), target_column=(target_cols[0] if target_cols else ''), group_column=(dims[0] if dims else ''))
            preferred = suite.get('preferred_mode') or 'average'
            benchmark_summary = build_benchmark_summary(scenario_df, measures[0], mode=preferred, time_column=('Year' if 'Year' in scenario_df.columns else ''), period_column=(time_cols[0] if time_cols else ''), target_column=(target_cols[0] if target_cols else ''), group_column=(dims[0] if dims else '')).to_dict()
            benchmark_summary['suite'] = suite.get('benchmarks') or {}
            analysis['benchmark_summary'] = benchmark_summary
            time_metric = measures[0]
            analysis['time_intelligence'] = build_time_intelligence(
                scenario_df,
                time_metric,
                profile=profile,
                year_col=('Year' if 'Year' in scenario_df.columns else ''),
                period_col=(time_cols[0] if time_cols else ''),
            )
            analysis['scenario_context'] = scenario_context
    except Exception:
        benchmark_summary = {}
    dashboard_memory = build_dashboard_memory(upload, analysis, request=request)
    analysis = apply_memory_to_analysis(analysis, dashboard_memory)
    _url_mode = request.GET.get('mode', '').strip().lower()
    dashboard_mode = _url_mode if _url_mode in ('executive', 'explorer', 'board', 'ops', 'analysis') else (dashboard_memory.get('mode') or 'executive').strip().lower()
    all_charts = [chart for chart in charts if not (isinstance(getattr(chart, 'cached_data', None), dict) and chart.cached_data.get('error'))]
    attach_metric_rendering(all_charts, analysis)
    attach_explanations(all_charts, analysis)
    attach_confidence(all_charts, analysis)
    attach_governance(all_charts, analysis)

    curated = curate_dashboard_charts(all_charts, analysis, mode=dashboard_mode)
    chart_list = curated.visible
    narrative_dashboard = build_decision_dashboard(analysis, chart_list, mode=dashboard_mode)
    narrative_dashboard['curation_summary'] = curated.summary
    narrative_dashboard['suppressed_count'] = max(
        int(narrative_dashboard.get('suppressed_count') or 0),
        int(curated.summary.get('suppressed_count') or 0),
    )

    presentation_polish = build_presentation_polish(upload, analysis, narrative_dashboard, chart_list)
    narrative_dashboard = decorate_narrative_dashboard(narrative_dashboard, presentation_polish)
    comments_list = CollabComment.objects.filter(upload=upload).select_related('author').order_by('-created_at')[:12]
    actions_list = CollabAction.objects.filter(upload=upload).select_related('creator', 'assignee').order_by('status', '-created_at')[:12]
    scheduled_delivery = ScheduledAnalyticsRun.objects.filter(upload=upload, user=request.user).order_by('-created_at').first()
    delivery_history = upload.analysis_snapshots.all()[:8]

    return render(request, 'analyser/charts/gallery.html', {
        'upload': upload,
        'charts': chart_list,
        'columns': cols,
        'executive_summary': executive_summary,
        'narrative_dashboard': narrative_dashboard,
        'dashboard_mode': dashboard_mode,
        'all_columns':      [c['name'] for c in cols],
        'numeric_columns':  [c for c in cols if c.get('is_numeric')],
        'category_columns': [c for c in cols if not c.get('is_numeric')],
        'dimension_names': ((_analysis_profile := (analysis.get('profile_json') or {})).get('dimensions') or []),
        'chart_type_choices': ChartConfig.CHART_TYPES,
        'color_choices': ChartConfig.COLOR_PALETTES,
        'size_choices': ChartConfig.SIZE_CHOICES,
        'agg_choices': ChartConfig.AGG_CHOICES,
        'benchmark_summary': benchmark_summary,
        'dashboard_memory': dashboard_memory,
        'dashboard_audit': build_dashboard_audit_meta(upload, analysis, request=request, dashboard_mode=dashboard_mode),
        'presentation_polish': presentation_polish,
        'comments_list': comments_list,
        'actions_list': actions_list,
        'scenario_context': scenario_context,
        'scenario_options': scenario_options,
        'scheduled_delivery': scheduled_delivery,
        'delivery_history': delivery_history,
        'share_ui': build_share_ui(request, upload),
    })


@login_required
@require_POST
def save_scheduled_delivery(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    cadence = (request.POST.get('cadence') or 'weekly').strip().lower()
    delivery_mode = (request.POST.get('delivery_mode') or 'email').strip().lower()
    title = (request.POST.get('title') or f"{upload.original_name} executive pack").strip()[:150]
    recipients = normalize_recipients(request.POST.get('recipients') or request.user.email)
    schedule, _ = ScheduledAnalyticsRun.objects.get_or_create(
        upload=upload,
        user=request.user,
        defaults={'title': title, 'cadence': cadence, 'delivery_mode': delivery_mode, 'recipients': recipients, 'status': 'queued'},
    )
    schedule.title = title
    schedule.cadence = cadence if cadence in {'daily','weekly','monthly'} else 'weekly'
    schedule.delivery_mode = delivery_mode if delivery_mode in {'email','in_app','none'} else 'email'
    schedule.recipients = recipients
    schedule.status = 'queued'
    schedule.last_error = ''
    if not schedule.next_run_at:
        schedule_next_run(schedule)
    schedule.save()
    messages.success(request, 'Scheduled delivery saved.')
    return redirect('analyser:chart_gallery', pk=pk)


@login_required
@require_POST
def run_scheduled_delivery_now(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    schedule = get_object_or_404(ScheduledAnalyticsRun, upload=upload, user=request.user)
    from .scheduled_delivery_engine import deliver_schedule
    try:
        deliver_schedule(schedule)
        messages.success(request, 'Scheduled report delivered successfully.')
    except Exception as e:
        schedule.status = 'error'
        schedule.last_error = str(e)[:1000]
        schedule.save(update_fields=['status','last_error','updated_at'])
        messages.error(request, f'Scheduled delivery failed: {e}')
    return redirect('analyser:chart_gallery', pk=pk)


@login_required
@require_POST
def disable_scheduled_delivery(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    ScheduledAnalyticsRun.objects.filter(upload=upload, user=request.user).delete()
    messages.success(request, 'Scheduled delivery removed.')
    return redirect('analyser:chart_gallery', pk=pk)


# ── Regenerate all auto charts ────────────────────────────────────────────────

@login_required
@require_POST
def regenerate_charts(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    created = auto_generate_charts(upload)
    messages.success(request, f'{len(created)} charts auto-generated.')
    if request.htmx:
        return _render_gallery_partial(request, upload)
    return redirect('analyser:chart_gallery', pk=pk)


# ── AI-powered regenerate (with loading state) ────────────────────────────────

@login_required
@require_POST
def ai_regenerate_charts(request, pk):
    """Regenerate charts using Claude AI recommendations."""
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)

    # Server-side pro guard — prevents direct POST abuse
    sub = getattr(request, 'subscription', None)
    if not (sub and sub.is_active):
        msg = ('🔒 AI chart generation requires a <strong>Pro plan</strong>. '
               '<a href="/billing/pricing/" class="underline font-semibold ml-1">Upgrade now →</a>')
        if request.htmx:
            return HttpResponse(
                f'<div class="col-span-full p-5 bg-amber-900/20 border border-amber-700/30 '
                f'rounded-xl text-amber-300 text-sm text-center">{msg}</div>')
        messages.warning(request, 'AI chart generation requires a Pro plan.')
        return redirect('analyser:chart_gallery', pk=pk)

    if not upload.analysis_result:
        if request.htmx:
            return HttpResponse('<p class="text-red-400 text-sm text-center py-4">No analysis data available.</p>')
        return redirect('analyser:chart_gallery', pk=pk)

    try:
        ai_ctx = get_ai_access_context(request.user, feature='chart_generation', estimated_tokens=3500)
        if not ai_ctx.get('ai_enabled'):
            notice = ai_ctx.get('message') or 'AI chart generation is unavailable.'
            if request.htmx:
                return HttpResponse(f'<div class="col-span-full p-5 bg-amber-900/20 border border-amber-700/30 rounded-xl text-amber-200 text-sm text-center">{notice}<br><span class="text-slate-400">Nexyza will keep using the manual engine until AI access is restored.</span></div>')
            messages.warning(request, notice)
            return redirect('analyser:chart_gallery', pk=pk)
        from .ai_charts import ai_recommend_charts, apply_ai_recommendations
        configs = ai_recommend_charts(upload.analysis_result, upload.original_name, user=request.user)
        created = apply_ai_recommendations(upload, configs)

        if request.htmx:
            resp = _render_gallery_partial(request, upload)
            # Inject success banner via OOB swap
            count = len(created)
            return resp
        messages.success(request, f'Claude generated {len(created)} charts tailored to your dataset.')
    except Exception as e:
        if request.htmx:
            return HttpResponse(
                f'<div class="col-span-full p-5 bg-red-900/20 border border-red-700/30 rounded-xl text-red-300 text-sm text-center">                AI chart generation failed: {e}<br><span class="text-slate-400">Try "Auto-Generate" for rule-based charts.</span></div>'
            )
        messages.error(request, f'AI generation failed: {e}')

    return redirect('analyser:chart_gallery', pk=pk)


# ── Create a new chart (HTMX form submit) ─────────────────────────────────────

@login_required
@require_POST
def create_chart(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)

    try:
        create_chart_from_post(upload, request.POST)
    except ChartPayloadError as exc:
        return JsonResponse(error_payload(exc), status=400)

    if request.htmx:
        return _render_gallery_partial(request, upload)
    return redirect('analyser:chart_gallery', pk=pk)


# ── Update chart config (inline edit) ────────────────────────────────────────

@login_required
@require_POST
def update_chart(request, pk, chart_id):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    chart  = get_object_or_404(ChartConfig, pk=chart_id, upload=upload)

    try:
        chart = update_chart_from_post(upload, chart, request.POST)
    except ChartPayloadError as exc:
        return JsonResponse(error_payload(exc), status=400)

    # Always return JSON — both modal and gallery use this
    return JsonResponse({
        'ok': True,
        'chart_type': chart.chart_type,
        'color':      chart.color,
        'size':       chart.size,
        'title':      chart.title,
    })


# ── Delete chart ──────────────────────────────────────────────────────────────

@login_required
@require_POST
def delete_chart(request, pk, chart_id):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    get_object_or_404(ChartConfig, pk=chart_id, upload=upload).delete()
    if request.htmx:
        return HttpResponse('')   # empty = remove from DOM
    return redirect('analyser:chart_gallery', pk=pk)


# ── Duplicate chart ───────────────────────────────────────────────────────────

@login_required
@require_POST
def duplicate_chart(request, pk, chart_id):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    src    = get_object_or_404(ChartConfig, pk=chart_id, upload=upload)
    last   = upload.chart_configs.order_by('-sort_order').first()

    ChartConfig.objects.create(
        upload=upload, title=f"{src.title} (copy)",
        chart_type=src.chart_type, x_axis=src.x_axis, y_axis=src.y_axis,
        group_by=src.group_by, aggregation=src.aggregation,
        color=src.color, size=src.size,
        sort_order=(last.sort_order + 1) if last else 0,
        is_auto=False, cached_data=src.cached_data,
    )
    if request.htmx:
        return _render_gallery_partial(request, upload)
    return redirect('analyser:chart_gallery', pk=pk)


# ── Reorder (drag-and-drop) ───────────────────────────────────────────────────

@login_required
@require_POST
def reorder_charts(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    try:
        order = json.loads(request.body).get('order', [])
        for i, chart_id in enumerate(order):
            ChartConfig.objects.filter(pk=chart_id, upload=upload).update(sort_order=i)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'ok': True})


# ── Live chart data API (re-render on edit) ────────────────────────────────────

@login_required
def chart_data_api(request, pk, chart_id):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    chart  = get_object_or_404(ChartConfig, pk=chart_id, upload=upload)
    data   = build_chart_data(upload, chart)
    return JsonResponse(data)


# ── Preview data for the add-chart form (live preview before saving) ──────────

@login_required
@require_POST
def preview_chart_data(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)

    try:
        data = build_preview_data(upload, request.POST)
    except ChartPayloadError as exc:
        return JsonResponse(error_payload(exc), status=400)
    return JsonResponse(data)


# ── Inline helpers ────────────────────────────────────────────────────────────

def _render_gallery_partial(request, upload):
    from django.template.loader import render_to_string
    charts  = upload.chart_configs.all().order_by('sort_order', 'created_at')
    analysis = upload.analysis_result or {}
    cols = analysis.get('columns', [])
    executive_summary = build_executive_summary(analysis, chart_count=charts.count())
    benchmark_summary = {}
    scenario_context = {}
    scenario_options = {'dimensions': [], 'selected_dimension': '', 'values': []}
    try:
        profile = analysis.get('profile_json') or {}
        measures = profile.get('measures') or []
        time_cols = profile.get('time_columns') or []
        target_cols = profile.get('target_columns') or []
        dims = profile.get('dimensions') or []
        if measures:
            df = load_dataframe(upload.file.path, upload.file_type, sheet_name=upload.active_sheet or None)
            scenario_state = build_scenario_state(request, upload, analysis)
            scenario_options = available_segment_values(df, scenario_state, profile)
            scenario_context = build_scenario_context(df, scenario_state, profile)
            scenario_df = df
            if scenario_context.get('active'):
                from .scenario_simulation_engine import apply_scenario_to_df
                scenario_df = apply_scenario_to_df(df, scenario_state, profile)
            suite = build_benchmark_suite(scenario_df, measures[0], time_column=('Year' if 'Year' in scenario_df.columns else ''), period_column=(time_cols[0] if time_cols else ''), target_column=(target_cols[0] if target_cols else ''), group_column=(dims[0] if dims else ''))
            preferred = suite.get('preferred_mode') or 'average'
            benchmark_summary = build_benchmark_summary(scenario_df, measures[0], mode=preferred, time_column=('Year' if 'Year' in scenario_df.columns else ''), period_column=(time_cols[0] if time_cols else ''), target_column=(target_cols[0] if target_cols else ''), group_column=(dims[0] if dims else '')).to_dict()
            benchmark_summary['suite'] = suite.get('benchmarks') or {}
            analysis['benchmark_summary'] = benchmark_summary
            time_metric = measures[0]
            analysis['time_intelligence'] = build_time_intelligence(
                scenario_df,
                time_metric,
                profile=profile,
                year_col=('Year' if 'Year' in scenario_df.columns else ''),
                period_col=(time_cols[0] if time_cols else ''),
            )
            analysis['scenario_context'] = scenario_context
    except Exception:
        benchmark_summary = {}
    dashboard_memory = build_dashboard_memory(upload, analysis, request=request)
    analysis = apply_memory_to_analysis(analysis, dashboard_memory)
    dashboard_mode = (request.GET.get('mode') or dashboard_memory.get('mode') or 'executive').strip().lower()
    chart_list = [chart for chart in charts if not (isinstance(getattr(chart, 'cached_data', None), dict) and chart.cached_data.get('error'))]
    attach_metric_rendering(chart_list, analysis)
    narrative_dashboard = build_decision_dashboard(analysis, chart_list, mode=dashboard_mode)
    attach_explanations(chart_list, analysis)
    attach_confidence(chart_list, analysis)
    attach_governance(chart_list, analysis)
    if dashboard_mode == 'executive':
        chart_list = [c for c in chart_list if not getattr(c, 'confidence_meta', {}).get('suppress_by_default')]
        visible_titles = {getattr(c, 'title', '') for c in chart_list}
        if narrative_dashboard.get('sections'):
            filtered_sections = []
            for section in narrative_dashboard['sections']:
                kept = [c for c in (section.get('charts') or []) if getattr(c, 'title', '') in visible_titles]
                if kept:
                    section = {**section, 'charts': kept}
                    filtered_sections.append(section)
            narrative_dashboard['sections'] = filtered_sections
            narrative_dashboard['visible_chart_count'] = sum(len(s.get('charts') or []) for s in filtered_sections)
    html = render_to_string('analyser/charts/partials/chart_grid.html', {
        'upload': upload, 'charts': charts,
        'executive_summary': executive_summary,
        'narrative_dashboard': narrative_dashboard,
        'dashboard_mode': dashboard_mode,
        'columns': cols,
        'all_columns':      [c['name'] for c in cols],
        'numeric_columns':  [c for c in cols if c.get('is_numeric')],
        'category_columns': [c for c in cols if not c.get('is_numeric')],
        'dimension_names': ((_analysis_profile := (analysis.get('profile_json') or {})).get('dimensions') or []),
        'chart_type_choices': ChartConfig.CHART_TYPES,
        'color_choices': ChartConfig.COLOR_PALETTES,
        'size_choices': ChartConfig.SIZE_CHOICES,
        'agg_choices': ChartConfig.AGG_CHOICES,
    }, request=request)
    return HttpResponse(html)


def _render_single_chart(request, upload, chart):
    from django.template.loader import render_to_string
    html = render_to_string('analyser/charts/partials/chart_card.html',
                            {'chart': chart, 'upload': upload,
                             'chart_type_choices': ChartConfig.CHART_TYPES,
                             'color_choices': ChartConfig.COLOR_PALETTES,
                             'size_choices': ChartConfig.SIZE_CHOICES,
                             'agg_choices': ChartConfig.AGG_CHOICES},
                            request=request)
    return HttpResponse(html)
