import csv
import io
import json
import os
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST, require_GET
from django.contrib import messages
from django.utils import timezone
from django.urls import reverse
from datetime import timedelta
from .models import FileUpload, SavedDashboard, ChartConfig, UploadAnalysisProfile, UploadClarificationResponse, AdaptiveRefinementSession
from .engine import analyse, compare_dataframes, get_excel_sheets, load_dataframe
from .upload_ai_screening import run_upload_screening
from .ai_policy import get_ai_access_context
from .ai_conversation_flow import sync_session, save_turn_answer
from .adaptive_refinement_engine import build_question_schema, build_recommendations
from .utils.safe_text import sanitize_text
from .gallery_ui import build_share_ui


def _sanitise_result(data):
    """
    Walk the entire analysis result dict and convert every non-JSON-serialisable
    value to a safe primitive. Uses a JSON round-trip with a fallback encoder
    so that Timestamps, numpy scalars, NaT, etc. never reach the database.
    """
    import json as _json
    import math as _math

    class _Enc(_json.JSONEncoder):
        def default(self, obj):
            # pandas types
            try:
                import pandas as _pd
                if isinstance(obj, _pd.Timestamp):  return obj.isoformat()
                if isinstance(obj, _pd.Period):      return str(obj)
                if obj is _pd.NaT or obj is _pd.NA:  return None
            except Exception:
                pass
            # numpy types
            try:
                import numpy as _np
                if isinstance(obj, _np.integer):   return int(obj)
                if isinstance(obj, _np.floating):
                    return None if (_np.isnan(obj) or _np.isinf(obj)) else float(obj)
                if isinstance(obj, _np.bool_):     return bool(obj)
                if isinstance(obj, _np.ndarray):   return obj.tolist()
            except Exception:
                pass
            # datetime
            try:
                import datetime
                if isinstance(obj, (datetime.datetime, datetime.date)):
                    return obj.isoformat()
            except Exception:
                pass
            return str(obj)   # last resort — never crash

    return _json.loads(_json.dumps(data, cls=_Enc))


def _get_file_type(filename: str):
    ext = os.path.splitext(filename)[1].lower()
    return {'.csv': 'csv', '.xlsx': 'excel', '.xls': 'excel', '.json': 'json'}.get(ext)


def _monthly_count(user):
    month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return FileUpload.objects.filter(user=user, created_at__gte=month_start).count()


def _get_or_create_refinement_session(upload_obj):
    profile = getattr(upload_obj, 'screening_profile', None) or run_upload_screening(upload_obj)
    screening_json = profile.screening_json or {}
    schema_payload = build_question_schema(
        profile.profile_json or {},
        screening_json,
        ai_enabled=bool(screening_json.get('ai_enabled')),
    )
    defaults = {
        'profile': profile,
        'classification_json': schema_payload.get('classification', {}),
        'question_schema': schema_payload.get('questions', []),
        'recommendations_json': build_recommendations(profile.profile_json or {}, screening_json, {}),
    }
    session, created = AdaptiveRefinementSession.objects.get_or_create(upload=upload_obj, defaults=defaults)
    changed = created
    if session.profile_id != profile.id:
        session.profile = profile
        changed = True
    if not session.question_schema:
        session.question_schema = schema_payload.get('questions', [])
        changed = True
    if not session.classification_json:
        session.classification_json = schema_payload.get('classification', {})
        changed = True
    session.recommendations_json = build_recommendations(profile.profile_json or {}, screening_json, session.answers_json or {})
    if changed:
        session.save()
    else:
        session.save(update_fields=['recommendations_json', 'updated_at'])
    return profile, session, schema_payload


def _extract_refinement_answer(question, request):
    key = question.get('key')
    q_type = question.get('type')
    if q_type == 'multi_select':
        values = [v for v in request.POST.getlist(key) if str(v).strip()]
        max_select = int(question.get('max_select') or len(values) or 3)
        return values[:max_select]
    value = request.POST.get(key, '')
    return value.strip() if isinstance(value, str) else value


# ── Upload ─────────────────────────────────────────────────────────────────────

