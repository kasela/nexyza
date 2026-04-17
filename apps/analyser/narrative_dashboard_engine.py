from __future__ import annotations

from typing import Any, Dict, List, Tuple


def _money(value: Any) -> str:
    try:
        v = float(value or 0)
    except Exception:
        return '—'
    sign = '-' if v < 0 else ''
    v = abs(v)
    if v >= 1_000_000_000:
        return f"{sign}{v/1_000_000_000:.2f}B"
    if v >= 1_000_000:
        return f"{sign}{v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"{sign}{v/1_000:.1f}K"
    return f"{sign}{v:,.0f}"


def _num(value: Any, digits: int = 2) -> str:
    try:
        v = float(value)
    except Exception:
        return '—'
    return f"{v:.{digits}f}"


def _pct(value: Any, digits: int = 2) -> str:
    try:
        v = float(value)
    except Exception:
        return '—'
    return f"{v:.{digits}f}%"


def _get_profile(analysis: Dict[str, Any]) -> Dict[str, Any]:
    return (analysis or {}).get('profile_json') or {}


def _get_screening(analysis: Dict[str, Any]) -> Dict[str, Any]:
    return (analysis or {}).get('screening_json') or {}


def _get_insights(analysis: Dict[str, Any]) -> Dict[str, Any]:
    profile = _get_profile(analysis)
    screening = _get_screening(analysis)
    return profile.get('business_insights') or screening.get('business_insights') or {}


def _get_roles(analysis: Dict[str, Any]) -> Dict[str, Any]:
    profile = _get_profile(analysis)
    screening = _get_screening(analysis)
    return profile.get('business_roles') or screening.get('business_roles') or {}


def _get_derived(analysis: Dict[str, Any]) -> Dict[str, Any]:
    profile = _get_profile(analysis)
    screening = _get_screening(analysis)
    return profile.get('derived_metrics') or screening.get('derived_metrics') or {}


def _get_analysis_type(analysis: Dict[str, Any]) -> str:
    profile = _get_profile(analysis)
    cls = profile.get('analysis_classification') or {}
    return (cls.get('analysis_type') or _get_screening(analysis).get('analysis_type') or '').strip()


def _get_primary_time(analysis: Dict[str, Any]) -> str:
    profile = _get_profile(analysis)
    cls = profile.get('analysis_classification') or {}
    return (
        cls.get('primary_time_column')
        or (_get_roles(analysis) or {}).get('time_column')
        or ''
    ).strip()


def _get_dimension_candidates(analysis: Dict[str, Any]) -> List[str]:
    profile = _get_profile(analysis)
    return profile.get('dimensions') or []


def _chart_has_data(chart: Any) -> bool:
    d = getattr(chart, 'cached_data', None) or {}
    if d.get('error'):
        return False
    if d.get('kpi'):
        return True
    if d.get('labels') and d.get('datasets'):
        return True
    if d.get('heatmap') and d.get('columns') and d.get('matrix'):
        return True
    return False


def _chart_title(chart: Any) -> str:
    parts = [
        getattr(chart, 'title', '') or '',
        getattr(chart, 'x_axis', '') or '',
        getattr(chart, 'y_axis', '') or '',
        getattr(chart, 'group_by', '') or '',
    ]
    return ' '.join(parts).lower()


def _shell_type(analysis: Dict[str, Any]) -> str:
    roles = _get_roles(analysis)
    primary_time = _get_primary_time(analysis)
    analysis_type = _get_analysis_type(analysis)
    has_target_actual = bool(roles.get('target_column') and roles.get('actual_column'))
    has_stock = bool(roles.get('opening_stock_column') and roles.get('closing_stock_column'))
    if has_target_actual and primary_time and has_stock:
        return 'performance_time_inventory'
    if has_target_actual and primary_time:
        return 'performance_time_series'
    if has_target_actual and has_stock:
        return 'performance_inventory_snapshot'
    if has_target_actual:
        return 'performance_snapshot'
    if primary_time:
        return 'time_series_generic'
    if analysis_type == 'composition_analysis':
        return 'composition_only'
    return 'general_business'


