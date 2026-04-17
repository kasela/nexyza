from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from .dataset_explanation_profiles import get_explanation_profile


def _safe_float(value: Any) -> Optional[float]:
    try:
        if value is None or value == '':
            return None
        return float(value)
    except Exception:
        return None


def _fmt_number(value: Any, digits: int = 1) -> str:
    v = _safe_float(value)
    if v is None:
        return '—'
    sign = '-' if v < 0 else ''
    v = abs(v)
    if v >= 1_000_000_000:
        return f"{sign}{v/1_000_000_000:.{digits}f}B"
    if v >= 1_000_000:
        return f"{sign}{v/1_000_000:.{digits}f}M"
    if v >= 1_000:
        return f"{sign}{v/1_000:.{digits}f}K"
    if float(v).is_integer():
        return f"{sign}{int(v):,}"
    return f"{sign}{v:,.{digits}f}"


def _fmt_pct(value: Any, digits: int = 2) -> str:
    v = _safe_float(value)
    return '—' if v is None else f"{v:.{digits}f}%"


def _comparison_sentence(data: Dict[str, Any]) -> str:
    comp = data.get('comparison') or {}
    variance = comp.get('variance_value')
    variance_direction = comp.get('variance_direction') or ''
    target_value = comp.get('target_value')
    current_value = data.get('current_value')
    current_label = data.get('current_label') or data.get('y_label') or data.get('title') or 'current value'
    current_fmt = _fmt_number(current_value)
    target_fmt = _fmt_number(target_value)
    variance_fmt = _fmt_number(variance)
    if target_value is not None and variance is not None:
        direction_word = 'above' if variance_direction == 'positive' else 'below' if variance_direction == 'negative' else 'against'
        return f"{current_label} is {current_fmt}, {direction_word} target by {variance_fmt} against {target_fmt}."
    if target_value is not None:
        return f"{current_label} is {current_fmt} against a target of {target_fmt}."
    return f"{current_label} is currently {current_fmt}."


def _find_extreme(records: List[Dict[str, Any]], metric_key: str, highest: bool = True) -> Optional[Dict[str, Any]]:
    filtered = [r for r in records if _safe_float(r.get(metric_key)) is not None]
    if not filtered:
        return None
    return max(filtered, key=lambda r: _safe_float(r.get(metric_key)) or 0) if highest else min(filtered, key=lambda r: _safe_float(r.get(metric_key)) or 0)


def _derive_title_focus(chart: Any, data: Dict[str, Any]) -> str:
    return getattr(chart, 'title', '') or data.get('title') or data.get('y_label') or 'This chart'

def _contextual_action(analysis: Dict[str, Any], fallback: str) -> str:
    profile = get_explanation_profile(analysis)
    return profile.get("action_text") or fallback


def _metric_noun(analysis: Dict[str, Any], fallback: str) -> str:
    profile = get_explanation_profile(analysis)
    return (profile.get("nouns") or {}).get("metric") or fallback


def _entity_noun(analysis: Dict[str, Any], fallback: str) -> str:
    profile = get_explanation_profile(analysis)
    return (profile.get("nouns") or {}).get("entity") or fallback


def _build_kpi_explanation(chart: Any, data: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, str]:
    summary = _comparison_sentence(data)
    measure = (getattr(chart, 'y_axis', '') or data.get('y_label') or 'metric').replace('_', ' ')
    why = f"Use this KPI to check whether {_metric_noun(analysis, measure.lower())} is on track before reviewing detailed breakdowns."
    next_step = "If this is behind plan, open the top-ranked variance or trend chart next."
    if 'achievement' in measure.lower() and '%' in summary:
        next_step = _contextual_action(analysis, "If this rate is weak, compare the worst segments and review the time trend for persistent slippage.")
    return {
        'summary': summary,
        'why_it_matters': why,
        'how_to_read': 'Read the headline value first, then compare it with the benchmark chip or target reference.',
        'next_action': _contextual_action(analysis, next_step),
    }


def _build_time_explanation(chart: Any, data: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, str]:
    labels = data.get('labels') or []
    datasets = data.get('datasets') or []
    first_ds = datasets[0] if datasets else {}
    values = first_ds.get('data') or []
    start = _safe_float(values[0]) if values else None
    end = _safe_float(values[-1]) if values else None
    delta_text = ''
    if start is not None and end is not None:
        delta = end - start
        delta_text = f" It moved from {_fmt_number(start)} to {_fmt_number(end)} across the visible period."
    label_span = f" over {len(labels)} periods" if labels else ''
    summary = f"{_derive_title_focus(chart, data)} shows the direction of change{label_span}.{delta_text}".strip()
    return {
        'summary': summary,
        'why_it_matters': f"Trend views show whether {_metric_noun(analysis, 'the result')} is improving, deteriorating, or staying volatile over time.",
        'how_to_read': 'Read the overall direction first, then look for sudden drops, recoveries, or repeated misses against the comparison line.',
        'next_action': _contextual_action(analysis, 'If the line is unstable or below plan, drill into the worst contributing dimension such as branch, region, or manager.'),
    }


