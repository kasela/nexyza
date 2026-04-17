from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List


def _clean(value: Any, fallback: str = '—') -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text or fallback


def _analysis_type(analysis: Dict[str, Any]) -> str:
    profile = (analysis or {}).get('profile_json') or {}
    cls = profile.get('analysis_classification') or {}
    value = cls.get('analysis_type') or (analysis or {}).get('analysis_type') or 'general_business'
    return str(value).replace('_', ' ').title()


def _roles(analysis: Dict[str, Any]) -> Dict[str, Any]:
    profile = (analysis or {}).get('profile_json') or {}
    screening = (analysis or {}).get('screening_json') or {}
    return profile.get('business_roles') or screening.get('business_roles') or {}


def _profile(analysis: Dict[str, Any]) -> Dict[str, Any]:
    return (analysis or {}).get('profile_json') or {}


def _benchmark_label(analysis: Dict[str, Any]) -> str:
    summary = (analysis or {}).get('benchmark_summary') or {}
    suite = summary.get('suite') or {}
    preferred = (summary.get('benchmark_kind') or summary.get('kind') or '').strip()
    if preferred:
        return preferred.replace('_', ' ').title()
    if suite:
        return ', '.join(k.replace('_', ' ').title() for k in list(suite.keys())[:3])
    return 'Not available'


def _time_logic(analysis: Dict[str, Any]) -> str:
    ti = (analysis or {}).get('time_intelligence') or {}
    signals = []
    if ti.get('current_period') and ti.get('previous_period'):
        signals.append('Previous period')
    if ti.get('qoq'):
        signals.append('QoQ')
    if ti.get('yoy'):
        signals.append('YoY')
    if ti.get('rolling'):
        signals.append('Rolling window')
    if ti.get('ytd'):
        signals.append('YTD')
    return ', '.join(signals) if signals else 'Static snapshot'


def build_chart_audit_meta(chart: Any, analysis: Dict[str, Any]) -> Dict[str, Any]:
    render_meta = getattr(chart, 'render_meta', None) or {}
    conf = getattr(chart, 'confidence_meta', None) or {}
    guardrail = (getattr(chart, 'config_json', None) or {}).get('guardrail') or {}
    explanation = getattr(chart, 'explanation', None) or {}
    return {
        'purpose': _clean((getattr(chart, 'config_json', None) or {}).get('insight') or explanation.get('summary') or getattr(chart, 'title', '')),
        'selected_because': _clean(' / '.join(conf.get('reasons') or guardrail.get('reasons') or []) if (conf.get('reasons') or guardrail.get('reasons')) else 'Matched the current decision story and passed structural checks.'),
        'source_columns': [c for c in [getattr(chart, 'x_axis', ''), getattr(chart, 'y_axis', ''), getattr(chart, 'group_by', ''), (getattr(chart, 'config_json', None) or {}).get('y2_axis', '')] if c],
        'resolved_dimension': _clean(getattr(chart, 'x_axis', '') or render_meta.get('dimension')),
        'resolved_measure': _clean(getattr(chart, 'y_axis', '') or render_meta.get('metric_name')),
        'benchmark_used': _benchmark_label(analysis),
        'time_logic_used': _time_logic(analysis),
        'confidence_label': _clean(conf.get('label') or conf.get('grade')),
        'confidence_score': conf.get('score'),
        'guardrail_result': _clean(guardrail.get('status') or ('accepted' if not guardrail.get('rejected') else 'rejected')),
        'guardrail_reasons': guardrail.get('reasons') or [],
    }


