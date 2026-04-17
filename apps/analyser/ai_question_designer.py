from __future__ import annotations

import json
from typing import Any, Dict, List

from .analysis_type_classifier import classify_analysis_type

from django.conf import settings

try:
    import anthropic
except Exception:  # pragma: no cover
    anthropic = None


FOCUS_OPTIONS = [
    "Trend over time",
    "Target vs achievement",
    "Top and bottom performers",
    "Contribution / Pareto",
    "Forecasting",
    "Relationship between variables",
    "Distribution and outliers",
]

OUTPUT_OPTIONS = [
    "Full analytical dashboard",
    "Executive summary + charts",
    "Forecast focused",
    "Conservative safe output",
]


def _choice_items(names: List[str]) -> List[Dict[str, str]]:
    seen = set()
    out = []
    for name in names:
        if not name or name in seen:
            continue
        seen.add(name)
        out.append({"value": name, "label": str(name).replace("_", " ").title()})
    return out


def _semantics(profile: Dict[str, Any]) -> Dict[str, Any]:
    return profile.get('business_semantics') or {}


def _semantic_roles(profile: Dict[str, Any]) -> Dict[str, str]:
    return (_semantics(profile).get('roles') or {})


def _semantic_recommended_focus(profile: Dict[str, Any]) -> List[str]:
    semantics = _semantics(profile)
    rec_charts = ((semantics.get('recommendations') or {}).get('charts') or [])
    mapping = {
        'target_vs_actual_trend': 'Target vs achievement',
        'variance_by_dimension': 'Target vs achievement',
        'attainment_ranked_bar': 'Top and bottom performers',
        'profitability_bridge': 'Contribution / Pareto',
        'margin_by_dimension': 'Top and bottom performers',
        'period_variance': 'Trend over time',
        'top_bottom_segments': 'Top and bottom performers',
        'trend_line': 'Trend over time',
        'exception_table': 'Distribution and outliers',
        'balance_trend': 'Trend over time',
        'stock_concentration': 'Contribution / Pareto',
        'movement_waterfall': 'Contribution / Pareto',
        'kpi_summary': 'Executive summary + charts',
    }
    focus=[]
    for chart in rec_charts:
        item=mapping.get(chart)
        if item and item not in focus and item in FOCUS_OPTIONS + OUTPUT_OPTIONS:
            focus.append(item)
    archetype = semantics.get('primary_archetype')
    if archetype == 'target_vs_actual':
        for item in ['Target vs achievement', 'Trend over time', 'Top and bottom performers']:
            if item not in focus:
                focus.append(item)
    elif archetype == 'financial_statement':
        for item in ['Contribution / Pareto', 'Trend over time', 'Top and bottom performers']:
            if item not in focus:
                focus.append(item)
    elif archetype in {'operational_performance', 'inventory_or_balance'}:
        for item in ['Top and bottom performers', 'Trend over time', 'Distribution and outliers']:
            if item not in focus:
                focus.append(item)
    return focus


def _append_question(questions: List[Dict[str, Any]], item: Dict[str, Any]) -> None:
    if item.get('key') and all(q.get('key') != item['key'] for q in questions):
        questions.append(item)


def _semantic_question_extensions(profile: Dict[str, Any], dimensions: List[str]) -> List[Dict[str, Any]]:
    semantics = _semantics(profile)
    roles = semantics.get('roles') or {}
    extras: List[Dict[str, Any]] = []
    hierarchies = semantics.get('hierarchies') or []
    if hierarchies:
        hierarchy_labels = [' > '.join(h) for h in hierarchies if isinstance(h, list) and h]
        if hierarchy_labels:
            extras.append({
                'key': 'comparison_level',
                'label': 'Which breakdown level should the dashboard prioritise first?',
                'help_text': 'Use this when the data has a clear organisational or category hierarchy.',
                'type': 'single_select',
                'required': False,
                'choices': _choice_items(hierarchy_labels + dimensions[:6]),
                'default': hierarchy_labels[0],
            })
    if semantics.get('needs_user_clarification'):
        extras.append({
            'key': 'semantic_confirmation',
            'label': 'Anything here that the system should treat differently?',
            'help_text': 'Optional. Confirm ambiguous fields, business meaning, or reporting assumptions.',
            'type': 'text',
            'required': False,
            'placeholder': 'Example: Treat Achievement as actual sales and compare by branch, not manager.',
            'default': '; '.join((semantics.get('ambiguities') or [])[:2]),
        })
    period_col = roles.get('period_column')
    if period_col and len(profile.get('time_columns') or []) > 1:
        extras.append({
            'key': 'time_story',
            'label': 'How should the trend story be framed?',
            'help_text': f'{period_col} was detected as the best time axis, but you can guide the narrative.',
            'type': 'single_select',
            'required': False,
            'choices': _choice_items(['Trend over time', 'Seasonality', 'Period comparison', 'None']),
            'default': 'Trend over time',
        })
    return extras