def _build_ranking_explanation(chart: Any, data: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, str]:
    labels = data.get('labels') or []
    datasets = data.get('datasets') or []
    values = (datasets[0] or {}).get('data') or []
    pairs = [(labels[i], _safe_float(values[i])) for i in range(min(len(labels), len(values)))]
    pairs = [(k, v) for k, v in pairs if v is not None]
    pairs.sort(key=lambda x: x[1], reverse=True)
    top_text = ''
    if pairs:
        leader, leader_val = pairs[0]
        tail, tail_val = pairs[-1]
        top_text = f" {leader} leads at {_fmt_number(leader_val)}, while {tail} sits at {_fmt_number(tail_val)}."
    metric = getattr(chart, 'y_axis', '') or data.get('y_label') or 'the metric'
    return {
        'summary': f"{_derive_title_focus(chart, data)} ranks {_entity_noun(analysis, 'entities')} by {metric}.{top_text}".strip(),
        'why_it_matters': f"Ranking views make it easy to see which {_entity_noun(analysis, 'segments')} need management attention, coaching, or replication first.",
        'how_to_read': 'Compare the spread between the top and bottom items, then focus on the bottom cluster rather than single isolated points.',
        'next_action': _contextual_action(analysis, 'Use the leaders as benchmarks and drill into the laggards to find recurring operational or commercial issues.'),
    }


def _build_variance_explanation(chart: Any, data: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, str]:
    records = (((analysis or {}).get('profile_json') or {}).get('derived_metrics') or {}).get('records') or []
    low = _find_extreme(records, 'variance_to_target', highest=False)
    summary = 'Variance highlights how far results sit above or below benchmark.'
    if low:
        summary = f"The sharpest negative variance belongs to {low.get('dimension_value')} at {_fmt_number(low.get('variance_to_target'))}."
    return {
        'summary': summary,
        'why_it_matters': f"Variance is the clearest bridge between {_metric_noun(analysis, 'performance')} and action because it quantifies the size of the gap.",
        'how_to_read': 'Negative bars signal under-delivery; positive bars indicate segments outperforming benchmark or plan.',
        'next_action': _contextual_action(analysis, 'Prioritise the deepest negative gaps first, then compare them with the strongest positive segments.'),
    }


def _build_scatter_explanation(chart: Any, data: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, str]:
    x_label = data.get('x_label') or getattr(chart, 'x_axis', '') or 'X'
    y_label = data.get('y_label') or getattr(chart, 'y_axis', '') or 'Y'
    return {
        'summary': f"{_derive_title_focus(chart, data)} tests the relationship between {x_label} and {y_label}.",
        'why_it_matters': 'Relationship views help separate structural drivers from random noise and reveal outliers worth investigating.',
        'how_to_read': 'Look for tight clustering, upward or downward slope, and points far away from the main cloud.',
        'next_action': _contextual_action(analysis, 'Investigate outliers first because they often explain the most important operational differences.'),
    }


def _build_generic_explanation(chart: Any, data: Dict[str, Any], analysis: Dict[str, Any]) -> Dict[str, str]:
    return {
        'summary': f"{_derive_title_focus(chart, data)} provides supporting context for the broader decision story.",
        'why_it_matters': 'Use this view after the headline KPIs and main ranking/trend charts, not before them.',
        'how_to_read': 'Read the largest visible differences first, then confirm them against the relevant benchmark or prior period.',
        'next_action': _contextual_action(analysis, 'Only act on this chart if it changes the priority set by the main executive signals.'),
    }


def explain_chart(chart: Any, analysis: Dict[str, Any]) -> Dict[str, str]:
    data = getattr(chart, 'cached_data', None) or {}
    ctype = (getattr(chart, 'chart_type', '') or data.get('chart_type') or '').lower()
    if ctype == 'kpi' or data.get('kpi'):
        return _build_kpi_explanation(chart, data, analysis)
    if ctype in {'line', 'area'}:
        return _build_time_explanation(chart, data, analysis)
    if ctype in {'horizontal_bar', 'bar', 'pareto', 'waterfall', 'progress_ring'}:
        return _build_ranking_explanation(chart, data, analysis)
    if ctype in {'variance_bar'} or 'variance' in (getattr(chart, 'title', '') or '').lower():
        return _build_variance_explanation(chart, data, analysis)
    if ctype in {'scatter', 'bubble'}:
        return _build_scatter_explanation(chart, data, analysis)
    return _build_generic_explanation(chart, data, analysis)


def explain_narrative_cards(decision_cards: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    enriched: List[Dict[str, Any]] = []
    for card in decision_cards or []:
        label = (card.get('label') or 'Signal').lower()
        body = card.get('body') or ''
        action = card.get('action') or ''
        why = 'This card surfaces an issue that should influence which charts are reviewed first.'
        if 'problem' in label or 'risk' in label:
            why = 'This is a priority because it represents downside risk, missed target, or concentrated operational pressure.'
        elif 'opportunity' in label:
            why = 'This matters because it shows where winning patterns can be replicated across weaker segments.'
        elif 'observation' in label or 'priority' in label:
            why = 'This card summarises the main story so the dashboard starts with decision context rather than raw visuals.'
        enriched.append({**card, 'why_it_matters': why, 'recommended_read': action or body})
    return enriched


def attach_explanations(charts: Iterable[Any], analysis: Dict[str, Any]) -> None:
    for chart in charts or []:
        setattr(chart, 'explanation', explain_chart(chart, analysis))
