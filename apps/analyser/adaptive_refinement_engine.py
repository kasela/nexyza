from __future__ import annotations

from typing import Any, Dict, List

from .ai_question_designer import build_ai_question_pack
from .analysis_type_classifier import classify_analysis_type


def _label(value: str) -> str:
    return str(value or '').replace('_', ' ').replace('-', ' ').title()


def classify_dataset(profile: Dict[str, Any], screening: Dict[str, Any] | None = None) -> Dict[str, Any]:
    screening = screening or {}
    classification = classify_analysis_type(profile)
    semantics = profile.get('business_semantics') or {}
    primary = semantics.get('primary_archetype') or classification.get('analysis_type') or 'generic_tabular'
    secondary: List[str] = []
    if profile.get('time_columns'):
        secondary.append('time_series')
    if profile.get('target_columns') or ((semantics.get('roles') or {}).get('target_measure')):
        secondary.append('target_tracking')
    if len(profile.get('dimensions') or []) >= 2:
        secondary.append('categorical_comparison')
    if (profile.get('row_count') or 0) > 5000:
        secondary.append('high_volume')
    confidence = semantics.get('overall_confidence') or 72
    try:
        confidence = float(confidence)
        if confidence <= 1:
            confidence *= 100
    except Exception:
        confidence = 72
    return {
        'primary_type': primary,
        'primary_label': semantics.get('primary_archetype_display') or _label(primary),
        'secondary_patterns': secondary,
        'confidence': confidence,
        'reason': screening.get('analysis_reason') or classification.get('reason', ''),
        'priorities': screening.get('decision_priorities') or classification.get('priorities', []),
    }


def build_question_schema(profile: Dict[str, Any], screening: Dict[str, Any] | None = None, ai_enabled: bool = False) -> Dict[str, Any]:
    question_pack = build_ai_question_pack(profile, ai_enabled=ai_enabled)
    return {
        'dataset_summary': question_pack.get('dataset_summary', ''),
        'source': question_pack.get('source', 'manual_fallback'),
        'questions': question_pack.get('questions', []),
        'classification': classify_dataset(profile, screening),
    }


def _pick_first(value: Any, fallback: str = '') -> str:
    if isinstance(value, list):
        return str(value[0]) if value else fallback
    return str(value or fallback)


def build_recommendations(profile: Dict[str, Any], screening: Dict[str, Any], answers: Dict[str, Any]) -> Dict[str, Any]:
    semantics = profile.get('business_semantics') or {}
    roles = semantics.get('roles') or {}
    priorities = answers.get('primary_goal') or screening.get('recommended_focus') or []
    if not isinstance(priorities, list):
        priorities = [priorities]
    measures = answers.get('main_measures') or []
    if not measures:
        seed = roles.get('primary_measure') or ''
        measures = [seed] if seed else list(profile.get('measures') or [])
    if not isinstance(measures, list):
        measures = [measures]
    dimensions = answers.get('important_dimensions') or []
    if not dimensions:
        seed_dims = [roles.get('primary_dimension'), roles.get('comparison_dimension')]
        dimensions = [d for d in seed_dims if d] or list(profile.get('dimensions') or [])
    if not isinstance(dimensions, list):
        dimensions = [dimensions]
    time_axis = answers.get('time_axis') or roles.get('period_column') or _pick_first(profile.get('time_columns'))
    target = answers.get('target_column') or roles.get('target_measure') or _pick_first(profile.get('target_columns'))
    output_mode = answers.get('output_mode') or 'Executive summary + charts'
    context_note = str(answers.get('business_context') or '').strip()

    sections = ['Executive KPIs', 'Comparison analysis']
    chart_family = ['kpi', 'bar']
    if time_axis and str(time_axis).lower() != 'none':
        sections.append('Trend analysis')
        chart_family.append('line')
    if target and str(target).lower() != 'none':
        sections.append('Variance and attainment')
        chart_family.extend(['variance_bar', 'bullet'])
    if 'Contribution / Pareto' in priorities:
        sections.append('Contribution mix')
        chart_family.append('pareto')
    if 'Distribution and outliers' in priorities:
        sections.append('Distribution and exceptions')
        chart_family.extend(['histogram', 'scatter'])
    if output_mode == 'Executive summary + charts':
        sections = ['Executive summary'] + [s for s in sections if s != 'Executive KPIs']

    chart_priority = []
    primary_dim = _pick_first(dimensions)
    primary_measure = _pick_first(measures)
    if primary_dim and primary_measure:
        chart_priority.append({'type': 'bar', 'x': primary_dim, 'y': primary_measure, 'purpose': 'Primary comparison'})
    if time_axis and primary_measure and str(time_axis).lower() != 'none':
        chart_priority.append({'type': 'line', 'x': time_axis, 'y': primary_measure, 'purpose': 'Trend story'})
    if target and primary_dim and primary_measure and str(target).lower() != 'none':
        chart_priority.append({'type': 'variance_bar', 'x': primary_dim, 'y': primary_measure, 'benchmark': target, 'purpose': 'Target gap'})

    return {
        'priorities': priorities[:3],
        'main_measures': measures[:4],
        'important_dimensions': dimensions[:3],
        'time_axis': time_axis,
        'target_column': target,
        'output_mode': output_mode,
        'recommended_sections': sections,
        'chart_family': list(dict.fromkeys(chart_family)),
        'chart_priority': chart_priority,
        'business_context_note': context_note,
        'dataset_summary': screening.get('dataset_summary') or '',
    }
