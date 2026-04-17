from __future__ import annotations

from typing import Any, Dict, List, Optional
import math
import re


def _canon(text: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text or "").strip().lower()).strip("_")


ROLE_HINTS: Dict[str, tuple[str, ...]] = {
    'target': ('target', 'budget', 'plan', 'goal', 'quota', 'benchmark'),
    'actual': ('actual', 'achievement', 'achivement', 'sales', 'revenue', 'income', 'turnover', 'value', 'amount'),
    'cost': ('cost', 'expense', 'spend', 'purchase', 'purchasing', 'procurement', 'cogs'),
    'profit': ('profit', 'margin', 'gp', 'gross_profit', 'net_profit'),
    'opening_stock': ('opening_stock', 'opening_inventory', 'opening_balance', 'opening_bal', 'begin_stock'),
    'closing_stock': ('closing_stock', 'ending_stock', 'ending_inventory', 'closing_balance', 'closing_bal', 'end_stock'),
    'count': ('count', 'qty', 'quantity', 'units', 'volume', 'visits', 'orders'),
}

DIMENSION_PRIORITY_HINTS = (
    'branch', 'store', 'outlet', 'location', 'region', 'manager', 'category', 'segment', 'department', 'province', 'area', 'cluster'
)


def _first_matching(columns: List[str], hints: tuple[str, ...]) -> Optional[str]:
    for col in columns:
        canon = _canon(col)
        if any(h in canon for h in hints):
            return col
    return None


def _safe_float(value: Any) -> Optional[float]:
    if value in (None, ''):
        return None
    try:
        if isinstance(value, str):
            value = value.replace(',', '').strip()
        v = float(value)
        if math.isnan(v) or math.isinf(v):
            return None
        return v
    except Exception:
        return None


def _safe_round(value: Optional[float], digits: int = 2) -> Optional[float]:
    if value is None:
        return None
    try:
        return round(float(value), digits)
    except Exception:
        return None