def _default_questions(profile: Dict[str, Any]) -> Dict[str, Any]:
    classification = classify_analysis_type(profile)
    semantics = _semantics(profile)
    semantic_roles = semantics.get('roles') or {}
    analysis_type = classification.get('analysis_type', 'general_performance')
    measures = profile.get('measures') or []
    targets = profile.get('target_columns') or []
    times = profile.get('time_columns') or []
    dimensions = profile.get('dimensions') or []
    opps = (profile.get('pattern_profile') or {}).get('opportunities') or []
    detected_focus: List[str] = []
    for opp in opps[:8]:
        mapping = {
            'trend': 'Trend over time',
            'target_tracking': 'Target vs achievement',
            'ranking': 'Top and bottom performers',
            'contribution': 'Contribution / Pareto',
            'forecast': 'Forecasting',
            'correlation': 'Relationship between variables',
            'distribution': 'Distribution and outliers',
        }
        intent = mapping.get(opp.get('intent'))
        if intent and intent not in detected_focus:
            detected_focus.append(intent)
    for focus in _semantic_recommended_focus(profile):
        if focus in FOCUS_OPTIONS and focus not in detected_focus:
            detected_focus.append(focus)
    if not detected_focus:
        detected_focus = FOCUS_OPTIONS[:4]

    summary = semantics.get('summary') or profile.get('ai_context_summary') or (
        f"This looks like a {analysis_type.replace('_', ' ')} dataset with {profile.get('row_count', 0):,} rows and {profile.get('column_count', 0)} columns. "
        f"Likely measures: {', '.join(measures[:4]) or 'none'}. "
        f"Likely dimensions: {', '.join(dimensions[:4]) or 'none'}. "
        f"Likely time fields: {', '.join(times[:3]) or 'none'}."
    )

    if analysis_type in ('target_tracking', 'performance_analysis') or semantics.get('primary_archetype') == 'target_vs_actual':
        detected_focus = ['Target vs achievement', 'Trend over time', 'Top and bottom performers', 'Contribution / Pareto']

    default_measure_order = [semantic_roles.get('primary_measure')] + measures
    default_measure_order = [m for i,m in enumerate(default_measure_order) if m and m not in default_measure_order[:i]]
    default_dims = [semantic_roles.get('primary_dimension'), semantic_roles.get('comparison_dimension')] + dimensions
    default_dims = [d for i,d in enumerate(default_dims) if d and d not in default_dims[:i]]
    target_default = semantic_roles.get('target_measure') or (targets[0] if targets else 'None')
    time_default = semantic_roles.get('period_column') or (times[0] if times else 'None')

    questions: List[Dict[str, Any]] = [
        {
            'key': 'primary_goal',
            'label': 'What should the dashboard prioritise?',
            'help_text': 'Choose up to 3 decision goals. This directly steers KPI and chart selection.',
            'type': 'multi_select',
            'required': True,
            'max_select': 3,
            'choices': _choice_items(detected_focus + [x for x in FOCUS_OPTIONS if x not in detected_focus]),
            'default': detected_focus[:2],
        },
        {
            'key': 'main_measures',
            'label': 'Which measures matter most?',
            'help_text': 'Choose the most important numeric fields for KPIs, trends, and comparisons.',
            'type': 'multi_select',
            'required': True,
            'max_select': 4,
            'choices': _choice_items(default_measure_order[:12]),
            'default': default_measure_order[: min(3, len(default_measure_order))],
        },
        {
            'key': 'target_column',
            'label': 'Which column should be treated as the main target, budget, or benchmark?',
            'help_text': 'Select one if this dataset includes a meaningful benchmark.',
            'type': 'single_select',
            'required': False,
            'choices': _choice_items(([target_default] if target_default and target_default != 'None' else []) + targets[:10] + ['None']),
            'default': target_default,
        },
        {
            'key': 'time_axis',
            'label': 'Which field should drive the time analysis?',
            'help_text': 'Choose the best date, month, year-month, or period field.',
            'type': 'single_select',
            'required': False,
            'choices': _choice_items(([time_default] if time_default and time_default != 'None' else []) + times[:10] + ['None']),
            'default': time_default,
        },
        {
            'key': 'important_dimensions',
            'label': 'Which breakdowns are most useful?',
            'help_text': 'Choose up to 3 dimensions for comparisons and ranking views.',
            'type': 'multi_select',
            'required': True,
            'max_select': 3,
            'choices': _choice_items(default_dims[:15]),
            'default': default_dims[: min(3, len(default_dims))],
        },
        {
            'key': 'output_mode',
            'label': 'What style of output do you want?',
            'help_text': 'This affects how broad the final dashboard should be.',
            'type': 'single_select',
            'required': True,
            'choices': _choice_items(OUTPUT_OPTIONS),
            'default': 'Executive summary + charts' if semantics.get('primary_archetype') in {'financial_statement', 'target_vs_actual'} else OUTPUT_OPTIONS[0],
        },
    ]

    for extra in _semantic_question_extensions(profile, dimensions):
        _append_question(questions, extra)

    _append_question(questions, {
        'key': 'business_context',
        'label': 'Anything specific the dashboard should focus on?',
        'help_text': 'Optional. Example: highlight underperforming branches and target gaps.',
        'type': 'text',
        'required': False,
        'placeholder': 'Describe the business question or reporting goal',
        'default': semantics.get('primary_archetype_display', ''),
    })
    return {
        'dataset_summary': summary,
        'questions': questions[:6],
        'source': 'heuristic',
    }


