from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _clamp(v: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, v))


def _grade(score: float) -> str:
    if score >= 0.82:
        return 'high'
    if score >= 0.6:
        return 'medium'
    return 'experimental'


def _reason_list(*pairs: tuple[bool, str]) -> List[str]:
    return [label for ok, label in pairs if ok]


def _chart_data(chart: Any) -> Dict[str, Any]:
    return getattr(chart, 'cached_data', None) or {}


def _chart_type(chart: Any) -> str:
    return (getattr(chart, 'chart_type', '') or _chart_data(chart).get('chart_type') or '').lower()


def compute_chart_confidence(chart: Any, analysis: Dict[str, Any]) -> Dict[str, Any]:
    data = _chart_data(chart)
    labels = data.get('labels') or []
    datasets = data.get('datasets') or []
    ctype = _chart_type(chart)
    profile = (analysis or {}).get('profile_json') or {}
    benchmark_summary = (analysis or {}).get('benchmark_summary') or {}
    time_intelligence = (analysis or {}).get('time_intelligence') or {}

    structural = 0.2
    semantic = 0.4
    benchmark = 0.35
    time_fit = 0.35
    decision = 0.4

    has_labels = isinstance(labels, list) and len(labels) > 0
    has_datasets = isinstance(datasets, list) and len(datasets) > 0
    first_ds = datasets[0] if has_datasets and isinstance(datasets[0], dict) else {}
    values = first_ds.get('data') or []
    value_count = len([v for v in values if v not in (None, '')]) if isinstance(values, list) else 0

    structural = 0.25
    if ctype == 'kpi':
        current_value = _safe_float(data.get('current_value'))
        structural = 0.9 if current_value is not None else 0.35
    elif has_labels and has_datasets and value_count > 0:
        structural = 0.95 if len(labels) == value_count or ctype in {'pie', 'doughnut', 'scatter'} else 0.8
    elif has_labels:
        structural = 0.45

    title = ((getattr(chart, 'title', '') or '') + ' ' + (getattr(chart, 'x_axis', '') or '') + ' ' + (getattr(chart, 'y_axis', '') or '')).lower()
    priorities = (((profile.get('analysis_classification') or {}).get('priorities')) or [])
    semantic = 0.45
    if ctype in {'line', 'area'} and profile.get('time_columns'):
        semantic = 0.9
    elif ctype in {'horizontal_bar', 'bar', 'variance_bar'} and any(k in title for k in ['variance', 'target', 'achievement', 'ranking']):
        semantic = 0.88
    elif ctype == 'kpi':
        semantic = 0.9 if any(k in title for k in ['target', 'achievement', 'variance', 'revenue', 'cost', 'profit']) else 0.72
    elif ctype in {'scatter', 'pie', 'doughnut'}:
        semantic = 0.42
    elif any(p.replace('_', ' ') in title for p in priorities):
        semantic = 0.82

    benchmark = 0.25
    if benchmark_summary.get('label') or benchmark_summary.get('suite'):
        benchmark = 0.85 if ctype == 'kpi' or any(k in title for k in ['target', 'variance', 'achievement']) else 0.6

    time_fit = 0.2
    if profile.get('time_columns'):
        time_fit = 0.8 if ctype in {'line', 'area'} else 0.5
        if time_intelligence.get('comparisons'):
            time_fit += 0.1
        time_fit = _clamp(time_fit)
    else:
        time_fit = 0.65 if ctype not in {'line', 'area'} else 0.3

    raw_decision = getattr(chart, '_decision_score', None)
    if raw_decision is not None:
        decision = _clamp(float(raw_decision) / 120.0)
    elif ctype == 'kpi':
        decision = 0.88
    elif ctype in {'horizontal_bar', 'bar', 'variance_bar', 'line', 'area'}:
        decision = 0.78
    elif ctype in {'scatter', 'pie', 'doughnut'}:
        decision = 0.4

    final = round((structural * 0.34) + (semantic * 0.24) + (benchmark * 0.14) + (time_fit * 0.12) + (decision * 0.16), 3)
    grade = _grade(final)
    reasons = _reason_list(
        (structural >= 0.8, 'structurally strong'),
        (semantic >= 0.8, 'good intent fit'),
        (benchmark >= 0.7, 'has benchmark context'),
        (time_fit >= 0.75, 'time-aware'),
        (decision >= 0.75, 'high decision value'),
        (grade == 'experimental', 'weak evidence'),
    )
    return {
        'structural_confidence': round(structural, 3),
        'semantic_confidence': round(semantic, 3),
        'benchmark_confidence': round(benchmark, 3),
        'time_confidence': round(time_fit, 3),
        'decision_value': round(decision, 3),
        'final_confidence': final,
        'grade': grade,
        'label': 'High confidence' if grade == 'high' else 'Medium confidence' if grade == 'medium' else 'Experimental insight',
        'reasons': reasons,
        'suppress_by_default': grade == 'experimental',
    }


def compute_explanation_confidence(chart: Any, analysis: Dict[str, Any]) -> Dict[str, Any]:
    explanation = getattr(chart, 'explanation', None) or {}
    chart_conf = getattr(chart, 'confidence_meta', None) or compute_chart_confidence(chart, analysis)
    profile = (analysis or {}).get('profile_json') or {}
    benchmark_summary = (analysis or {}).get('benchmark_summary') or {}
    time_intelligence = (analysis or {}).get('time_intelligence') or {}

    evidence_count = sum(1 for key in ('summary', 'why_it_matters', 'how_to_read', 'next_action') if explanation.get(key))
    base = 0.25 + (0.15 * evidence_count)

    domain_fit = 0.85 if (analysis or {}).get('screening_json', {}).get('analysis_type') or (profile.get('analysis_classification') or {}).get('analysis_type') else 0.55
    benchmark_fit = 0.8 if benchmark_summary.get('label') or benchmark_summary.get('suite') else 0.45
    time_fit = 0.78 if profile.get('time_columns') and time_intelligence else 0.58

    final = round(_clamp((base * 0.34) + (chart_conf.get('final_confidence', 0.5) * 0.28) + (domain_fit * 0.16) + (benchmark_fit * 0.12) + (time_fit * 0.10)), 3)
    grade = _grade(final)
    return {
        'evidence_count': evidence_count,
        'domain_fit_confidence': round(domain_fit, 3),
        'benchmark_fit_confidence': round(benchmark_fit, 3),
        'time_fit_confidence': round(time_fit, 3),
        'final_confidence': final,
        'grade': grade,
        'label': 'High confidence' if grade == 'high' else 'Medium confidence' if grade == 'medium' else 'Experimental insight',
        'show_experimental_badge': grade == 'experimental',
    }


def attach_confidence(charts: Iterable[Any], analysis: Dict[str, Any]) -> None:
    for chart in charts:
        cmeta = compute_chart_confidence(chart, analysis)
        setattr(chart, 'confidence_meta', cmeta)
        emeta = compute_explanation_confidence(chart, analysis)
        setattr(chart, 'explanation_confidence_meta', emeta)
