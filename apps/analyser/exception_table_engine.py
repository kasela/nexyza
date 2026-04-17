from __future__ import annotations

from typing import Any, Dict, List


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _money(value: Any) -> str:
    v = _safe_float(value)
    sign = '-' if v < 0 else ''
    v = abs(v)
    if v >= 1_000_000_000:
        return f"{sign}{v/1_000_000_000:.2f}B"
    if v >= 1_000_000:
        return f"{sign}{v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"{sign}{v/1_000:.1f}K"
    return f"{sign}{v:,.0f}"


def _pct(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}%"
    except Exception:
        return '—'


def _get_profile(analysis: Dict[str, Any]) -> Dict[str, Any]:
    return (analysis or {}).get('profile_json') or {}


def _get_insights(analysis: Dict[str, Any]) -> Dict[str, Any]:
    profile = _get_profile(analysis)
    screening = (analysis or {}).get('screening_json') or {}
    return profile.get('business_insights') or screening.get('business_insights') or {}


def _get_roles(analysis: Dict[str, Any]) -> Dict[str, Any]:
    profile = _get_profile(analysis)
    screening = (analysis or {}).get('screening_json') or {}
    return profile.get('business_roles') or screening.get('business_roles') or {}


def _get_derived_records(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    profile = _get_profile(analysis)
    screening = (analysis or {}).get('screening_json') or {}
    derived = profile.get('derived_metrics') or screening.get('derived_metrics') or {}
    return derived.get('records') or []


def _top_negative_variance(records: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    ranked = sorted(
        [r for r in records if r.get('variance_to_target') is not None],
        key=lambda r: _safe_float(r.get('variance_to_target'))
    )
    out = []
    for row in ranked[:limit]:
        out.append({
            'entity': row.get('dimension_value') or 'Unknown',
            'metric': _money(row.get('variance_to_target')),
            'support': _pct(row.get('achievement_pct')) if row.get('achievement_pct') is not None else '—',
        })
    return out


def _top_positive_surprise(records: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    ranked = sorted(
        [r for r in records if r.get('variance_to_target') is not None],
        key=lambda r: _safe_float(r.get('variance_to_target')),
        reverse=True,
    )
    out = []
    for row in [r for r in ranked if _safe_float(r.get('variance_to_target')) > 0][:limit]:
        out.append({
            'entity': row.get('dimension_value') or 'Unknown',
            'metric': _money(row.get('variance_to_target')),
            'support': _pct(row.get('achievement_pct')) if row.get('achievement_pct') is not None else '—',
        })
    return out


def _at_risk(records: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    risk_rows = []
    for row in records:
        ach = row.get('achievement_pct')
        if ach is None:
            continue
        achf = _safe_float(ach)
        if achf < 80:
            risk_rows.append(row)
    risk_rows.sort(key=lambda r: _safe_float(r.get('achievement_pct')))
    out = []
    for row in risk_rows[:limit]:
        out.append({
            'entity': row.get('dimension_value') or 'Unknown',
            'metric': _pct(row.get('achievement_pct')),
            'support': _money(row.get('variance_to_target')) if row.get('variance_to_target') is not None else '—',
        })
    return out


def _inventory_alerts(alerts: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    out = []
    for row in alerts[:limit]:
        out.append({
            'entity': row.get('dimension_value') or 'Unknown',
            'metric': _money(row.get('gap_value')),
            'support': row.get('reason') or 'Inventory alert',
        })
    return out


def build_exception_tables(analysis: Dict[str, Any], limit: int = 5) -> List[Dict[str, Any]]:
    insights = _get_insights(analysis)
    roles = _get_roles(analysis)
    records = _get_derived_records(analysis)
    tables: List[Dict[str, Any]] = []

    if records and roles.get('target_column') and any(r.get('variance_to_target') is not None for r in records):
        worst = _top_negative_variance(records, limit)
        if worst:
            tables.append({
                'key': 'negative_variance',
                'title': 'Biggest negative variance',
                'intro': 'Entities furthest below target that need immediate review.',
                'columns': ['Entity', 'Variance', 'Achievement %'],
                'rows': worst,
            })

        best = _top_positive_surprise(records, limit)
        if best:
            tables.append({
                'key': 'positive_surprise',
                'title': 'Biggest positive surprise',
                'intro': 'Entities outperforming target and creating upside.',
                'columns': ['Entity', 'Variance', 'Achievement %'],
                'rows': best,
            })

        risk = _at_risk(records, limit)
        if risk:
            tables.append({
                'key': 'at_risk',
                'title': 'Entities at risk',
                'intro': 'Segments below the default 80% attainment threshold.',
                'columns': ['Entity', 'Achievement %', 'Variance'],
                'rows': risk,
            })

    inventory_alerts = insights.get('inventory_alerts') or []
    inv_rows = _inventory_alerts(inventory_alerts, limit)
    if inv_rows:
        tables.append({
            'key': 'inventory_alerts',
            'title': 'Inventory pressure alerts',
            'intro': 'Possible stock build-up or purchase pressure surfaced by the engine.',
            'columns': ['Entity', 'Gap', 'Reason'],
            'rows': inv_rows,
        })

    quality_flags = (_get_profile(analysis).get('quality_flags') or [])[:limit]
    if quality_flags:
        rows = [{'entity': 'Dataset', 'metric': flag if isinstance(flag, str) else str(flag), 'support': 'Quality flag'} for flag in quality_flags]
        tables.append({
            'key': 'data_quality',
            'title': 'Data quality issues',
            'intro': 'Validation flags that may affect interpretation.',
            'columns': ['Entity', 'Issue', 'Type'],
            'rows': rows,
        })

    return tables
