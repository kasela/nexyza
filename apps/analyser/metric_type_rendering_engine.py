from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional


@dataclass
class MetricRenderMeta:
    metric_type: str = 'number'
    unit: str = ''
    unit_position: str = 'suffix'
    decimals: int = 1
    palette_hint: str = 'slate'
    semantic_direction: str = 'neutral'
    benchmark_label: str = ''
    benchmark_value: str = ''
    status: str = 'context'
    status_label: str = 'Context'
    formatter: str = 'number'
    comparison_formatter: str = 'number'
    compact_note: str = ''

    def as_dict(self) -> Dict[str, Any]:
        return {
            'metric_type': self.metric_type,
            'unit': self.unit,
            'unit_position': self.unit_position,
            'decimals': self.decimals,
            'palette_hint': self.palette_hint,
            'semantic_direction': self.semantic_direction,
            'benchmark_label': self.benchmark_label,
            'benchmark_value': self.benchmark_value,
            'status': self.status,
            'status_label': self.status_label,
            'formatter': self.formatter,
            'comparison_formatter': self.comparison_formatter,
            'compact_note': self.compact_note,
        }


def _profile(analysis: Dict[str, Any]) -> Dict[str, Any]:
    return (analysis or {}).get('profile_json') or {}


def _screening(analysis: Dict[str, Any]) -> Dict[str, Any]:
    return (analysis or {}).get('screening_json') or {}


def _safe_float(value: Any) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def _format_compact(value: Any, decimals: int = 1) -> str:
    num = _safe_float(value)
    if num is None:
        return '—'
    sign = '-' if num < 0 else ''
    num = abs(num)
    if num >= 1_000_000_000:
        return f"{sign}{num/1_000_000_000:.{decimals}f}B"
    if num >= 1_000_000:
        return f"{sign}{num/1_000_000:.{decimals}f}M"
    if num >= 1_000:
        return f"{sign}{num/1_000:.{decimals}f}K"
    if float(num).is_integer():
        return f"{sign}{num:,.0f}"
    return f"{sign}{num:,.{decimals}f}"


def _format_percent(value: Any, decimals: int = 1) -> str:
    num = _safe_float(value)
    if num is None:
        return '—'
    return f"{num:.{decimals}f}%"


def _label_metric_type(label: str, semantic_type: str = '', metric_key: str = '') -> MetricRenderMeta:
    token = ' '.join([label or '', semantic_type or '', metric_key or '']).lower()
    if '%' in token or 'percent' in token or 'ratio' in token or metric_key.endswith('_pct'):
        return MetricRenderMeta(metric_type='percentage', unit='%', decimals=1, palette_hint='emerald', semantic_direction='higher_is_better', formatter='percent', comparison_formatter='percent_delta')
    if 'currency' in token or 'amount' in token or 'revenue' in token or 'sales' in token or 'cost' in token or 'expense' in token or 'price' in token or 'target' in token or 'actual' in token or 'variance' in token:
        return MetricRenderMeta(metric_type='currency', unit='', decimals=1, palette_hint='violet' if 'variance' not in token else 'rose', semantic_direction='higher_is_better' if 'variance' not in token else 'mixed', formatter='compact', comparison_formatter='compact_delta')
    if 'count' in token or 'volume' in token or 'tickets' in token or 'units' in token or 'orders' in token:
        return MetricRenderMeta(metric_type='count', unit='', decimals=0, palette_hint='cyan', semantic_direction='higher_is_better', formatter='integer', comparison_formatter='integer_delta')
    if 'day' in token or 'duration' in token or 'hours' in token or 'minutes' in token:
        return MetricRenderMeta(metric_type='duration', unit='days' if 'day' in token else 'hrs', unit_position='suffix', decimals=1, palette_hint='amber', semantic_direction='lower_is_better', formatter='number', comparison_formatter='number_delta')
    return MetricRenderMeta(metric_type='number', unit='', decimals=1, palette_hint='slate', semantic_direction='neutral', formatter='number', comparison_formatter='number_delta')


