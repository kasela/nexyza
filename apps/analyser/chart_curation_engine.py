from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Tuple


TOP_LIMIT_BY_MODE = {
    'executive': 8,
    'board': 10,
    'ops': 12,
    'analysis': 12,
}


@dataclass
class CuratedResult:
    visible: List[Any]
    suppressed: List[Any]
    summary: Dict[str, Any]


def _profile(analysis: Dict[str, Any]) -> Dict[str, Any]:
    return (analysis or {}).get('profile_json') or {}


def _roles(analysis: Dict[str, Any]) -> Dict[str, Any]:
    direct = (analysis or {}).get('semantic_roles') or {}
    if direct:
        return direct
    profile = _profile(analysis)
    semantic_roles = ((profile.get('business_semantics') or {}).get('roles') or {})
    return {
        'primary_dimension': semantic_roles.get('primary_dimension') or '',
        'actual_column': semantic_roles.get('primary_measure') or '',
        'target_column': semantic_roles.get('target_measure') or '',
        'period_column': semantic_roles.get('period_column') or '',
        'comparison_dimension': semantic_roles.get('comparison_dimension') or '',
    }


def _goals(analysis: Dict[str, Any]) -> List[str]:
    profile = _profile(analysis)
    goals = ((profile.get('user_guidance') or {}).get('primary_goals') or [])
    return [g.strip() for g in goals if str(g).strip()]


def _semantic_recommended_patterns(analysis: Dict[str, Any]) -> List[str]:
    profile = _profile(analysis)
    semantics = profile.get('business_semantics') or {}
    return list(((semantics.get('recommendations') or {}).get('charts') or []))


def _semantic_archetype(analysis: Dict[str, Any]) -> str:
    profile = _profile(analysis)
    semantics = profile.get('business_semantics') or {}
    return str(semantics.get('primary_archetype') or '')


def _chart_axis_names(chart: Any) -> Tuple[str, str, str]:
    return (
        (getattr(chart, 'x_axis', '') or '').strip(),
        (getattr(chart, 'y_axis', '') or '').strip(),
        (getattr(chart, 'group_by', '') or '').strip(),
    )


def _chart_category(chart_type: str) -> str:
    if chart_type == 'kpi':
        return 'kpi'
    if chart_type in {'line', 'area', 'rolling_line', 'cumulative_line'}:
        return 'trend'
    if chart_type in {'variance_bar', 'bullet', 'progress_ring', 'waterfall'}:
        return 'performance'
    if chart_type in {'bar', 'horizontal_bar', 'pareto'}:
        return 'ranking'
    if chart_type in {'pie', 'doughnut'}:
        return 'composition'
    if chart_type in {'histogram', 'heatmap'}:
        return 'distribution'
    if chart_type == 'scatter':
        return 'relationship'
    return 'other'


def _is_empty_or_error(chart: Any) -> bool:
    payload = getattr(chart, 'cached_data', None) or {}
    if not isinstance(payload, dict):
        return False
    if payload.get('error'):
        return True
    labels = payload.get('labels') or []
    datasets = payload.get('datasets') or []
    if payload.get('kpi'):
        value = payload.get('value')
        return value in (None, '', 'N/A', '—')
    return not labels or not datasets


