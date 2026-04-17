from __future__ import annotations

from typing import Any, Dict


def build_executive_summary(analysis_result: Dict[str, Any], chart_count: int = 0) -> Dict[str, str]:
    analysis_result = analysis_result or {}
    profile = analysis_result.get('profile_json') or {}
    screening = analysis_result.get('screening_json') or {}
    insights = profile.get('business_insights') or screening.get('business_insights') or {}
    kpi = insights.get('kpi_summary') or {}
    analysis_type = ((profile.get('analysis_classification') or {}).get('analysis_type') or screening.get('analysis_type') or '').replace('_', ' ').strip()
    dimension = ((profile.get('business_roles') or {}).get('primary_dimension') or (profile.get('analysis_classification') or {}).get('primary_dimension') or 'business dimension')
    target = ((profile.get('business_roles') or {}).get('target_column') or screening.get('recommended_target_column') or 'target')
    actual = ((profile.get('business_roles') or {}).get('actual_column') or screening.get('recommended_main_measure') or 'actual')

    achievement_pct = kpi.get('achievement_pct_total')
    variance_total = kpi.get('variance_total')
    best_branch = kpi.get('best_branch') or '—'
    worst_branch = kpi.get('worst_branch') or '—'
    highest_stock_branch = kpi.get('highest_closing_stock_branch') or '—'

    def _money(v: Any) -> str:
        try:
            v = float(v or 0)
        except Exception:
            return '—'
        sign = '-' if v < 0 else ''
        v = abs(v)
        if v >= 1_000_000:
            return f"{sign}{v/1_000_000:.2f}M"
        if v >= 1_000:
            return f"{sign}{v/1_000:.1f}K"
        return f"{sign}{v:,.0f}"

    def _pct(v: Any) -> str:
        try:
            return f"{float(v):.2f}%"
        except Exception:
            return '—'

    headline = f"{analysis_type.title() if analysis_type else 'AI'} view of {actual} against {target} by {dimension}."
    if achievement_pct is not None:
        headline = f"Overall achievement is {_pct(achievement_pct)} with variance of {_money(variance_total)}."

    opportunity = f"Prioritise {actual} vs {target}, then rank {dimension.lower()} results, then review stock and purchasing exceptions."
    risk = f"Current pressure points: weakest branch {worst_branch}; highest stock concentration {highest_stock_branch}."
    action = f"Keep the strongest management visuals on screen and suppress weak or empty charts. Currently showing up to {chart_count} chart cards."

    if best_branch != '—' and worst_branch != '—':
        opportunity = f"Best branch is {best_branch}; weakest branch is {worst_branch}. Use the next charts to explain that gap."

    return {
        'headline': headline,
        'opportunity': opportunity,
        'risk': risk,
        'action': action,
    }