@login_required
def upload(request):
    sub = getattr(request, 'subscription', None)
    is_pro = sub.is_active if sub else False
    m_count = _monthly_count(request.user)
    m_pct = min(int(m_count / settings.FREE_UPLOAD_LIMIT * 100), 100)

    if request.method == 'POST':
        file = request.FILES.get('file')
        if not file:
            err = 'No file selected.'
            if request.htmx:
                return HttpResponse(f'<p class="text-red-400 text-sm mt-4 text-center">{err}</p>')
            messages.error(request, err); return redirect('analyser:upload')

        file_type = _get_file_type(file.name)
        if not file_type:
            err = 'Unsupported file type. Upload CSV, XLSX/XLS, or JSON.'
            if request.htmx:
                return HttpResponse(f'<p class="text-red-400 text-sm mt-4 text-center">{err}</p>')
            messages.error(request, err); return redirect('analyser:upload')

        size_limit = sub.file_size_limit if sub else settings.FREE_FILE_SIZE_LIMIT
        if file.size > size_limit:
            err = f'File too large. Limit: {size_limit/1024/1024:.0f} MB.'
            if request.htmx:
                return HttpResponse(f'<p class="text-red-400 text-sm mt-4 text-center">{err}</p>')
            messages.error(request, err); return redirect('analyser:upload')

        if not is_pro and m_count >= settings.FREE_UPLOAD_LIMIT:
            err = f'Monthly upload limit ({settings.FREE_UPLOAD_LIMIT}) reached.'
            if request.htmx:
                return HttpResponse(
                    f'<div class="mt-4 p-4 bg-amber-900/30 border border-amber-700/40 rounded-xl text-amber-300 text-sm text-center">'
                    f'{err} <a href="/billing/pricing/" class="underline font-semibold">Upgrade →</a></div>')
            messages.error(request, err); return redirect('billing:pricing')

        upload_obj = FileUpload.objects.create(
            user=request.user, file=file, original_name=file.name,
            file_type=file_type, file_size=file.size, status=FileUpload.STATUS_PROCESSING,
        )

        screening_profile = None
        try:
            result = analyse(upload_obj.file.path, file_type)
            result = _sanitise_result(result)   # strip Timestamps, numpy scalars, etc.
            upload_obj.analysis_result = result
            upload_obj.row_count = result['rows']
            upload_obj.column_count = result['cols']
            upload_obj.status = FileUpload.STATUS_DONE
            if result.get('sheets'):
                upload_obj.available_sheets = result['sheets']
                upload_obj.active_sheet = result['sheets'][0]
            upload_obj.save()
            screening_profile = run_upload_screening(upload_obj)

            # ── Auto AI insights (non-blocking) ──────────────────────────────
            # Analyse the dataset immediately so insights are ready on first view.
            try:
                from .ai_policy import get_ai_access_context as _ai_ctx
                _ctx = _ai_ctx(request.user, feature='upload_screening', estimated_tokens=700)
                if _ctx.get('ai_enabled') and not upload_obj.ai_insights:
                    from .ai import generate_insights
                    _insights = generate_insights(upload_obj.analysis_result, upload_obj.original_name)
                    if _insights:
                        upload_obj.ai_insights = sanitize_text(_insights, limit=4000, preview=False)
                        upload_obj.save(update_fields=['ai_insights'])
            except Exception:
                pass  # Non-blocking — dashboard still loads fine without insights
        except Exception as e:
            upload_obj.status = FileUpload.STATUS_ERROR
            upload_obj.error_message = str(e)
            upload_obj.save()
            if request.htmx:
                return HttpResponse(f'<p class="text-red-400 text-sm mt-4 text-center">Error: {e}</p>')
            messages.error(request, f'Error: {e}'); return redirect('analyser:upload')

        next_url = None
        if screening_profile and screening_profile.requires_clarification and not screening_profile.is_confirmed:
            next_url = f'/workspace/{upload_obj.id}/review/'
        else:
            next_url = f'/workspace/{upload_obj.id}/'

        if request.htmx:
            from django.template.loader import render_to_string
            html = render_to_string('analyser/partials/upload_success.html', {'upload': upload_obj, 'next_url': next_url}, request=request)
            resp = HttpResponse(html)
            resp['HX-Push-Url'] = next_url
            return resp
        if screening_profile and screening_profile.requires_clarification and not screening_profile.is_confirmed:
            return redirect('analyser:profile_review', pk=upload_obj.id)
        return redirect('analyser:result', pk=upload_obj.id)

    return render(request, 'analyser/upload.html', {'is_pro': is_pro, 'monthly_count': m_count, 'monthly_pct': m_pct})


# ── Sheet switcher (HTMX) ─────────────────────────────────────────────────────

@login_required
@require_POST
def switch_sheet(request, pk):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    sheet_name = request.POST.get('sheet_name', '')
    try:
        result = analyse(upload_obj.file.path, upload_obj.file_type, sheet_name=sheet_name)
        result = _sanitise_result(result)
        upload_obj.analysis_result = result
        upload_obj.row_count = result['rows']
        upload_obj.column_count = result['cols']
        upload_obj.active_sheet = sheet_name
        upload_obj.save(update_fields=['analysis_result', 'row_count', 'column_count', 'active_sheet'])
    except Exception as e:
        return HttpResponse(f'<p class="text-red-400">Error loading sheet: {e}</p>')
    from django.template.loader import render_to_string
    sub = getattr(request, 'subscription', None)
    html = render_to_string('analyser/partials/analysis_panels.html', {
        'upload': upload_obj, 'analysis': result,
        'is_pro': sub.is_active if sub else False,
    }, request=request)
    return HttpResponse(html)


