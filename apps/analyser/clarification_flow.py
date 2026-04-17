from __future__ import annotations

from typing import Any, Dict, Iterable, List


_GOAL_MAP = {
    'Trend over time': 'trend',
    'Target vs achievement': 'target_tracking',
    'Top and bottom performers': 'ranking',
    'Contribution / Pareto': 'contribution',
    'Forecasting': 'forecast',
    'Relationship between variables': 'correlation',
    'Distribution and outliers': 'distribution',
}


def build_clarification_questions(profile: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Backwards-compatible fallback. Richer question design lives in ai_question_designer."""
    from .ai_question_designer import build_ai_question_pack
    return build_ai_question_pack(profile, ai_enabled=False).get('questions', [])



def _prioritized_list(values: Iterable[str]) -> List[str]:
    out: List[str] = []
    seen = set()
    for v in values or []:
        if not v or v in {'None', 'none'}:
            continue
        if v not in seen:
            seen.add(v)
            out.append(v)
    return out



def guidance_from_answers(answers: Dict[str, Any]) -> Dict[str, Any]:
    primary_goals = answers.get('primary_goal') or answers.get('analysis_focus') or []
    if isinstance(primary_goals, str):
        primary_goals = [primary_goals] if primary_goals else []

    main_measures = answers.get('main_measures') or []
    if isinstance(main_measures, str):
        main_measures = [main_measures] if main_measures else []

    important_dimensions = answers.get('important_dimensions') or []
    if isinstance(important_dimensions, str):
        important_dimensions = [important_dimensions] if important_dimensions else []

    time_column = answers.get('time_axis') or answers.get('time_column') or ''
    target_column = answers.get('target_column') or ''

    guidance = {
        'decision_mode': 'decision_first',
        'primary_goals': primary_goals,
        'analysis_focus': _GOAL_MAP.get(primary_goals[0], 'general') if primary_goals else 'general',
        'priority_measures': _prioritized_list(main_measures),
        'primary_measure': _prioritized_list(main_measures)[0] if _prioritized_list(main_measures) else (answers.get('primary_measure') or ''),
        'priority_dimensions': _prioritized_list(important_dimensions),
        'primary_dimension': _prioritized_list(important_dimensions)[0] if _prioritized_list(important_dimensions) else (answers.get('primary_dimension') or ''),
        'target_column': '' if target_column in {'', 'None', None} else target_column,
        'time_column': '' if time_column in {'', 'None', None} else time_column,
        'output_mode': answers.get('output_mode') or 'Full analytical dashboard',
        'business_context': (answers.get('business_context') or '').strip(),
    }
    return guidance