def _chart_section(chart: Any, analysis: Dict[str, Any]) -> str:
    title = _chart_title(chart)
    ctype = (getattr(chart, 'chart_type', '') or '').lower()
    primary_time = _get_primary_time(analysis).lower()
    roles = _get_roles(analysis)
    dimension_candidates = [d.lower() for d in _get_dimension_candidates(analysis)]

    if ctype == 'kpi':
        return 'executive'
    if primary_time and any(k in title for k in [primary_time, 'month', 'year', 'trend', 'time', 'season']):
        return 'trend'
    if any(k in title for k in ['achievement %', 'variance', 'target', 'actual', 'achievement', 'achivement', 'attainment']):
        return 'performance'
    if roles.get('opening_stock_column') and any(k in title for k in ['stock', 'turnover', 'purchase', 'inventory', 'closing', 'opening', 'gap']):
        return 'inventory'
    if any(k in title for k in ['manager', 'branch', 'province', 'cluster', 'category', 'area', 'region']):
        return 'ranking'
    if ctype in {'pareto', 'pie', 'doughnut'}:
        return 'composition'
    if ctype in {'scatter', 'heatmap'}:
        return 'diagnostics'
    if ctype in {'bar', 'horizontal_bar'} and dimension_candidates:
        return 'ranking'
    return 'diagnostics'


def _is_weak_chart(chart: Any, analysis: Dict[str, Any]) -> bool:
    if not _chart_has_data(chart):
        return True
    ctype = (getattr(chart, 'chart_type', '') or '').lower()
    title = _chart_title(chart)
    roles = _get_roles(analysis)
    primary_time = _get_primary_time(analysis)
    if not roles.get('opening_stock_column') and any(k in title for k in ['stock', 'inventory', 'purchase']) and 'achievement' not in title:
        return True
    if roles.get('target_column') and roles.get('actual_column'):
        if ctype in {'pie', 'doughnut'} and not any(k in title for k in ['contribution', 'pareto', 'mix', 'category']):
            return True
        if ctype == 'scatter' and not roles.get('opening_stock_column') and 'variance' not in title:
            return True
    if primary_time and ctype in {'progress_ring'}:
        return True
    return False


def _build_hero(analysis: Dict[str, Any], insights: Dict[str, Any], shell_type: str) -> Dict[str, Any]:
    kpi = insights.get('kpi_summary') or {}
    roles = _get_roles(analysis)
    primary_time = _get_primary_time(analysis)
    achievement_total = kpi.get('achievement_pct_total')
    variance_total = kpi.get('variance_total')
    best_branch = kpi.get('best_branch') or '—'
    worst_branch = kpi.get('worst_branch') or '—'
    risk_branch = kpi.get('highest_closing_stock_branch') or '—'

    if shell_type == 'performance_time_series':
        if achievement_total is not None:
            headline = f"{primary_time or 'Time'}-led performance dashboard is ready."
            subheadline = f"Overall achievement is {_pct(achievement_total)} with variance {_money(variance_total)}. Lead with trend, then move to branch and manager ranking."
            status = 'Performance narrative'
            tone = 'violet' if float(achievement_total) < 100 else 'emerald'
        else:
            headline = 'Time-series performance dashboard is ready.'
            subheadline = 'Lead with trend, then move to ranking and exceptions.'
            status = 'Trend narrative'
            tone = 'violet'
    elif shell_type == 'performance_inventory_snapshot':
        headline = f"Performance and inventory dashboard is ready."
        subheadline = f"Best branch is {best_branch}. Watch {risk_branch} for stock pressure while closing target gaps in {worst_branch}."
        status = 'Operational narrative'
        tone = 'amber'
    elif shell_type == 'performance_snapshot':
        headline = f"Performance dashboard is ready."
        subheadline = f"Overall achievement is {_pct(achievement_total)} with a shortfall of {_money(variance_total)}. Use ranking and variance views first."
        status = 'Performance narrative'
        tone = 'rose' if (achievement_total is not None and float(achievement_total) < 100) else 'emerald'
    elif shell_type == 'composition_only':
        headline = 'Composition dashboard is ready.'
        subheadline = 'Use contribution, mix, and concentration visuals to identify dominant segments.'
        status = 'Composition narrative'
        tone = 'violet'
    else:
        headline = 'Adaptive dashboard is ready.'
        subheadline = 'The page is arranged around the strongest questions detected in the uploaded file.'
        status = 'Analysis ready'
        tone = 'violet'
    return {'status': status, 'headline': headline, 'subheadline': subheadline, 'tone': tone}