def _score_chart(chart: Any, analysis: Dict[str, Any]) -> Tuple[float, List[str]]:
    profile = _profile(analysis)
    roles = _roles(analysis)
    goals = _goals(analysis)
    semantic_patterns = _semantic_recommended_patterns(analysis)
    semantic_archetype = _semantic_archetype(analysis)
    reasons: List[str] = []
    score = 40.0

    chart_type = getattr(chart, 'chart_type', '') or ''
    x_axis, y_axis, group_by = _chart_axis_names(chart)
    dimensions = set(profile.get('dimensions') or [])
    measures = set(profile.get('measures') or [])
    time_columns = set(profile.get('time_columns') or [])
    target_columns = set(profile.get('target_columns') or [])
    actual_columns = set(profile.get('actual_columns') or [])

    category = _chart_category(chart_type)
    reasons.append(category.replace('_', ' ').title())

    if chart_type == 'kpi':
        score += 22
        reasons.append('Fast executive signal')
    if chart_type in {'line', 'area', 'rolling_line', 'cumulative_line'} and x_axis in time_columns:
        score += 22
        reasons.append('Time-aware trend')
    if chart_type in {'variance_bar', 'bullet', 'progress_ring', 'waterfall'} and target_columns:
        score += 20
        reasons.append('Target-aware comparison')
    if chart_type in {'bar', 'horizontal_bar', 'variance_bar', 'pareto'} and x_axis in dimensions:
        score += 12
        reasons.append('Segment comparison')
    if chart_type == 'doughnut':
        score -= 10
        reasons.append('Lower priority composition')
    elif chart_type == 'pie':
        score -= 12
        reasons.append('Lower priority composition')
    if y_axis and y_axis in actual_columns:
        score += 12
        reasons.append('Uses actual metric')
    elif y_axis and y_axis in measures:
        score += 8
    if group_by and group_by in dimensions:
        score += 3
    if chart_type in {'pie', 'doughnut'}:
        score -= 6
        reasons.append('Composition view')
    if chart_type == 'scatter' and len(measures) < 2:
        score -= 20
    if x_axis and y_axis and x_axis == y_axis:
        score -= 25
        reasons.append('Repeated axis')

    primary_dimension = roles.get('primary_dimension')
    primary_actual = roles.get('actual_column')
    primary_target = roles.get('target_column')
    if x_axis and primary_dimension and x_axis == primary_dimension:
        score += 5
    if y_axis and primary_actual and y_axis == primary_actual:
        score += 8
    config_json = getattr(chart, 'config_json', None) or {}
    target_column = config_json.get('target_column') or ''
    if primary_target and target_column == primary_target:
        score += 8

    semantic_chart_map = {
        'target_vs_actual_trend': {'line', 'area'},
        'variance_by_dimension': {'variance_bar', 'horizontal_bar'},
        'attainment_ranked_bar': {'horizontal_bar', 'bar'},
        'profitability_bridge': {'waterfall', 'pareto', 'bar'},
        'margin_by_dimension': {'horizontal_bar', 'bar'},
        'period_variance': {'area', 'line'},
        'top_bottom_segments': {'horizontal_bar', 'bar'},
        'trend_line': {'line', 'area'},
        'exception_table': {'histogram', 'heatmap'},
        'balance_trend': {'line', 'area'},
        'stock_concentration': {'pareto', 'pie', 'doughnut'},
        'movement_waterfall': {'waterfall', 'area'},
    }
    for semantic_pattern in semantic_patterns:
        eligible_types = semantic_chart_map.get(semantic_pattern, set())
        if chart_type in eligible_types:
            score += 11
            reasons.append(semantic_pattern.replace('_', ' ').title())

    if semantic_archetype == 'target_vs_actual' and chart_type in {'variance_bar', 'line', 'horizontal_bar', 'kpi'}:
        score += 6
    elif semantic_archetype == 'financial_statement' and chart_type in {'pareto', 'horizontal_bar', 'area', 'kpi'}:
        score += 6
    elif semantic_archetype in {'operational_performance', 'inventory_or_balance'} and chart_type in {'horizontal_bar', 'line', 'heatmap', 'kpi'}:
        score += 5

    goal_bonus_map = {
        'Target vs achievement': {'variance_bar', 'bullet', 'progress_ring', 'waterfall'},
        'Trend over time': {'line', 'area', 'rolling_line', 'cumulative_line'},
        'Contribution / Pareto': {'pareto', 'pie', 'doughnut'},
        'Ranking / top and bottom': {'bar', 'horizontal_bar', 'pareto'},
        'Distribution / spread': {'histogram', 'heatmap'},
    }
    for goal, eligible_types in goal_bonus_map.items():
        if goal in goals and chart_type in eligible_types:
            score += 10
            reasons.append(goal)

    confidence_meta = getattr(chart, 'confidence_meta', {}) or {}
    confidence = float(confidence_meta.get('final_chart_confidence') or 0)
    if confidence:
        score += confidence * 18
        reasons.append(f'Confidence {confidence:.2f}')
    if confidence_meta.get('suppress_by_default'):
        score -= 22
        reasons.append('Flagged low confidence')

    if _is_empty_or_error(chart):
        score -= 100
        reasons.append('Empty or errored payload')

    return score, reasons[:4]


