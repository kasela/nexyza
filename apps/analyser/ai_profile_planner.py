from __future__ import annotations

from typing import Any, Dict, List

from .data_profile import profile_dataset
from .pattern_detection import detect_patterns
from .analysis_type_classifier import classify_analysis_type
from .decision_chart_builder import build_decision_chart_plan
from .intelligent_profile_engine import enrich_profile_for_business


def _apply_user_guidance(profile: Dict[str, Any], guidance: Dict[str, Any]) -> Dict[str, Any]:
    if not guidance:
        return profile

    def prioritize(items, preferred):
        items = list(items or [])
        preferred_list = preferred if isinstance(preferred, list) else [preferred] if preferred else []
        ordered = [p for p in preferred_list if p in items]
        return ordered + [x for x in items if x not in ordered]

    profile['measures'] = prioritize(profile.get('measures'), guidance.get('priority_measures') or guidance.get('primary_measure'))
    profile['actual_columns'] = prioritize(profile.get('actual_columns') or profile.get('measures'), guidance.get('priority_measures') or guidance.get('primary_measure'))
    profile['target_columns'] = prioritize(profile.get('target_columns'), guidance.get('target_column'))
    profile['time_columns'] = prioritize(profile.get('time_columns'), guidance.get('time_column'))
    profile['dimensions'] = prioritize(profile.get('dimensions'), guidance.get('priority_dimensions') or guidance.get('primary_dimension'))
    profile['user_guidance'] = guidance
    return profile


def build_dataset_profile(analysis_result: Dict[str, Any], filename: str = "") -> Dict[str, Any]:
    profile = profile_dataset(analysis_result, filename)
    guidance = (analysis_result or {}).get('user_guidance') or {}
    profile = _apply_user_guidance(profile, guidance)
    profile["pattern_profile"] = detect_patterns(profile)
    profile["analysis_classification"] = classify_analysis_type(profile)
    profile = enrich_profile_for_business(profile, analysis_result)
    return profile


def build_profile_prompt(profile: Dict[str, Any]) -> str:
    rows = profile.get("row_count", 0)
    cols = profile.get("column_count", 0)
    col_lines = []
    for c in profile.get("column_profiles", [])[:40]:
        samples = ", ".join(c.get("sample_values") or [])
        col_lines.append(
            f"- {c['name']} | semantic={c['semantic_type']} | role={c['role']} | unique={c['unique_count']} | "
            f"null={c['null_pct']}% | conf={c['confidence']} | hints={','.join(c.get('hints') or []) or 'none'} | samples={samples}"
        )

    opp_lines = [f"- {o['intent']} ({o['priority']}): {o['reason']}" for o in (profile.get("pattern_profile", {}).get("opportunities") or [])[:12]]
    return f"""You are an expert business analyst and chart planner.
You are NOT being asked to infer raw column types from messy data. That has already been profiled for you.
Use the profile below to choose the most meaningful business analysis views.

GOALS:
1. Prioritise business-relevant charts, not just technically valid charts.
2. Prefer strong analytical coverage across KPI, trend, ranking, comparison, contribution, distribution, and forecast readiness.
3. Avoid empty, redundant, or near-duplicate charts.
4. Choose only exact supplied field names.
5. If target/budget columns exist together with actual/achievement columns, prioritise COMBINED actual-vs-target charts in one view before separate charts.
6. If time columns exist, prioritise trends and rolling/cumulative views, and include at least one actual-vs-target time comparison when possible.
7. If a category can show contribution concentration, prioritise a Pareto chart.
8. Apply user guidance aggressively when it exists.

Dataset profile for {profile.get('filename') or 'uploaded file'}
Rows: {rows}
Columns: {cols}
Measures: {', '.join(profile.get('measures') or [])}
Identifiers (NEVER use as axis or KPI): {', '.join(profile.get('identifier_columns') or []) or 'none'}
Dimensions: {', '.join(profile.get('dimensions') or [])}
Time columns: {', '.join(profile.get('time_columns') or [])}
Target columns: {', '.join(profile.get('target_columns') or [])}
Forecast columns: {', '.join(profile.get('forecast_columns') or [])}
Quality flags: {', '.join(profile.get('quality_flags') or []) or 'none'}
User guidance: {profile.get('user_guidance') or {}}

COLUMN PROFILE:
{chr(10).join(col_lines)}

PATTERN OPPORTUNITIES:
{chr(10).join(opp_lines)}

BUSINESS ROLES:
{profile.get('business_roles') or {}}

DERIVED METRICS AVAILABLE:
{profile.get('derived_metrics', {}).get('available') or []}

BUSINESS INSIGHTS:
{profile.get('business_insights', {}).get('kpi_summary') or {}}

If derived metrics are available, actively use them for KPI cards and branch-level comparisons where they improve decision making.
Use achievement_pct, variance_to_target, stock_turnover, stock_movement, and purchase_sales_gap whenever they add real analytical value.

Return ONLY a JSON array of chart specs.
Aim for 8 to 12 strong outputs. Every chart should have a distinct analytical purpose.
Each item must follow this shape:
{{"title":"...","chart_type":"bar|horizontal_bar|line|area|rolling_line|cumulative_line|variance_bar|pareto|waterfall|bullet|progress_ring|scatter|pie|doughnut|histogram|heatmap|kpi","x_axis":"","y_axis":"","aggregation":"sum|mean|count|min|max","group_by":"","color":"violet|blue|emerald|amber|rose|cyan|multi","size":"sm|md|lg|full","x_label":"...","y_label":"...","insight":"A concrete data-aware rationale, not generic text.","is_time_series":true,"combined_date_key":"","target_column":"","extra_measures":["optional second series like target"],"y2_axis":"optional right-axis series"}}
"""


def heuristic_chart_plan(profile: Dict[str, Any], target_count: int = 10) -> List[Dict[str, Any]]:
    """Decision-first heuristic plan used both for manual fallback and as an AI safety net."""
    return build_decision_chart_plan(profile, target_count=target_count)