# ── Result ────────────────────────────────────────────────────────────────────

@login_required
def result(request, pk):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    sub = getattr(request, 'subscription', None)
    is_pro = sub.is_active if sub else False
    analysis = upload_obj.analysis_result or {}
    cols = analysis.get('columns', [])
    numeric = [c['name'] for c in cols if c.get('is_numeric')]
    categ   = [c['name'] for c in cols if not c.get('is_numeric')]
    # Build example NLQ suggestions from actual columns
    examples = []
    if numeric:
        examples.append(f"What is the average {numeric[0]}?")
        if len(numeric) >= 2:
            examples.append(f"Show {numeric[0]} vs {numeric[1]}")
    if categ and numeric:
        examples.append(f"Which {categ[0]} has the highest {numeric[0]}?")
        examples.append(f"What is the total {numeric[0]} by {categ[0]}?")
    if not examples:
        examples = ["How many rows are there?", "What are the column names?"]
    return render(request, 'analyser/result.html', {
        'upload':             upload_obj,
        'analysis':           analysis,
        'is_pro':             is_pro,
        'chart_configs':      upload_obj.chart_configs.all(),
        'example_questions':  examples[:4],
        'chart_type_choices': ChartConfig.CHART_TYPES,
        'color_choices':      ChartConfig.COLOR_PALETTES,
        'size_choices':       ChartConfig.SIZE_CHOICES,
        'agg_choices':        ChartConfig.AGG_CHOICES,
        'all_columns':        [c['name'] for c in analysis.get('columns', [])],
        'share_ui':           build_share_ui(request, upload_obj),
    })


@login_required
def profile_review(request, pk):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    profile = getattr(upload_obj, 'screening_profile', None) or run_upload_screening(upload_obj)
    existing = getattr(profile, 'clarification_response', None)
    existing_answers = (existing.response_json if existing else {})
    session, review_state = sync_session(profile, existing_answers, user=request.user)

    debug_profile_payload = {
        'profile_json': profile.profile_json or {},
        'screening_json': profile.screening_json or {},
        'analysis_user_guidance': (upload_obj.analysis_result or {}).get('user_guidance') or {},
        'analysis_conversation_brief': (upload_obj.analysis_result or {}).get('conversation_brief') or {},
        'analysis_conversation_confidence': (upload_obj.analysis_result or {}).get('conversation_confidence') or {},
    }
    debug_data_profile = json.dumps(debug_profile_payload, indent=2, ensure_ascii=False, default=str)

    return render(request, 'analyser/profile_review.html', {
        'upload': upload_obj,
        'screening_profile': profile,
        'profile_json': profile.profile_json,
        'screening_json': profile.screening_json,
        'questions': profile.question_payload or [],
        'existing_answers': existing_answers,
        'review_state': review_state,
        'conversation_session': session,
        'debug_data_profile': debug_data_profile,
        'show_debug_data_profile': settings.DEBUG or request.GET.get('debug_profile') == '1',
    })


@login_required
@require_POST
def submit_profile_review(request, pk):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    profile = getattr(upload_obj, 'screening_profile', None) or run_upload_screening(upload_obj)
    existing = getattr(profile, 'clarification_response', None)
    answers = dict(existing.response_json) if existing and isinstance(existing.response_json, dict) else {}

    action = request.POST.get('action', 'next')
    _session, review_state, guidance = save_turn_answer(profile, request, answers, user=request.user)
    should_finish = action == 'finish' or review_state.get('is_complete') or review_state.get('ready_to_build')
    if not should_finish:
        messages.info(request, 'Answer saved. Nexyza updated the conversation and selected the next best question.')
        return redirect('analyser:profile_review', pk=upload_obj.id)

    profile.is_confirmed = True
    profile.requires_clarification = False
    profile.save(update_fields=['is_confirmed', 'requires_clarification', 'updated_at'])

    analysis = upload_obj.analysis_result or {}
    analysis['user_guidance'] = guidance
    analysis['ai_review_answers'] = answers
    analysis['conversation_brief'] = review_state.get('business_brief') or {}
    analysis['conversation_confidence'] = review_state.get('confidence') or {}
    upload_obj.analysis_result = _sanitise_result(analysis)
    upload_obj.save(update_fields=['analysis_result', 'updated_at'])

    upload_obj.chart_configs.filter(is_auto=True).delete()
    messages.success(request, 'Dataset preferences saved. Nexyza will now build the first dashboard using your conversation guidance.')
    return redirect('analyser:build_dashboard', pk=upload_obj.id)