def curate_dashboard_charts(charts: Iterable[Any], analysis: Dict[str, Any], mode: str = 'executive') -> CuratedResult:
    mode = (mode or 'executive').strip().lower()

    # Explorer mode: show every chart that isn't empty/errored — no limits, no suppression.
    if mode == 'explorer':
        all_charts = list(charts or [])
        visible: List[Any] = []
        suppressed: List[Any] = []
        for chart in all_charts:
            score, reasons = _score_chart(chart, analysis)
            meta = {
                'score': round(score, 2),
                'priority_label': 'High priority' if score >= 78 else 'Recommended' if score >= 60 else 'Supporting view',
                'reasons': reasons,
                'category': _chart_category(getattr(chart, 'chart_type', '') or ''),
            }
            setattr(chart, 'selection_meta', meta)
            if _is_empty_or_error(chart):
                suppressed.append(chart)
            else:
                visible.append(chart)
        visible.sort(key=lambda c: ((getattr(c, 'selection_meta', {}) or {}).get('score') or 0), reverse=True)
        summary = {
            'mode': mode,
            'limit': len(visible),
            'considered': len(all_charts),
            'visible_count': len(visible),
            'suppressed_count': len(suppressed),
            'top_categories': sorted({(getattr(c, 'selection_meta', {}) or {}).get('category', 'other') for c in visible}),
            'policy_label': 'Explorer mode — all charts shown',
            'policy_note': 'All non-empty charts are visible. Switch to Executive for curated view.',
        }
        return CuratedResult(visible=visible, suppressed=suppressed, summary=summary)

    limit = TOP_LIMIT_BY_MODE.get(mode, 10)
    scored: List[Any] = []
    summary = {
        'mode': mode,
        'limit': limit,
        'considered': 0,
        'visible_count': 0,
        'suppressed_count': 0,
        'top_categories': [],
        'policy_label': 'Decision-first chart selection',
        'policy_note': 'Promotes charts that match time, target, ranking, and confidence signals.',
    }

    for chart in charts or []:
        score, reasons = _score_chart(chart, analysis)
        meta = {
            'score': round(score, 2),
            'priority_label': 'High priority' if score >= 78 else 'Recommended' if score >= 60 else 'Supporting view',
            'reasons': reasons,
            'category': _chart_category(getattr(chart, 'chart_type', '') or ''),
        }
        setattr(chart, 'selection_meta', meta)
        scored.append(chart)

    summary['considered'] = len(scored)
    scored.sort(key=lambda c: ((getattr(c, 'selection_meta', {}) or {}).get('score') or 0), reverse=True)

    semantic_archetype = _semantic_archetype(analysis)
    visible: List[Any] = []
    suppressed: List[Any] = []
    categories_seen = set()
    used_specs = set()

    # First pass: keep critical chart types first.
    priority_types = []
    if semantic_archetype == 'target_vs_actual':
        priority_types = ['kpi', 'variance_bar', 'bullet', 'progress_ring', 'horizontal_bar', 'bar', 'line', 'area']

    def _try_add(chart: Any) -> bool:
        meta = getattr(chart, 'selection_meta', {}) or {}
        score = meta.get('score', 0)
        spec = (getattr(chart, 'chart_type', ''), getattr(chart, 'x_axis', ''), getattr(chart, 'y_axis', ''), getattr(chart, 'group_by', ''))
        if score < 15 or _is_empty_or_error(chart):
            if chart not in suppressed:
                suppressed.append(chart)
            return False
        if spec in used_specs:
            if chart not in suppressed:
                suppressed.append(chart)
            return False
        visible.append(chart)
        used_specs.add(spec)
        categories_seen.add(meta.get('category'))
        if chart in suppressed:
            suppressed.remove(chart)
        return True

    if priority_types:
        for needed in priority_types:
            if len(visible) >= limit:
                break
            for chart in scored:
                if getattr(chart, 'chart_type', '') != needed:
                    continue
                if _try_add(chart):
                    break

    # First pass: keep diversity after critical types.
    for chart in scored:
        if len(visible) >= limit:
            break
        meta = getattr(chart, 'selection_meta', {}) or {}
        spec = (getattr(chart, 'chart_type', ''), getattr(chart, 'x_axis', ''), getattr(chart, 'y_axis', ''), getattr(chart, 'group_by', ''))
        if spec in used_specs:
            continue
        score = meta.get('score', 0)
        if score < 15 or _is_empty_or_error(chart):
            if chart not in suppressed:
                suppressed.append(chart)
            continue
        if meta.get('category') == 'composition' and semantic_archetype == 'target_vs_actual' and any((getattr(c, 'selection_meta', {}) or {}).get('category') == 'performance' for c in visible):
            if chart not in suppressed:
                suppressed.append(chart)
            continue
        if meta.get('category') not in categories_seen or score >= 78:
            _try_add(chart)
        elif chart not in suppressed:
            suppressed.append(chart)

    # Second pass: refill visible list with strongest leftovers.
    if len(visible) < limit:
        refill = []
        current_ids = {getattr(c, 'id', None) for c in visible}
        for chart in scored:
            spec = (getattr(chart, 'chart_type', ''), getattr(chart, 'x_axis', ''), getattr(chart, 'y_axis', ''), getattr(chart, 'group_by', ''))
            if getattr(chart, 'id', None) in current_ids:
                continue
            if spec in used_specs:
                continue
            score = (getattr(chart, 'selection_meta', {}) or {}).get('score', 0)
            if score < 15 or _is_empty_or_error(chart):
                continue
            refill.append(chart)
        for chart in refill:
            if len(visible) >= limit:
                break
            visible.append(chart)
            used_specs.add((getattr(chart, 'chart_type', ''), getattr(chart, 'x_axis', ''), getattr(chart, 'y_axis', ''), getattr(chart, 'group_by', '')))
            if chart in suppressed:
                suppressed.remove(chart)

    summary['visible_count'] = len(visible)
    summary['suppressed_count'] = len(scored) - len(visible)
    summary['top_categories'] = sorted({(getattr(c, 'selection_meta', {}) or {}).get('category', 'other') for c in visible})
    return CuratedResult(visible=visible, suppressed=[c for c in scored if c not in visible], summary=summary)