def _build_preview_records(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    preview_cols = profile.get('preview_columns') or []
    preview_rows = ((profile.get('preview') or {}).get('rows') or [])
    if not preview_cols or not preview_rows:
        return []
    out: List[Dict[str, Any]] = []
    for row in preview_rows[:300]:
        if not isinstance(row, list):
            continue
        rec = {col: row[idx] if idx < len(row) else None for idx, col in enumerate(preview_cols)}
        out.append(rec)
    return out


def detect_measure_roles(profile: Dict[str, Any]) -> Dict[str, Optional[str]]:
    measures = list(profile.get('measures') or [])
    dimensions = list(profile.get('dimensions') or [])
    time_columns = list(profile.get('time_columns') or [])

    roles: Dict[str, Optional[str]] = {
        'primary_dimension': None,
        'secondary_dimension': None,
        'primary_time_column': time_columns[0] if time_columns else None,
        'target_column': None,
        'actual_column': None,
        'cost_column': None,
        'profit_column': None,
        'opening_stock_column': None,
        'closing_stock_column': None,
        'volume_column': None,
        'primary_measure': measures[0] if measures else None,
        'secondary_measure': measures[1] if len(measures) > 1 else None,
    }

    for role_name, hints in ROLE_HINTS.items():
        match = _first_matching(measures, hints)
        if role_name == 'cost':
            roles['cost_column'] = match
        elif role_name == 'profit':
            roles['profit_column'] = match
        elif role_name == 'count':
            roles['volume_column'] = match
        else:
            key = f'{role_name}_column'
            if key in roles:
                roles[key] = match

    # Promote actual/target if semantic lists already captured them.
    actual_columns = list(profile.get('actual_columns') or [])
    target_columns = list(profile.get('target_columns') or [])
    if actual_columns:
        roles['actual_column'] = actual_columns[0]
    if target_columns:
        roles['target_column'] = target_columns[0]

    dim_order: List[str] = []
    for hint in DIMENSION_PRIORITY_HINTS:
        for dim in dimensions:
            if dim not in dim_order and hint in _canon(dim):
                dim_order.append(dim)
    for dim in dimensions:
        if dim not in dim_order:
            dim_order.append(dim)
    if dim_order:
        roles['primary_dimension'] = dim_order[0]
    if len(dim_order) > 1:
        roles['secondary_dimension'] = dim_order[1]

    # Better primary/secondary measures from detected roles.
    preferred_measure_order = [
        roles.get('actual_column'),
        roles.get('target_column'),
        roles.get('profit_column'),
        roles.get('cost_column'),
        roles.get('volume_column'),
    ]
    ordered_measures: List[str] = []
    for item in preferred_measure_order + measures:
        if item and item in measures and item not in ordered_measures:
            ordered_measures.append(item)
    if ordered_measures:
        roles['primary_measure'] = ordered_measures[0]
    if len(ordered_measures) > 1:
        roles['secondary_measure'] = ordered_measures[1]

    return roles


def detect_primary_intents(profile: Dict[str, Any], roles: Dict[str, Optional[str]]) -> List[str]:
    measures = list(profile.get('measures') or [])
    dims = list(profile.get('dimensions') or [])
    times = list(profile.get('time_columns') or [])
    opportunities = (profile.get('pattern_profile') or {}).get('opportunities') or []

    ranked = [o.get('intent') for o in sorted(opportunities, key=lambda x: x.get('priority', 0), reverse=True) if o.get('intent')]
    intents: List[str] = []

    if roles.get('target_column') and roles.get('actual_column'):
        intents += ['target_vs_actual', 'variance']
    if times and measures:
        intents += ['trend']
    if dims and measures:
        intents += ['ranking', 'comparison']
    if len(dims) >= 2 and measures:
        intents += ['composition']
    if len(measures) >= 2:
        intents += ['distribution']
    if len(measures) >= 2 and (profile.get('correlation') or {}).get('matrix'):
        intents += ['correlation']
    if roles.get('opening_stock_column') and roles.get('closing_stock_column'):
        intents += ['inventory']
    if roles.get('cost_column') and roles.get('profit_column'):
        intents += ['profitability']

    intents += ranked

    out: List[str] = []
    for intent in intents:
        if intent and intent not in out:
            out.append(intent)
    return out[:6]


def derive_generic_metrics(profile: Dict[str, Any], roles: Dict[str, Optional[str]]) -> Dict[str, Any]:
    records: List[Dict[str, Any]] = []
    metric_labels: Dict[str, str] = {}
    metric_types: Dict[str, str] = {}
    summaries: Dict[str, Dict[str, Any]] = {}
    source_records = _build_preview_records(profile)

    dim = roles.get('primary_dimension')
    measures = list(profile.get('measures') or [])
    actual = roles.get('actual_column')
    target = roles.get('target_column')
    cost = roles.get('cost_column')
    profit = roles.get('profit_column')
    opening = roles.get('opening_stock_column')
    closing = roles.get('closing_stock_column')

    if not source_records:
        return {
            'available': [],
            'labels': {},
            'semantic_types': {},
            'summaries': {},
            'records': [],
        }

    derived_names: List[str] = []
    _is_stats_export = any('stats_export' in f for f in (profile.get('quality_flags') or []))
    # Skip pairwise fallback when real business-role derived metrics can be computed.
    # Pairwise of e.g. "Total Revenue" × "Unit Cost" is cross-scale and meaningless;
    # the role-specific metrics (profit_margin_pct, actual_to_cost_ratio, etc.) are better.
    _has_role_derived = bool(
        (actual and target) or
        (actual and cost) or
        (actual and profit) or
        (opening and closing)
    )

    for rec in source_records:
        item: Dict[str, Any] = {}
        if dim:
            item['dimension_value'] = rec.get(dim)

        measure_values: Dict[str, Optional[float]] = {}
        for measure in measures:
            f = _safe_float(rec.get(measure))
            measure_values[measure] = f
            item[f'{_canon(measure)}_value'] = f

        if actual and target and measure_values.get(actual) is not None and measure_values.get(target) not in (None, 0):
            item['achievement_pct'] = _safe_round((measure_values[actual] / measure_values[target]) * 100, 2)
            item['variance_to_target'] = _safe_round(measure_values[actual] - measure_values[target], 2)
            metric_labels.setdefault('achievement_pct', 'Achievement %')
            metric_labels.setdefault('variance_to_target', 'Variance to Target')
            metric_types['achievement_pct'] = 'ratio'
            metric_types['variance_to_target'] = 'metric'
            derived_names += ['achievement_pct', 'variance_to_target']

        if cost and actual and measure_values.get(cost) not in (None, 0) and measure_values.get(actual) is not None:
            item['actual_to_cost_ratio'] = _safe_round(measure_values[actual] / measure_values[cost], 4)
            item['cost_gap'] = _safe_round(measure_values[actual] - measure_values[cost], 2)
            metric_labels.setdefault('actual_to_cost_ratio', f'{actual} to {cost} Ratio')
            metric_labels.setdefault('cost_gap', f'{actual} minus {cost}')
            metric_types['actual_to_cost_ratio'] = 'ratio'
            metric_types['cost_gap'] = 'metric'
            derived_names += ['actual_to_cost_ratio', 'cost_gap']

        if profit and actual and measure_values.get(actual) not in (None, 0) and measure_values.get(profit) is not None:
            item['profit_margin_pct'] = _safe_round((measure_values[profit] / measure_values[actual]) * 100, 2)
            metric_labels.setdefault('profit_margin_pct', 'Profit Margin %')
            metric_types['profit_margin_pct'] = 'ratio'
            derived_names.append('profit_margin_pct')

        if opening and closing and measure_values.get(opening) is not None and measure_values.get(closing) is not None:
            avg_stock = (measure_values[opening] + measure_values[closing]) / 2 if (measure_values[opening] + measure_values[closing]) != 0 else None
            item['stock_movement'] = _safe_round(measure_values[closing] - measure_values[opening], 2)
            item['average_stock'] = _safe_round(avg_stock, 2)
            metric_labels.setdefault('stock_movement', 'Stock Movement')
            metric_labels.setdefault('average_stock', 'Average Stock')
            metric_types['stock_movement'] = 'metric'
            metric_types['average_stock'] = 'metric'
            derived_names += ['stock_movement', 'average_stock']
            if actual and avg_stock and measure_values.get(actual) is not None:
                item['stock_turnover'] = _safe_round(measure_values[actual] / avg_stock, 4)
                metric_labels.setdefault('stock_turnover', 'Stock Turnover')
                metric_types['stock_turnover'] = 'ratio'
                derived_names.append('stock_turnover')

        # generic pairwise fallback — skip when real business-role metrics were
        # computed (prevents cross-scale comparisons like "Revenue ÷ Unit Cost"),
        # and skip entirely for stats-export CSVs.
        if not _is_stats_export and not _has_role_derived:
            pair_pool = measures[:3]
            for idx, left in enumerate(pair_pool):
                for right in pair_pool[idx + 1:]:
                    left_v = measure_values.get(left)
                    right_v = measure_values.get(right)
                    if left_v is None or right_v is None:
                        continue
                    diff_key = f'{_canon(left)}_minus_{_canon(right)}'
                    if diff_key not in item:
                        item[diff_key] = _safe_round(left_v - right_v, 2)
                        metric_labels.setdefault(diff_key, f'{left} minus {right}')
                        metric_types[diff_key] = 'metric'
                        derived_names.append(diff_key)
                    if right_v not in (None, 0):
                        ratio_key = f'{_canon(left)}_to_{_canon(right)}_ratio'
                        if ratio_key not in item:
                            item[ratio_key] = _safe_round(left_v / right_v, 4)
                            metric_labels.setdefault(ratio_key, f'{left} to {right} Ratio')
                            metric_types[ratio_key] = 'ratio'
                            derived_names.append(ratio_key)

        records.append(item)

    available = []
    for metric_name in derived_names:
        if metric_name not in available:
            values = [r.get(metric_name) for r in records if r.get(metric_name) is not None]
            if values:
                available.append(metric_name)
                digits = 4 if metric_types.get(metric_name) == 'ratio' and any(abs(v) < 10 for v in values) else 2
                summaries[metric_name] = {
                    'label': metric_labels.get(metric_name, metric_name.replace('_', ' ').title()),
                    'semantic_type': metric_types.get(metric_name, 'metric'),
                    'min': _safe_round(min(values), digits),
                    'max': _safe_round(max(values), digits),
                    'mean': _safe_round(sum(values) / len(values), digits),
                }

    return {
        'available': available,
        'labels': {k: metric_labels[k] for k in available if k in metric_labels},
        'semantic_types': {k: metric_types.get(k, 'metric') for k in available},
        'summaries': summaries,
        'records': records[:120],
    }


def classify_dataset(profile: Dict[str, Any], roles: Dict[str, Optional[str]], intents: List[str]) -> Dict[str, Any]:
    measures = list(profile.get('measures') or [])
    dims = list(profile.get('dimensions') or [])
    times = list(profile.get('time_columns') or [])

    analysis_type = 'general_analysis'
    confidence = 0.62
    reason = 'General dataset with reusable analytical opportunities detected.'

    if roles.get('target_column') and roles.get('actual_column') and times:
        analysis_type = 'performance_time_series'
        confidence = 0.93
        reason = 'Target and actual measures with time context indicate a performance time-series dataset.'
    elif roles.get('target_column') and roles.get('actual_column'):
        analysis_type = 'performance_analysis'
        confidence = 0.91
        reason = 'Target and actual measures indicate a performance-analysis dataset.'
    elif times and measures:
        analysis_type = 'trend_analysis'
        confidence = 0.82
        reason = 'Time columns with measures indicate a trend-analysis dataset.'
    elif 'composition' in intents and dims and measures:
        analysis_type = 'composition_analysis'
        confidence = 0.76
        reason = 'Dimension-heavy dataset suggests composition and contribution analysis.'
    elif 'correlation' in intents and len(measures) >= 2:
        analysis_type = 'relationship_analysis'
        confidence = 0.74
        reason = 'Multiple measures suggest relationship analysis.'

    priorities = []
    for intent in intents:
        mapped = {
            'target_vs_actual': 'target_vs_actual',
            'variance': 'variance',
            'trend': 'trend',
            'ranking': 'ranking',
            'comparison': 'comparison',
            'composition': 'contribution',
            'inventory': 'inventory_efficiency',
            'correlation': 'correlation',
            'distribution': 'distribution',
            'profitability': 'profitability',
        }.get(intent)
        if mapped and mapped not in priorities:
            priorities.append(mapped)

    return {
        'analysis_type': analysis_type,
        'confidence': confidence,
        'reason': reason,
        'priorities': priorities[:6] or ['comparison', 'ranking'],
        'primary_measure': roles.get('primary_measure') or (measures[0] if measures else ''),
        'secondary_measure': roles.get('secondary_measure') or (measures[1] if len(measures) > 1 else ''),
        'primary_dimension': roles.get('primary_dimension') or (dims[0] if dims else ''),
        'primary_time_column': roles.get('primary_time_column') or (times[0] if times else ''),
        'primary_target_column': roles.get('target_column') or '',
    }


def build_universal_business_insights(profile: Dict[str, Any], roles: Dict[str, Optional[str]], derived: Dict[str, Any], classification: Dict[str, Any]) -> Dict[str, Any]:
    records = list(derived.get('records') or [])
    labels = derived.get('labels') or {}
    insights: Dict[str, Any] = {
        'analysis_goal': classification.get('analysis_type') or 'general_analysis',
        'top_performers': [],
        'underperformers': [],
        'over_target': [],
        'under_target': [],
        'kpi_summary': {},
        'inventory_alerts': [],
        'narrative_points': [],
        'top_exceptions': [],
    }

    actual = roles.get('actual_column')
    target = roles.get('target_column')
    if actual:
        total_actual = sum((r.get(f'{_canon(actual)}_value') or 0) for r in records)
        insights['kpi_summary']['total_primary_measure'] = _safe_round(total_actual, 2)
    if target:
        total_target = sum((r.get(f'{_canon(target)}_value') or 0) for r in records)
        insights['kpi_summary']['total_target'] = _safe_round(total_target, 2)

    if 'achievement_pct' in derived.get('available', []):
        perf = [r for r in records if r.get('achievement_pct') is not None and r.get('dimension_value')]
        perf.sort(key=lambda r: r['achievement_pct'], reverse=True)
        insights['top_performers'] = [r['dimension_value'] for r in perf[:3]]
        insights['underperformers'] = [r['dimension_value'] for r in perf[-3:]]
        insights['over_target'] = [r['dimension_value'] for r in perf if (r.get('achievement_pct') or 0) >= 100]
        insights['under_target'] = [r['dimension_value'] for r in perf if (r.get('achievement_pct') or 0) < 100]
        if perf:
            insights['kpi_summary']['best_entity'] = perf[0]['dimension_value']
            insights['kpi_summary']['worst_entity'] = perf[-1]['dimension_value']
            insights['kpi_summary']['best_achievement_pct'] = perf[0]['achievement_pct']
            insights['kpi_summary']['worst_achievement_pct'] = perf[-1]['achievement_pct']

    if 'variance_to_target' in derived.get('available', []):
        variance_records = [r for r in records if r.get('variance_to_target') is not None and r.get('dimension_value')]
        if variance_records:
            total_variance = sum(r.get('variance_to_target') or 0 for r in variance_records)
            insights['kpi_summary']['variance_total'] = _safe_round(total_variance, 2)
            variance_records.sort(key=lambda r: r['variance_to_target'])
            insights['top_exceptions'] = [
                {
                    'dimension_value': r['dimension_value'],
                    'metric': 'Variance to Target',
                    'value': r['variance_to_target'],
                }
                for r in variance_records[:5]
            ]

    if 'stock_turnover' in derived.get('available', []):
        turn = [r for r in records if r.get('stock_turnover') is not None and r.get('dimension_value')]
        turn.sort(key=lambda r: r['stock_turnover'], reverse=True)
        if turn:
            insights['kpi_summary']['best_stock_turnover_entity'] = turn[0]['dimension_value']
            insights['kpi_summary']['lowest_stock_turnover_entity'] = turn[-1]['dimension_value']
            insights['inventory_alerts'].append({
                'dimension_value': turn[-1]['dimension_value'],
                'reason': 'Lowest stock turnover detected.',
                'gap_value': turn[-1]['stock_turnover'],
            })

    for metric in derived.get('available', [])[:4]:
        summary = (derived.get('summaries') or {}).get(metric) or {}
        if summary.get('mean') is not None:
            insights['narrative_points'].append(f"{summary.get('label', labels.get(metric, metric))} average is {summary['mean']}.")

    return insights


def build_ai_context_summary(profile: Dict[str, Any], roles: Dict[str, Optional[str]], derived: Dict[str, Any], classification: Dict[str, Any], insights: Dict[str, Any]) -> str:
    parts: List[str] = []
    if classification.get('analysis_type'):
        parts.append(f"Analysis type: {str(classification['analysis_type']).replace('_', ' ')}")
    if roles.get('primary_dimension'):
        parts.append(f"Primary dimension: {roles['primary_dimension']}")
    if roles.get('primary_time_column'):
        parts.append(f"Primary time column: {roles['primary_time_column']}")
    if roles.get('primary_measure'):
        parts.append(f"Primary measure: {roles['primary_measure']}")
    if roles.get('secondary_measure'):
        parts.append(f"Secondary measure: {roles['secondary_measure']}")
    if roles.get('target_column') and roles.get('actual_column'):
        parts.append(f"Performance pair: {roles['actual_column']} vs {roles['target_column']}")
    top = (insights.get('top_performers') or [])[:2]
    if top:
        parts.append('Top entities: ' + ', '.join(top))
    available = derived.get('available') or []
    labels = derived.get('labels') or {}
    if available:
        parts.append('Derived metrics: ' + ', '.join(labels.get(name, name.replace('_', ' ').title()) for name in available[:6]))
    return '. '.join(parts) + ('.' if parts else '')