@login_required
def build_dashboard(request, pk):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    ai_ctx = get_ai_access_context(request.user, feature='first_dashboard', estimated_tokens=3800)
    thinking_steps = [
        'Profiling dataset',
        'Understanding business intent',
        'Evaluating your answers',
        'Choosing measures and dimensions',
        'Building KPI cards',
        'Generating charts',
        'Checking chart quality',
        'Preparing insights',
    ]
    kpi_placeholders = [
        'Revenue KPI',
        'Target gap',
        'Top performers',
        'Forecast readiness',
    ]
    screening_profile = getattr(upload_obj, 'screening_profile', None)
    screening_json = getattr(screening_profile, 'screening_json', {}) if screening_profile else {}
    return render(request, 'analyser/build_dashboard.html', {
        'upload': upload_obj,
        'ai_context': ai_ctx,
        'thinking_steps': thinking_steps,
        'kpi_placeholders': kpi_placeholders,
        'screening_json': screening_json,
        'conversation_brief': (upload_obj.analysis_result or {}).get('conversation_brief') or {},
        'semantic_snapshot': screening_json.get('business_semantics') or (((upload_obj.analysis_result or {}).get('profile_json') or {}).get('business_semantics') or {}),
    })


@login_required
@require_POST
def build_dashboard_start(request, pk):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    ai_ctx = get_ai_access_context(request.user, feature='first_dashboard', estimated_tokens=3800)

    from .charts import auto_generate_charts
    if ai_ctx.get('ai_enabled'):
        try:
            from .ai_charts import ai_recommend_charts, apply_ai_recommendations
            configs = ai_recommend_charts(upload_obj.analysis_result or {}, upload_obj.original_name, user=request.user)
            created = apply_ai_recommendations(upload_obj, configs)
            _prune_empty_auto_charts(upload_obj)
            return JsonResponse({'ok': True, 'redirect_url': reverse('analyser:chart_gallery', args=[upload_obj.id]), 'mode': 'ai', 'count': len(created)})
        except Exception as exc:
            created = auto_generate_charts(upload_obj)
            _prune_empty_auto_charts(upload_obj)
            return JsonResponse({'ok': True, 'redirect_url': reverse('analyser:chart_gallery', args=[upload_obj.id]), 'mode': 'manual_fallback', 'count': len(created), 'warning': str(exc)[:300]})

    created = auto_generate_charts(upload_obj)
    _prune_empty_auto_charts(upload_obj)
    return JsonResponse({'ok': True, 'redirect_url': reverse('analyser:chart_gallery', args=[upload_obj.id]), 'mode': 'manual', 'count': len(created), 'message': ai_ctx.get('message', '')})


def _prune_empty_auto_charts(upload_obj):
    qs = upload_obj.chart_configs.filter(is_auto=True)
    for chart in qs:
        payload = chart.cached_data or {}
        labels = payload.get('labels') or []
        datasets = payload.get('datasets') or []
        values = []
        for ds in datasets:
            if isinstance(ds, dict):
                values.extend([v for v in (ds.get('data') or []) if v not in (None, '')])
        note = str(payload.get('note') or '').lower()
        if ('no chart data' in note) or (not labels and not values) or (values and all((v == 0 or v == 0.0) for v in values)):
            chart.delete()



# ── Shared view (public) ──────────────────────────────────────────────────────

def shared_result(request, token):
    upload_obj = get_object_or_404(FileUpload, share_token=token, share_enabled=True)
    if upload_obj.share_expires and upload_obj.share_expires < timezone.now():
        return render(request, 'analyser/share_expired.html')
    return render(request, 'analyser/result.html', {
        'upload': upload_obj,
        'analysis': upload_obj.analysis_result or {},
        'is_pro': True,  # viewer sees full results
        'is_shared_view': True,
    })


# ── Share link management ─────────────────────────────────────────────────────

@login_required
@require_POST
def toggle_share(request, pk):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    action = request.POST.get('action', 'enable')
    if action == 'enable':
        if not upload_obj.share_token:
            upload_obj.generate_share_token()
        upload_obj.share_enabled = True
        days = int(request.POST.get('days', settings.SHARE_LINK_EXPIRY_DAYS))
        upload_obj.share_expires = timezone.now() + timedelta(days=days)
    else:
        upload_obj.share_enabled = False
    upload_obj.save(update_fields=['share_token', 'share_enabled', 'share_expires'])
    if request.htmx:
        from django.template.loader import render_to_string
        return HttpResponse(render_to_string('analyser/partials/share_panel.html',
                                             {'upload': upload_obj, 'request': request}))
    return redirect('analyser:result', pk=pk)


# ── AI Insights ───────────────────────────────────────────────────────────────