def build_kpi_audit_meta(chart: Any, analysis: Dict[str, Any]) -> Dict[str, Any]:
    render_meta = getattr(chart, 'render_meta', None) or {}
    metric_name = render_meta.get('metric_label') or getattr(chart, 'y_axis', '') or getattr(chart, 'title', '')
    formula = metric_name
    if getattr(chart, 'y_axis', '') == 'achievement_pct':
        formula = 'Actual / Target × 100'
    elif getattr(chart, 'y_axis', '') == 'variance_to_target':
        formula = 'Actual − Target'
    return {
        'metric_name': _clean(metric_name),
        'formula': _clean(formula),
        'benchmark_source': _benchmark_label(analysis),
        'comparison_period': _time_logic(analysis),
        'threshold_logic': _clean(render_meta.get('status_label') or 'Good ≥95%, Warning 80–94%, Critical <80% when target context is available.'),
        'unit': _clean(render_meta.get('metric_type') or render_meta.get('formatter') or 'number'),
        'caveats': build_caveats(analysis)[:3],
    }


def build_caveats(analysis: Dict[str, Any]) -> List[str]:
    caveats: List[str] = []
    summary = (analysis or {}).get('benchmark_summary') or {}
    if not summary:
        caveats.append('No benchmark summary was available, so raw values may be shown without strong context.')
    else:
        kind = summary.get('benchmark_kind') or summary.get('kind')
        if kind in {'average', 'median', 'peer_group'}:
            caveats.append(f'Benchmark context is based on {str(kind).replace("_", " ")}, not a formal target.')
    ti = (analysis or {}).get('time_intelligence') or {}
    if not ti.get('current_period'):
        caveats.append('Time-based comparisons were limited because no stable ordered period could be derived.')
    if ti.get('forecast_hint') and not ti.get('yoy'):
        caveats.append('Forecast hints are based on recent momentum and should be treated as directional only.')
    conf_notes = (analysis or {}).get('confidence_notes') or []
    caveats.extend(conf_notes[:2])
    return caveats


def build_dashboard_audit_meta(upload: Any, analysis: Dict[str, Any], request: Any | None = None, dashboard_mode: str = 'executive') -> Dict[str, Any]:
    profile = _profile(analysis)
    filters = []
    if request is not None:
        for key, value in getattr(request, 'GET', {}).items():
            if value and key not in {'mode'}:
                filters.append(f'{key}={value}')
    return {
        'dataset_filename': getattr(upload, 'original_name', '—'),
        'refresh_timestamp': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'active_filters': filters,
        'drill_state': getattr(request, 'GET', {}).get('drill', '') if request is not None else '',
        'selected_audience': getattr(request, 'GET', {}).get('audience', 'executive') if request is not None else 'executive',
        'selected_mode': dashboard_mode,
        'analysis_type': _analysis_type(analysis),
        'dataset_type': _clean((analysis or {}).get('dataset_domain') or profile.get('dataset_domain') or 'general business'),
        'explanation_domain': _clean((analysis or {}).get('explanation_domain') or profile.get('dataset_domain') or 'general business'),
        'business_roles': _roles(analysis),
        'caveats': build_caveats(analysis),
        'methodology': [
            'Schema normalization was applied before profiling and chart resolution.',
            'Charts were filtered through guardrails, confidence scoring, and decision ranking.',
            'Benchmarks and time intelligence were attached where the dataset supported them.',
        ],
    }


def attach_governance(charts: Iterable[Any], analysis: Dict[str, Any]) -> None:
    for chart in charts:
        audit = build_chart_audit_meta(chart, analysis)
        setattr(chart, 'audit_meta', audit)
        if (getattr(chart, 'chart_type', '') or '').lower() == 'kpi':
            setattr(chart, 'kpi_audit_meta', build_kpi_audit_meta(chart, analysis))


def build_export_governance_block(context: Dict[str, Any]) -> Dict[str, Any]:
    upload = context.get('upload')
    analysis = context.get('analysis') or {}
    audit = build_dashboard_audit_meta(upload, analysis, request=None, dashboard_mode=context.get('mode', 'executive')) if upload is not None else {}
    return {
        'summary_lines': [
            f"Generated: {audit.get('refresh_timestamp', '—')}",
            f"Analysis type: {audit.get('analysis_type', '—')}",
            f"Dataset type: {audit.get('dataset_type', '—')}",
        ],
        'methodology': audit.get('methodology') or [],
        'caveats': audit.get('caveats') or [],
    }