def _build_kpis(analysis: Dict[str, Any], insights: Dict[str, Any], shell_type: str) -> List[Dict[str, str]]:
    kpi = insights.get('kpi_summary') or {}
    roles = _get_roles(analysis)
    derived = _get_derived(analysis)
    derived_summaries = (derived.get('summaries') or {}) if isinstance(derived, dict) else {}

    total_actual = kpi.get('total_actual')
    if total_actual is None:
        total_actual = kpi.get('total_primary_measure')

    total_target = kpi.get('total_target')
    variance_total = kpi.get('variance_total')

    achievement_pct_total = kpi.get('achievement_pct_total')
    if achievement_pct_total is None:
        achievement_pct_total = ((derived_summaries.get('achievement_pct') or {}).get('mean'))

    best_branch = kpi.get('best_branch') or kpi.get('best_entity')
    worst_branch = kpi.get('worst_branch') or kpi.get('worst_entity')
    best_turnover_branch = kpi.get('best_stock_turnover_branch') or kpi.get('best_stock_turnover_entity')
    lowest_turnover_branch = kpi.get('lowest_stock_turnover_branch') or kpi.get('lowest_stock_turnover_entity')
    best_turnover = kpi.get('best_stock_turnover')
    if best_turnover is None:
        best_turnover = ((derived_summaries.get('stock_turnover') or {}).get('max'))
    lowest_turnover = kpi.get('lowest_stock_turnover')
    if lowest_turnover is None:
        lowest_turnover = ((derived_summaries.get('stock_turnover') or {}).get('min'))

    items: List[Dict[str, str]] = []
    if roles.get('actual_column'):
        items.append({'label': 'Actual', 'value': _money(total_actual), 'subtext': roles.get('actual_column'), 'emoji': '📌'})
    if roles.get('target_column'):
        items.append({'label': 'Target', 'value': _money(total_target), 'subtext': roles.get('target_column'), 'emoji': '🎯'})
        items.append({'label': 'Achievement %', 'value': _pct(achievement_pct_total), 'subtext': 'Overall target delivery', 'emoji': '✅' if (achievement_pct_total or 0) >= 100 else '🎯'})
        items.append({'label': 'Variance', 'value': _money(variance_total), 'subtext': 'Net against target', 'emoji': '📉' if (variance_total or 0) < 0 else '📈'})
    if best_branch:
        items.append({'label': 'Best branch', 'value': best_branch, 'subtext': 'Top attainment', 'emoji': '🏆'})
    if worst_branch:
        items.append({'label': 'Weakest branch', 'value': worst_branch, 'subtext': 'Lowest attainment', 'emoji': '⚠️'})
    if roles.get('opening_stock_column') and lowest_turnover_branch:
        items.append({'label': 'Stock risk', 'value': lowest_turnover_branch, 'subtext': f'Lowest turnover {_num(lowest_turnover, 4)}', 'emoji': '📦'})
    if roles.get('opening_stock_column') and best_turnover_branch:
        items.append({'label': 'Best turnover', 'value': best_turnover_branch, 'subtext': _num(best_turnover, 4), 'emoji': '⚙️'})
    return items[:6]


def _build_insight_cards(analysis: Dict[str, Any], insights: Dict[str, Any], shell_type: str) -> List[Dict[str, str]]:
    kpi = insights.get('kpi_summary') or {}
    narrative_points = insights.get('narrative_points') or []
    top_performers = insights.get('top_performers') or []
    underperformers = insights.get('underperformers') or []
    roles = _get_roles(analysis)
    cards = [
        {
            'label': 'Problem', 'emoji': '🔴',
            'title': f"{(underperformers[:1] or [kpi.get('worst_branch') or 'Weak branch'])[0]} needs attention",
            'body': narrative_points[1] if len(narrative_points) > 1 else 'The weakest segment is pulling overall performance down.'
        },
        {
            'label': 'Observation', 'emoji': '🟡',
            'title': 'The file supports managerial comparison',
            'body': 'Use dimension switches to compare branches, managers, categories, or regions without changing the dashboard shell.'
        },
        {
            'label': 'Opportunity', 'emoji': '🟢',
            'title': 'Top performers set the benchmark',
            'body': f"Use {', '.join(top_performers[:3]) or 'leading segments'} as the reference pattern for weaker units."
        },
        {
            'label': 'Action', 'emoji': '⚡',
            'title': 'Follow the page in business order',
            'body': 'Start with KPI and trend, then review ranking, then move to composition or diagnostics only if needed.'
        },
    ]
    if roles.get('opening_stock_column'):
        cards[1] = {
            'label': 'Observation', 'emoji': '🟡',
            'title': 'Inventory pressure is visible',
            'body': narrative_points[3] if len(narrative_points) > 3 else 'Stock flow and purchase gap should be reviewed after performance delivery.'
        }
    return cards