@login_required
@require_POST
def generate_ai_insights(request, pk):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    sub = getattr(request, 'subscription', None)
    if not (sub and sub.is_active):
        return HttpResponse(
            '<div class="p-5 bg-amber-900/20 border border-amber-700/30 rounded-xl text-amber-300 text-sm">'
            '🔒 AI Insights require a <strong>Pro plan</strong>. '
            '<a href="/billing/pricing/" class="underline font-semibold ml-1">Upgrade now →</a></div>')
    if not upload_obj.ai_insights:
        try:
            from .ai import generate_insights
            insights = generate_insights(upload_obj.analysis_result, upload_obj.original_name)
            upload_obj.ai_insights = sanitize_text(insights, limit=4000, preview=False)
            upload_obj.save(update_fields=['ai_insights'])
        except Exception as e:
            return HttpResponse(f'<p class="text-red-400 text-sm">AI error: {e}</p>')
    from django.template.loader import render_to_string
    return HttpResponse(render_to_string('analyser/partials/ai_insights.html',
                                         {'insights': sanitize_text(upload_obj.ai_insights, limit=4000, preview=False)}, request=request))


# ── Chart builder ─────────────────────────────────────────────────────────────

CHART_TYPES = [
    ('bar','Bar'), ('line','Line'), ('scatter','Scatter'),
    ('pie','Pie'), ('doughnut','Doughnut'), ('area','Area'),
]

@login_required
def chart_builder(request, pk):
    import json as _json
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    analysis = upload_obj.analysis_result or {}
    cols = analysis.get('columns', [])
    return render(request, 'analyser/chart_builder.html', {
        'upload': upload_obj,
        'columns': cols,
        'numeric_columns': [c for c in cols if c.get('is_numeric')],
        'all_columns': [c['name'] for c in cols],
        'chart_configs': upload_obj.chart_configs.all(),
        'chart_types': CHART_TYPES,
        'chart_type_js': _json.dumps([ct for ct,_ in CHART_TYPES]),
    })


@login_required
@require_POST
def chart_data(request, pk):
    """Return Chart.js-ready JSON for the given config."""
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    x_col  = request.POST.get('x_axis', '')
    y_col  = request.POST.get('y_axis', '')
    agg    = request.POST.get('aggregation', 'sum')
    ctype  = request.POST.get('chart_type', 'bar')
    group  = request.POST.get('group_by', '')

    try:
        df = load_dataframe(upload_obj.file.path, upload_obj.file_type,
                            sheet_name=upload_obj.active_sheet or None)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

    if x_col not in df.columns or y_col not in df.columns:
        return JsonResponse({'error': 'Invalid column selection.'}, status=400)

    try:
        if group and group in df.columns:
            agg_fn = {'sum': 'sum', 'mean': 'mean', 'count': 'count', 'min': 'min', 'max': 'max'}[agg]
            pivot = df.groupby([x_col, group])[y_col].agg(agg_fn).unstack(fill_value=0)
            COLORS = ['rgba(139,92,246,0.8)','rgba(59,130,246,0.8)','rgba(16,185,129,0.8)',
                      'rgba(245,158,11,0.8)','rgba(239,68,68,0.8)','rgba(236,72,153,0.8)']
            datasets = [
                {'label': str(col), 'data': pivot[col].tolist(),
                 'backgroundColor': COLORS[i % len(COLORS)],
                 'borderColor': COLORS[i % len(COLORS)].replace('0.8','1'),
                 'borderWidth': 2, 'tension': 0.4}
                for i, col in enumerate(pivot.columns)
            ]
            labels = [str(l) for l in pivot.index.tolist()]
        else:
            agg_fn = {'sum': 'sum', 'mean': 'mean', 'count': 'count', 'min': 'min', 'max': 'max'}[agg]
            grouped = df.groupby(x_col)[y_col].agg(agg_fn).reset_index()
            grouped = grouped.sort_values(y_col, ascending=False).head(50)
            labels = [str(v) for v in grouped[x_col].tolist()]
            datasets = [{
                'label': f'{agg.title()} of {y_col}',
                'data': [round(float(v), 4) if v == v else 0 for v in grouped[y_col].tolist()],
                'backgroundColor': 'rgba(139,92,246,0.7)',
                'borderColor': 'rgba(139,92,246,1)',
                'borderWidth': 2,
                'tension': 0.4,
                'fill': ctype == 'area',
            }]
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'labels': labels, 'datasets': datasets, 'chart_type': ctype})


@login_required
@require_POST
def save_chart(request, pk):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    ChartConfig.objects.create(
        upload=upload_obj,
        name=request.POST.get('name', 'My Chart'),
        chart_type=request.POST.get('chart_type', 'bar'),
        x_axis=request.POST.get('x_axis', ''),
        y_axis=request.POST.get('y_axis', ''),
        group_by=request.POST.get('group_by', ''),
        aggregation=request.POST.get('aggregation', 'sum'),
    )
    messages.success(request, 'Chart saved.')
    return redirect('analyser:chart_builder', pk=pk)


# ── Compare ───────────────────────────────────────────────────────────────────

