from __future__ import annotations

from typing import Any, Dict, List


def _safe_list(value: Any) -> List[str]:
    return [str(v) for v in (value or []) if str(v).strip()]


def _classification(profile: Dict[str, Any]) -> Dict[str, Any]:
    return profile.get('analysis_classification') or {}


def detect_chart_pack(profile: Dict[str, Any]) -> str:
    cls = _classification(profile)
    roles = profile.get('business_roles') or {}
    time_cols = _safe_list(profile.get('time_columns'))
    dims = _safe_list(profile.get('dimensions'))
    measures = _safe_list(profile.get('measures'))
    derived = set(_safe_list((profile.get('derived_metrics') or {}).get('available')))
    intents = set(_safe_list((profile.get('universal_intelligence') or {}).get('detected_intents')))
    analysis_type = str(cls.get('analysis_type') or '').strip()

    has_target_actual = bool(roles.get('target_column') and roles.get('actual_column'))
    has_stock = bool(roles.get('opening_stock_column') and roles.get('closing_stock_column'))
    has_time = bool(time_cols)
    rich_dims = len(dims) >= 3
    has_ratio = any(m.endswith('_ratio') or m.endswith('_pct') for m in derived)

    if has_target_actual and has_time and has_stock:
        return 'performance_time_inventory'
    if has_target_actual and has_time and rich_dims:
        return 'performance_hierarchy_time'
    if has_target_actual and has_time:
        return 'performance_time_series'
    if has_target_actual:
        return 'performance_snapshot'
    if analysis_type == 'trend_analysis' or ('trend' in intents and has_time):
        return 'time_series_generic'
    if analysis_type == 'composition_analysis' or 'composition' in intents:
        return 'composition_focus'
    if len(measures) >= 2 and ('correlation' in intents or has_ratio):
        return 'relationship_focus'
    return 'general_business'


def suggested_groupings(profile: Dict[str, Any]) -> List[str]:
    cls = _classification(profile)
    col_lookup = {c['name']: c for c in (profile.get('column_profiles') or [])}
    dims = [d for d in _safe_list(profile.get('dimensions')) if (col_lookup.get(d, {}).get('unique_count') or 2) > 1]
    primary = str(cls.get('primary_dimension') or '').strip()
    preferred_order = [
        primary,
        'Category',
        'Province',
        'Geographical Area',
        'Cluster',
        'Regional Manager',
    ]
    ordered: List[str] = []
    for item in preferred_order:
        if item and item in dims and item not in ordered:
            ordered.append(item)
    for item in dims:
        if item not in ordered:
            ordered.append(item)
    return ordered[:5]


def chart_pack_settings(profile: Dict[str, Any]) -> Dict[str, Any]:
    pack = detect_chart_pack(profile)
    dims = suggested_groupings(profile)
    cls = _classification(profile)
    primary_time = str(cls.get('primary_time_column') or '').strip() or (_safe_list(profile.get('time_columns'))[:1] or [''])[-1]

    settings: Dict[str, Any] = {
        'pack': pack,
        'groupings': dims,
        'primary_grouping': dims[0] if dims else '',
        'secondary_grouping': dims[1] if len(dims) > 1 else '',
        'tertiary_grouping': dims[2] if len(dims) > 2 else '',
        'primary_time': primary_time,
        'prefer_combo_trend': False,
        'allow_scatter': False,
        'allow_donut': False,
        'allow_progress_ring': False,
        'prefer_heatmap': False,
        'prefer_pareto': False,
        'target_count_cap': 10,
    }

    if pack in {'performance_time_series', 'performance_hierarchy_time', 'performance_time_inventory', 'time_series_generic'}:
        settings.update({
            'prefer_combo_trend': True,
            'allow_scatter': pack in {'performance_time_inventory', 'relationship_focus'},
            'prefer_heatmap': len(dims) >= 2,
            'prefer_pareto': len(dims) >= 1,
            'target_count_cap': 12,
        })
    elif pack in {'performance_snapshot', 'composition_focus'}:
        settings.update({
            'allow_donut': pack == 'composition_focus' and len(dims) == 1,
            'prefer_pareto': len(dims) >= 1,
            'prefer_heatmap': len(dims) >= 2,
        })
    elif pack == 'relationship_focus':
        settings.update({
            'allow_scatter': True,
            'target_count_cap': 9,
        })
    else:
        settings.update({
            'allow_scatter': len(_safe_list(profile.get('measures'))) >= 2,
            'allow_donut': len(dims) == 1 and len(_safe_list(profile.get('measures'))) == 1,
            'prefer_pareto': len(dims) >= 1,
        })

    return settings