def _build_column_index(analysis: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    profile = _profile(analysis)
    index: Dict[str, Dict[str, Any]] = {}
    for col in profile.get('column_profiles') or []:
        name = str(col.get('name') or '')
        if name:
            index[name.lower()] = col
            canonical = str(col.get('canonical_name') or '')
            if canonical:
                index[canonical.lower()] = col
    labels = (((profile.get('derived_metrics') or {}).get('labels')) or {})
    semantic_types = (((profile.get('derived_metrics') or {}).get('semantic_types')) or {})
    for key, label in labels.items():
        index[str(key).lower()] = {
            'name': label,
            'semantic_type': semantic_types.get(key) or '',
            'role': 'derived',
        }
        index[str(label).lower()] = index[str(key).lower()]
    return index


def _metric_meta_for_chart(chart: Any, analysis: Dict[str, Any]) -> MetricRenderMeta:
    column_index = _build_column_index(analysis)
    screening = _screening(analysis)
    roles = screening.get('business_roles') or (_profile(analysis).get('business_roles') or {})
    derived = screening.get('derived_metrics') or (_profile(analysis).get('derived_metrics') or {})
    y_axis = getattr(chart, 'y_axis', '') or ''
    title = getattr(chart, 'title', '') or ''
    lower_key = str(y_axis).lower()
    lower_title = title.lower()
    col = column_index.get(lower_key) or column_index.get(lower_title)
    semantic = (col or {}).get('semantic_type') or ''
    name = (col or {}).get('name') or y_axis or title
    meta = _label_metric_type(name, semantic_type=semantic, metric_key=lower_key)

    if lower_key in {'variance_to_target'} or 'variance' in lower_key or 'variance' in lower_title:
        meta.metric_type = 'variance'
        meta.palette_hint = 'rose'
        meta.semantic_direction = 'mixed'
        meta.formatter = 'compact'
        meta.comparison_formatter = 'compact_delta'
    elif lower_key in {'achievement_pct'} or 'attainment' in lower_title:
        meta.metric_type = 'percentage'
        meta.palette_hint = 'emerald'
        meta.semantic_direction = 'higher_is_better'
        meta.formatter = 'percent'
        meta.comparison_formatter = 'percent_delta'

    if getattr(chart, 'chart_type', '') == 'kpi':
        comparison = (getattr(chart, 'cached_data', {}) or {}).get('comparison') or {}
        benchmark_label = ''
        benchmark_value = ''
        status = 'context'
        status_label = 'Context'
        if comparison.get('target_value') not in (None, '', '—'):
            benchmark_label = 'Target'
            benchmark_value = str(comparison.get('target_value'))
            pct = _safe_float(comparison.get('attainment_pct') or comparison.get('achievement_pct'))
            if pct is not None:
                if pct >= 95:
                    status, status_label = 'good', 'On track'
                elif pct >= 80:
                    status, status_label = 'warning', 'Watch'
                else:
                    status, status_label = 'critical', 'Behind'
        elif comparison.get('prior_value') not in (None, '', '—'):
            benchmark_label = 'Previous period'
            benchmark_value = str(comparison.get('prior_value'))
            status, status_label = 'context', 'Trend'

        summary = (analysis or {}).get('benchmark_summary') or {}
        suite = summary.get('suite') or {}
        preferred = summary.get('mode') or next(iter(suite.keys()), '')
        preferred_summary = suite.get(preferred) or summary
        if not benchmark_label and preferred_summary.get('benchmark_value') not in (None, '', '—', 0):
            benchmark_label = str(preferred_summary.get('label') or 'Benchmark')
            benchmark_value = _format_compact(preferred_summary.get('benchmark_value'), decimals=1)
            variance_pct = _safe_float(preferred_summary.get('variance_pct'))
            if variance_pct is not None:
                pct = (1 + variance_pct) * 100
                if pct >= 95:
                    status, status_label = 'good', 'On track'
                elif pct >= 80:
                    status, status_label = 'warning', 'Watch'
                else:
                    status, status_label = 'critical', 'Behind'

        if not benchmark_label and roles.get('target_column') and str(y_axis).lower() == str(roles.get('actual_column') or '').lower():
            benchmark_label = str(roles.get('target_column'))
            benchmark_value = 'Available'

        meta.benchmark_label = benchmark_label
        meta.benchmark_value = benchmark_value
        meta.status = status
        meta.status_label = status_label

        summaries = derived.get('summaries') or {}
        if lower_key in summaries:
            summary = summaries.get(lower_key) or {}
            if summary.get('semantic_type') == 'ratio':
                meta.metric_type = 'percentage' if 'pct' in lower_key else 'ratio'
                meta.formatter = 'percent' if 'pct' in lower_key else 'number'
            if not meta.compact_note and summary.get('mean') is not None:
                meta.compact_note = f"Mean {_format_percent(summary['mean']) if meta.formatter == 'percent' else _format_compact(summary['mean'])}"

    return meta


def attach_metric_rendering(charts: Iterable[Any], analysis: Dict[str, Any]) -> None:
    for chart in charts:
        meta = _metric_meta_for_chart(chart, analysis)
        setattr(chart, 'render_meta', meta.as_dict())
