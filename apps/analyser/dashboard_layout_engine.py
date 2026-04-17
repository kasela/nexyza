from __future__ import annotations

from typing import Any, Dict, Iterable, List


def _safe_lower(value: Any) -> str:
    return str(value or '').strip().lower()


SECTION_BLUEPRINT = [
    {
        'key': 'kpi_row',
        'title': 'Executive KPIs',
        'description': 'Fast read of overall performance, target delivery, and efficiency.',
        'matchers': [
            lambda c: _safe_lower(c.get('chart_type')) == 'kpi',
        ],
    },
    {
        'key': 'target_block',
        'title': 'Target performance',
        'description': 'How actual performance compares against targets across the business.',
        'matchers': [
            lambda c: 'target' in _safe_lower(c.get('title')) or 'achievement' in _safe_lower(c.get('title')),
            lambda c: _safe_lower(c.get('chart_type')) in {'variance_bar', 'bullet', 'progress_ring'},
        ],
    },
    {
        'key': 'ranking_block',
        'title': 'Branch ranking',
        'description': 'Top and bottom performers, contribution, and concentration.',
        'matchers': [
            lambda c: _safe_lower(c.get('chart_type')) in {'horizontal_bar', 'pareto'},
            lambda c: 'contribution' in _safe_lower(c.get('title')) or 'ranking' in _safe_lower(c.get('title')),
        ],
    },
    {
        'key': 'stock_block',
        'title': 'Stock efficiency',
        'description': 'Inventory pressure, stock movement, and turnover efficiency.',
        'matchers': [
            lambda c: 'stock' in _safe_lower(c.get('title')),
            lambda c: 'purchase' in _safe_lower(c.get('title')),
            lambda c: 'inventory' in _safe_lower(c.get('title')),
        ],
    },
    {
        'key': 'diagnostic_block',
        'title': 'Drivers and diagnostics',
        'description': 'Relationships, spread, and supporting evidence behind the main story.',
        'matchers': [
            lambda c: _safe_lower(c.get('chart_type')) in {'scatter', 'histogram', 'heatmap', 'line', 'area', 'rolling_line', 'cumulative_line'},
        ],
    },
]


def _matches(chart: Dict[str, Any], blueprint: Dict[str, Any]) -> bool:
    for matcher in blueprint.get('matchers') or []:
        try:
            if matcher(chart):
                return True
        except Exception:
            continue
    return False


def build_dashboard_layout(charts: Iterable[Any], profile: Dict[str, Any] | None = None) -> Dict[str, Any]:
    profile = profile or {}
    chart_list: List[Dict[str, Any]] = []
    for chart in charts:
        if isinstance(chart, dict):
            item = dict(chart)
        else:
            item = {
                'id': str(getattr(chart, 'id', '')),
                'title': getattr(chart, 'title', ''),
                'chart_type': getattr(chart, 'chart_type', ''),
                'x_axis': getattr(chart, 'x_axis', ''),
                'y_axis': getattr(chart, 'y_axis', ''),
                'group_by': getattr(chart, 'group_by', ''),
                'aggregation': getattr(chart, 'aggregation', ''),
                'size': getattr(chart, 'size', ''),
                'color': getattr(chart, 'color', ''),
            }
            item['object'] = chart
        chart_list.append(item)

    buckets: Dict[str, List[Dict[str, Any]]] = {bp['key']: [] for bp in SECTION_BLUEPRINT}
    leftovers: List[Dict[str, Any]] = []

    for chart in chart_list:
        matched_key = None
        for blueprint in SECTION_BLUEPRINT:
            if _matches(chart, blueprint):
                matched_key = blueprint['key']
                break
        if matched_key:
            buckets[matched_key].append(chart)
        else:
            leftovers.append(chart)

    if leftovers:
        buckets['diagnostic_block'].extend(leftovers)

    sections = []
    for blueprint in SECTION_BLUEPRINT:
        items = buckets.get(blueprint['key']) or []
        if not items:
            continue
        sections.append({
            'key': blueprint['key'],
            'title': blueprint['title'],
            'description': blueprint['description'],
            'charts': items,
        })

    business_insights = profile.get('business_insights') or {}
    kpis = business_insights.get('kpi_summary') or {}
    snapshot = []
    if kpis.get('achievement_pct_total') is not None:
        snapshot.append({
            'label': 'Overall achievement',
            'value': f"{kpis['achievement_pct_total']}%",
            'tone': 'violet',
            'helper': 'Actual versus target across the whole file.',
        })
    if kpis.get('variance_total') is not None:
        snapshot.append({
            'label': 'Net variance',
            'value': kpis['variance_total'],
            'tone': 'rose' if float(kpis['variance_total']) < 0 else 'emerald',
            'helper': 'Positive means ahead of target; negative means behind.',
        })
    if kpis.get('best_branch'):
        snapshot.append({
            'label': 'Best branch',
            'value': kpis['best_branch'],
            'tone': 'emerald',
            'helper': 'Strongest target delivery in the current file.',
        })
    if kpis.get('worst_branch'):
        snapshot.append({
            'label': 'Watch branch',
            'value': kpis['worst_branch'],
            'tone': 'amber',
            'helper': 'Weakest target delivery in the current file.',
        })
    if kpis.get('highest_closing_stock_branch'):
        snapshot.append({
            'label': 'Highest closing stock',
            'value': kpis['highest_closing_stock_branch'],
            'tone': 'cyan',
            'helper': 'Largest ending inventory exposure.',
        })

    narrative = [point for point in (business_insights.get('narrative_points') or []) if point][:3]

    return {
        'sections': sections,
        'executive_snapshot': snapshot,
        'narrative': narrative,
    }