@login_required
def compare(request):
    uploads = FileUpload.objects.filter(user=request.user, status=FileUpload.STATUS_DONE)
    diff = None
    upload_a = upload_b = None

    if request.method == 'POST':
        id_a = request.POST.get('file_a')
        id_b = request.POST.get('file_b')
        if id_a and id_b and id_a != id_b:
            upload_a = get_object_or_404(FileUpload, pk=id_a, user=request.user)
            upload_b = get_object_or_404(FileUpload, pk=id_b, user=request.user)
            diff = compare_dataframes(upload_a.analysis_result or {}, upload_b.analysis_result or {})

    return render(request, 'analyser/compare.html', {
        'uploads': uploads,
        'diff': diff,
        'upload_a': upload_a,
        'upload_b': upload_b,
    })


# ── Export ────────────────────────────────────────────────────────────────────

@login_required
def export(request, pk, fmt):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    if upload_obj.status != FileUpload.STATUS_DONE:
        return HttpResponse('Not ready', status=400)
    analysis = upload_obj.analysis_result or {}

    if fmt == 'json':
        resp = HttpResponse(json.dumps(analysis, indent=2, default=str), content_type='application/json')
        resp['Content-Disposition'] = f'attachment; filename="{upload_obj.original_name}_analysis.json"'
        return resp

    if fmt == 'csv':
        out = io.StringIO()
        w = csv.writer(out)
        w.writerow(['Column', 'Type', 'Nulls %', 'Unique', 'Min', 'Max', 'Mean', 'Median', 'Std'])
        for col in analysis.get('columns', []):
            w.writerow([col['name'], col['dtype'], col['null_pct'], col['unique_count'],
                        col.get('min',''), col.get('max',''), col.get('mean',''),
                        col.get('median',''), col.get('std','')])
        resp = HttpResponse(out.getvalue(), content_type='text/csv')
        resp['Content-Disposition'] = f'attachment; filename="{upload_obj.original_name}_summary.csv"'
        return resp

    return HttpResponse('Invalid format', status=400)


# ── Delete ────────────────────────────────────────────────────────────────────


@login_required
@require_POST
def pin_upload(request, pk):
    """Toggle pin status on a file upload."""
    from django.http import JsonResponse
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    upload.is_pinned = not upload.is_pinned
    upload.save(update_fields=['is_pinned'])
    return JsonResponse({'ok': True, 'pinned': upload.is_pinned})


@login_required
def delete_upload(request, pk):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    if request.method == 'POST':
        upload_obj.file.delete(save=False)
        upload_obj.delete()
        messages.success(request, 'File deleted.')
        return redirect('dashboard:index')
    return render(request, 'analyser/confirm_delete.html', {'upload': upload_obj})


def _cache_analysis(upload_id: int, result: dict):
    """Optionally cache heavy analysis results to Redis/disk."""
    try:
        from django.core.cache import cache
        cache.set(f'analysis:{upload_id}', result, timeout=3600)
    except Exception:
        pass


# ── Bulk operations ───────────────────────────────────────────────────────────

@login_required
@require_POST
def bulk_delete(request):
    """Delete multiple uploads at once."""
    from django.http import JsonResponse
    # Accept ids as a list, comma-separated string, or JSON body
    ids = request.POST.getlist('ids[]') or request.POST.getlist('ids')
    if len(ids) == 1 and ',' in ids[0]:
        ids = [i.strip() for i in ids[0].split(',') if i.strip()]
    if not ids:
        import json
        try:
            body = json.loads(request.body)
            ids  = body.get('ids', [])
        except Exception:
            pass

    deleted = 0
    for pk in ids:
        try:
            upload = FileUpload.objects.get(pk=pk, user=request.user)
            upload.file.delete(save=False)
            upload.delete()
            deleted += 1
        except FileUpload.DoesNotExist:
            pass

    if request.headers.get('Accept') == 'application/json' or request.htmx:
        return JsonResponse({'ok': True, 'deleted': deleted})
    messages.success(request, f'{deleted} file(s) deleted.')
    return redirect('dashboard:index')



@login_required
def adaptive_refinement(request, pk):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    profile, session, schema_payload = _get_or_create_refinement_session(upload_obj)
    questions = session.question_schema or schema_payload.get('questions', [])
    total = len(questions)
    answered_count = 0
    for q in questions:
        val = (session.answers_json or {}).get(q.get('key'))
        if isinstance(val, list):
            answered_count += 1 if [x for x in val if str(x).strip()] else 0
        elif str(val).strip():
            answered_count += 1
    step = min(max(int(request.GET.get('step', session.current_step or 0) or 0), 0), max(total - 1, 0))
    current_question = questions[step] if questions else None
    progress_pct = int((answered_count / total) * 100) if total else 100
    return render(request, 'analyser/adaptive_refinement.html', {
        'upload': upload_obj,
        'screening_profile': profile,
        'session': session,
        'questions': questions,
        'current_question': current_question,
        'current_step': step,
        'answered_count': answered_count,
        'total_questions': total,
        'progress_pct': progress_pct,
        'classification': session.classification_json or schema_payload.get('classification', {}),
        'recommendations': session.recommendations_json or {},
        'dataset_summary': schema_payload.get('dataset_summary') or ((profile.screening_json or {}).get('dataset_summary') or ''),
        'existing_answers': session.answers_json or {},
    })