def _section_order(shell_type: str, roles: Dict[str, Any]) -> List[Tuple[str, str, str]]:
    base = {
        'executive': ('Executive KPIs', 'Start with the top-line outcome before moving into detail.'),
        'trend': ('Time trend', 'Use these visuals to read monthly or period movement before drilling into segments.'),
        'performance': ('Target performance', 'Review actual versus target, attainment, and variance.'),
        'ranking': ('Ranking views', 'See which segments lead, lag, or concentrate the result.'),
        'inventory': ('Inventory efficiency', 'Review stock pressure, turnover, and purchase-to-sales mismatches.'),
        'composition': ('Composition', 'Use contribution and mix charts only after the primary performance view.'),
        'diagnostics': ('Drivers and diagnostics', 'These visuals validate the story and are not the first management view.'),
    }
    if shell_type == 'performance_time_inventory':
        keys = ['executive', 'trend', 'performance', 'ranking', 'inventory', 'diagnostics']
    elif shell_type == 'performance_time_series':
        keys = ['executive', 'trend', 'performance', 'ranking', 'composition', 'diagnostics']
    elif shell_type == 'performance_inventory_snapshot':
        keys = ['executive', 'performance', 'ranking', 'inventory', 'diagnostics']
    elif shell_type == 'performance_snapshot':
        keys = ['executive', 'performance', 'ranking', 'composition', 'diagnostics']
    elif shell_type == 'composition_only':
        keys = ['executive', 'composition', 'ranking', 'diagnostics']
    else:
        keys = ['executive', 'trend', 'performance', 'ranking', 'composition', 'diagnostics']
    return [(k, *base[k]) for k in keys]


def _build_summary_line(analysis: Dict[str, Any]) -> str:
    roles = _get_roles(analysis)
    profile = _get_profile(analysis)
    primary_time = _get_primary_time(analysis)
    pieces = []
    if roles.get('primary_dimension'):
        pieces.append(f"Primary dimension: {roles['primary_dimension']}")
    if primary_time:
        pieces.append(f"Time grain: {primary_time}")
    if roles.get('actual_column'):
        pieces.append(f"Actual: {roles['actual_column']}")
    if roles.get('target_column'):
        pieces.append(f"Target: {roles['target_column']}")
    extra_dims = [d for d in (profile.get('dimensions') or []) if d != roles.get('primary_dimension')]
    if extra_dims:
        pieces.append(f"Available groupings: {', '.join(extra_dims[:4])}")
    return ' · '.join(pieces)


def build_narrative_dashboard(analysis: Dict[str, Any], charts: List[Any]) -> Dict[str, Any]:
    insights = _get_insights(analysis)
    roles = _get_roles(analysis)
    shell_type = _shell_type(analysis)
    hero = _build_hero(analysis, insights, shell_type)
    executive_kpis = _build_kpis(analysis, insights, shell_type)
    insight_cards = _build_insight_cards(analysis, insights, shell_type)

    visible = [c for c in charts if not _is_weak_chart(c, analysis)]
    suppressed_count = max(0, len(charts) - len(visible))

    grouped: Dict[str, List[Any]] = {}
    for chart in visible:
        grouped.setdefault(_chart_section(chart, analysis), []).append(chart)

    sections = []
    for key, title, intro in _section_order(shell_type, roles):
        items = grouped.get(key) or []
        if not items:
            continue
        sections.append({'key': key, 'title': title, 'intro': intro, 'charts': items})

    return {
        'shell_type': shell_type,
        'hero': hero,
        'executive_kpis': executive_kpis,
        'insight_cards': insight_cards,
        'sections': sections,
        'summary_line': _build_summary_line(analysis),
        'suppressed_count': suppressed_count,
        'visible_chart_count': len(visible),
        'dimension_switches': [d for d in _get_dimension_candidates(analysis) if d != roles.get('primary_dimension')][:5],
        'primary_time': _get_primary_time(analysis),
    }