PROMPT_TEMPLATE = """You are designing a short, high-quality clarification step for an AI analytics SaaS.
First identify the analysis type from the profile and then ask only dataset-specific questions that improve management decision making.
The user uploaded a dataset. Profiling already happened. Design adaptive questions that materially improve chart planning, target mapping, time analysis, and business relevance.
Support multiple answers where relevant.

Return ONLY valid JSON with this shape:
{
  "dataset_summary": "2-3 sentence concise summary",
  "questions": [
    {
      "key": "snake_case_key",
      "label": "Question text",
      "help_text": "Short helper text",
      "type": "single_select|multi_select|text",
      "required": true,
      "max_select": 3,
      "choices": [{"value": "...", "label": "..."}],
      "default": ["..."]
    }
  ]
}

Rules:
- Ask 4 to 6 questions max.
- Questions must vary materially by dataset. Do not return the same generic checklist for every dataset.
- If the dataset is target-tracking, prioritise actual-vs-target, variance, ranking, and contribution questions.
- If the dataset is trend-oriented, prioritise time axis, primary measure, and segmentation questions.
- Use exact supplied field names as choice values.
- Prefer multi_select for goals, measures, and dimensions.
- If there is a likely actual column and a likely target column, ask whether the dashboard should prioritise combined actual-vs-target views.
- If there are multiple valid time fields, ask which should drive the trend story.
- If dimensions look hierarchical, ask which breakdown level matters most.
- Include a text question only if useful.
- Include "None" as a choice when a target or time field may be absent.
- Do not ask about things that are already obvious with high confidence.
- Keep the experience premium and concise.

PROFILE:
{profile_json}

Business semantics may already be inferred inside profile.business_semantics. Use it when strong, and ask only for the highest-value confirmations.
"""


def _call_ai(profile: Dict[str, Any]) -> Dict[str, Any] | None:
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
    if not api_key or anthropic is None:
        return None
    try:
        client = anthropic.Anthropic(api_key=api_key)
        prompt = PROMPT_TEMPLATE.format(profile_json=json.dumps(profile, ensure_ascii=False)[:18000])
        msg = client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=1400,
            system='You create short, structured clarification flows for analytics products. Always return strict JSON.',
            messages=[{'role': 'user', 'content': prompt}],
        )
        text = msg.content[0].text.strip()
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            return json.loads(text[start:end + 1])
    except Exception:
        return None
    return None


def _sanitize_question_pack(pack: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    fallback = _default_questions(profile)
    if not isinstance(pack, dict):
        return fallback
    questions = pack.get('questions')
    if not isinstance(questions, list) or not questions:
        return fallback

    valid_types = {'single_select', 'multi_select', 'text'}
    cleaned = []
    for idx, q in enumerate(questions[:6]):
        if not isinstance(q, dict):
            continue
        q_type = q.get('type')
        if q_type not in valid_types:
            continue
        key = q.get('key') or f'q_{idx+1}'
        label = q.get('label') or key.replace('_', ' ').title()
        item = {
            'key': key,
            'label': label,
            'help_text': q.get('help_text', ''),
            'type': q_type,
            'required': bool(q.get('required', False)),
        }
        if q_type in {'single_select', 'multi_select'}:
            choices = q.get('choices') or []
            norm_choices = []
            seen = set()
            for c in choices:
                if isinstance(c, dict):
                    value = c.get('value')
                    label_c = c.get('label') or value
                else:
                    value = str(c)
                    label_c = value
                if not value or value in seen:
                    continue
                seen.add(value)
                norm_choices.append({'value': value, 'label': label_c})
            if not norm_choices:
                continue
            item['choices'] = norm_choices
            if q_type == 'multi_select':
                item['max_select'] = int(q.get('max_select') or min(3, len(norm_choices)))
                default = q.get('default') or []
                item['default'] = default if isinstance(default, list) else [default]
            else:
                item['default'] = q.get('default') or norm_choices[0]['value']
        else:
            item['placeholder'] = q.get('placeholder', '')
            item['default'] = q.get('default', '')
        cleaned.append(item)

    if not cleaned:
        return fallback
    return {
        'dataset_summary': pack.get('dataset_summary') or fallback['dataset_summary'],
        'questions': cleaned,
        'source': pack.get('source') or 'ai',
    }


def build_ai_question_pack(profile: Dict[str, Any], ai_enabled: bool = False) -> Dict[str, Any]:
    if ai_enabled:
        ai_pack = _call_ai(profile)
        if ai_pack:
            ai_pack['source'] = 'ai_generated'
            return _sanitize_question_pack(ai_pack, profile)
    pack = _default_questions(profile)
    pack['source'] = 'manual_fallback'
    return pack