@login_required
@require_POST
def adaptive_refinement_submit(request, pk):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    profile, session, _schema_payload = _get_or_create_refinement_session(upload_obj)
    questions = session.question_schema or []
    answers = dict(session.answers_json or {})
    action = request.POST.get('action', 'next')
    active_key = request.POST.get('active_key', '')
    current_idx = next((i for i, q in enumerate(questions) if q.get('key') == active_key), session.current_step or 0)
    current_question = questions[current_idx] if 0 <= current_idx < len(questions) else None
    if current_question:
        if action == 'skip':
            answers.pop(active_key, None)
        elif action != 'back':
            answers[active_key] = _extract_refinement_answer(current_question, request)
    if action == 'back':
        next_idx = max(current_idx - 1, 0)
    else:
        next_idx = min(current_idx + 1, max(len(questions) - 1, 0))
    session.answers_json = answers
    session.current_step = next_idx
    session.recommendations_json = build_recommendations(profile.profile_json or {}, profile.screening_json or {}, answers)
    if action == 'finish':
        session.is_complete = True
    session.save(update_fields=['answers_json', 'current_step', 'recommendations_json', 'is_complete', 'updated_at'])

    analysis = upload_obj.analysis_result or {}
    analysis['adaptive_refinement_answers'] = answers
    analysis['adaptive_refinement_recommendations'] = session.recommendations_json
    analysis['user_guidance'] = session.recommendations_json
    analysis['conversation_brief'] = {
        'dataset_type': (session.classification_json or {}).get('primary_label', ''),
        'priorities': session.recommendations_json.get('priorities', []),
        'main_measures': session.recommendations_json.get('main_measures', []),
        'important_dimensions': session.recommendations_json.get('important_dimensions', []),
        'time_axis': session.recommendations_json.get('time_axis', ''),
        'target_column': session.recommendations_json.get('target_column', ''),
        'output_mode': session.recommendations_json.get('output_mode', ''),
    }
    upload_obj.analysis_result = _sanitise_result(analysis)
    upload_obj.save(update_fields=['analysis_result', 'updated_at'])

    if action == 'finish':
        messages.success(request, 'Adaptive refinement saved. Nexyza will now build the dashboard using these decisions.')
        return redirect('analyser:build_dashboard', pk=upload_obj.id)
    return redirect(f"{reverse('analyser:adaptive_refinement', kwargs={'pk': upload_obj.id})}?step={next_idx}")


@login_required
@require_GET
def adaptive_refinement_download(request, pk):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    profile, session, schema_payload = _get_or_create_refinement_session(upload_obj)
    payload = {
        'upload_id': str(upload_obj.id),
        'dataset_name': upload_obj.original_name,
        'classification': session.classification_json or schema_payload.get('classification', {}),
        'dataset_summary': schema_payload.get('dataset_summary') or ((profile.screening_json or {}).get('dataset_summary') or ''),
        'questions': session.question_schema or [],
        'answers': session.answers_json or {},
        'recommendations': session.recommendations_json or {},
        'profile_excerpt': {
            'measures': (profile.profile_json or {}).get('measures', []),
            'dimensions': (profile.profile_json or {}).get('dimensions', []),
            'time_columns': (profile.profile_json or {}).get('time_columns', []),
            'target_columns': (profile.profile_json or {}).get('target_columns', []),
        },
    }
    response = JsonResponse(payload, json_dumps_params={'indent': 2})
    response['Content-Disposition'] = f'attachment; filename="adaptive-refinement-{upload_obj.id}.json"'
    return response



def _infer_dashboard_filters(df):
    import pandas as pd
    filters = []
    try:
        year_col = None
        for col in df.columns:
            s = str(col).lower()
            if 'year' in s:
                year_col = col
                break
        if year_col is None:
            for col in df.columns:
                series = df[col]
                if pd.api.types.is_datetime64_any_dtype(series):
                    year_col = col
                    break
        if year_col is not None:
            series = df[year_col]
            if not pd.api.types.is_datetime64_any_dtype(series):
                try:
                    series = pd.to_datetime(series, errors='coerce')
                except Exception:
                    series = None
            if series is not None and getattr(series, 'dt', None) is not None:
                years = [int(y) for y in sorted(series.dt.year.dropna().unique().tolist())]
                if years:
                    filters.append({'key': 'year', 'label': 'Year', 'options': ['All Years'] + [str(y) for y in years]})
        categorical = []
        for col in df.columns:
            if len(categorical) >= 2:
                break
            s = df[col]
            if pd.api.types.is_object_dtype(s) or pd.api.types.is_categorical_dtype(s):
                uniques = [str(v) for v in s.dropna().astype(str).unique().tolist() if str(v).strip()][:12]
                if 2 <= len(uniques) <= 12:
                    categorical.append((col, uniques))
        labels = ['Province', 'Category']
        for idx, item in enumerate(categorical):
            col, options = item
            filters.append({'key': str(col), 'label': labels[idx], 'options': [f'All {labels[idx]}s'] + options})
    except Exception:
        pass
    return filters[:3]


def _pick_power_dashboard_charts(charts):
    import re
    non_kpis = [c for c in charts if c.chart_type != 'kpi' and c.cached_data]
    def score(chart, terms, types=None):
        title = f"{chart.title} {chart.chart_type}".lower()
        value = sum(4 for t in terms if t in title)
        if types and chart.chart_type in types:
            value += 2
        return value
    def select(terms, types=None, used=None):
        used = used or set()
        ranked = sorted(non_kpis, key=lambda c: (score(c, terms, types), c.sort_order, c.created_at), reverse=True)
        for c in ranked:
            if c.id not in used:
                return c
        return None
    used = set()
    trend = select(['trend','month','time','over time','monthly'], {'line','bar','area','rolling_line','cumulative_line'}, used)
    if trend:
        used.add(trend.id)
    compare = select(['branch','region','category','manager','comparison','rank'], {'horizontal_bar','bar','variance_bar'}, used)
    if compare:
        used.add(compare.id)
    attainment = select(['attainment','achievement %','achievement','target','gap','variance'], {'bar','horizontal_bar','variance_bar','bullet','progress_ring','waterfall'}, used)
    if attainment:
        used.add(attainment.id)
    mix = select(['mix','share','composition','category','contribution','pareto'], {'pie','doughnut','pareto'}, used)
    if mix:
        used.add(mix.id)
    detail = []
    for c in non_kpis:
        if c.id not in used:
            detail.append(c)
    return {
        'hero': [c for c in [trend, compare] if c],
        'secondary': [c for c in [attainment, mix] if c],
        'detail': detail[:4],
    }


def _chart_payload(chart):
    payload = chart.cached_data or {}
    return {
        'id': str(chart.id),
        'title': chart.title,
        'type': chart.chart_type,
        'payload': payload,
    }


@login_required
def power_dashboard(request, pk):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    charts = list(upload_obj.chart_configs.order_by('sort_order', 'created_at'))
    kpi_charts = [c for c in charts if c.chart_type == 'kpi' and c.cached_data][:4]
    selected = _pick_power_dashboard_charts(charts)
    chart_bundles = {
        'hero': [_chart_payload(c) for c in selected['hero']],
        'secondary': [_chart_payload(c) for c in selected['secondary']],
        'detail': [_chart_payload(c) for c in selected['detail']],
    }
    filters = []
    rows_preview = []
    table_columns = []
    try:
        df = load_dataframe(upload_obj)
        if df is not None:
            filters = _infer_dashboard_filters(df)
            preview = df.head(500).copy()
            table_columns = [str(c) for c in preview.columns]  # all columns
            rows_preview = preview.fillna('').astype(str).to_dict(orient='records')
    except Exception:
        pass

    analysis = upload_obj.analysis_result or {}
    profile_json = (analysis.get('profile_json') or {})
    semantic = profile_json.get('business_semantics') or (getattr(getattr(upload_obj, 'screening_profile', None), 'screening_json', {}) or {}).get('business_semantics') or {}
    subtitle = semantic.get('summary') or analysis.get('adaptive_refinement_recommendations', {}).get('summary') or 'Decision-ready dashboard built from the current dataset and generated chart pack.'
    # Dynamic tab names from semantic profile
    primary_measure = semantic.get('primary_measure') or ''
    analysis_label = (f"{primary_measure} Analysis" if primary_measure else None) or 'Performance'
    nav_sections = [
        {'key': 'overview', 'label': 'Overview'},
        {'key': 'analysis', 'label': analysis_label},
        {'key': 'data', 'label': 'Data View'},
    ]
    context = {
        'upload': upload_obj,
        'kpi_charts': kpi_charts,
        'chart_bundles_json': json.dumps(chart_bundles),
        'filters': filters,
        'nav_sections': nav_sections,
        'dashboard_title': semantic.get('dataset_name') or upload_obj.original_name,
        'dashboard_subtitle': subtitle,
        'table_columns': table_columns,          # list — for Django template loop
        'table_columns_json': json.dumps(table_columns),  # JSON — for JS
        'table_rows_json': json.dumps(rows_preview),
    }
    return render(request, 'analyser/power_dashboard.html', context)
