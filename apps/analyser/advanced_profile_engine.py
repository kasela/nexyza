from __future__ import annotations

import json
from typing import Any, Dict, List

from django.utils import timezone
from django.conf import settings

from .ai_policy import get_ai_access_context

try:
    import anthropic
except Exception:  # pragma: no cover
    anthropic = None


def _safe_list(values, limit: int = 12) -> List[Any]:
    out = []
    for v in (values or [])[:limit]:
        if v is None:
            continue
        out.append(v)
    return out


def _safe_text(v: Any) -> str:
    if v is None:
        return ""
    return str(v).strip()


def _fallback_advanced_profile(profile: Dict[str, Any], analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    semantics = profile.get('business_semantics') or {}
    roles = profile.get('business_roles') or {}
    insights = profile.get('business_insights') or {}
    classification = profile.get('analysis_classification') or {}
    columns = profile.get('column_profiles') or []

    quality_flags = list(profile.get('quality_flags') or [])
    null_heavy = [c['name'] for c in columns if float(c.get('null_pct') or 0) >= 25][:8]
    high_card = [c['name'] for c in columns if c.get('cardinality') == 'high'][:8]

    executive_summary = [
        f"Dataset has {profile.get('row_count', 0):,} rows and {profile.get('column_count', 0)} columns.",
        f"Primary analysis type appears to be {_safe_text(classification.get('analysis_type') or 'general analysis').replace('_', ' ')}.",
    ]
    if semantics.get('summary'):
        executive_summary.append(_safe_text(semantics.get('summary')))
    if insights.get('narrative_summary'):
        executive_summary.append(_safe_text(insights.get('narrative_summary')))

    dashboard_blueprint = {
        'primary_kpis': _safe_list((((semantics.get('recommendations') or {}).get('kpis')) or []), 8),
        'primary_filters': _safe_list(profile.get('dimensions') or [], 8),
        'time_axis': roles.get('period_column') or ((profile.get('time_columns') or [''])[:1] or [''])[0],
        'primary_dimension': roles.get('primary_dimension') or ((profile.get('dimensions') or [''])[:1] or [''])[0],
        'primary_measure': roles.get('actual_column') or ((profile.get('actual_columns') or profile.get('measures') or [''])[:1] or [''])[0],
        'target_measure': roles.get('target_column') or ((profile.get('target_columns') or [''])[:1] or [''])[0],
        'recommended_story': _safe_list((((semantics.get('recommendations') or {}).get('charts')) or []), 10),
        'decision_questions': _safe_list((((semantics.get('recommendations') or {}).get('questions')) or []), 10),
    }

    return {
        'version': '1.0',
        'source': 'deterministic_fallback',
        'generated_at': timezone.now().isoformat(),
        'dataset_identity': {
            'filename': profile.get('filename', ''),
            'rows': profile.get('row_count', 0),
            'columns': profile.get('column_count', 0),
            'file_type': analysis_result.get('file_type') or '',
        },
        'executive_summary': executive_summary[:4],
        'schema_overview': {
            'measures': _safe_list(profile.get('measures') or [], 15),
            'dimensions': _safe_list(profile.get('dimensions') or [], 15),
            'time_columns': _safe_list(profile.get('time_columns') or [], 10),
            'target_columns': _safe_list(profile.get('target_columns') or [], 10),
            'forecast_columns': _safe_list(profile.get('forecast_columns') or [], 10),
            'actual_columns': _safe_list(profile.get('actual_columns') or [], 10),
        },
        'quality_assessment': {
            'flags': quality_flags,
            'duplicate_columns': _safe_list(profile.get('duplicate_column_names') or [], 10),
            'high_null_columns': null_heavy,
            'high_cardinality_dimensions': high_card,
        },
        'semantic_layer': {
            'dataset_type': semantics.get('primary_archetype_display') or semantics.get('primary_archetype') or '',
            'summary': semantics.get('summary') or '',
            'overall_confidence': semantics.get('overall_confidence') or 0,
            'roles': roles,
        },
        'measure_catalog': [
            {
                'name': c.get('name'),
                'semantic_type': c.get('semantic_type'),
                'stats': c.get('stats') or {},
                'hints': c.get('hints') or [],
            }
            for c in columns if c.get('role') == 'measure'
        ][:20],
        'dimension_catalog': [
            {
                'name': c.get('name'),
                'semantic_type': c.get('semantic_type'),
                'cardinality': c.get('cardinality'),
                'sample_values': _safe_list(c.get('sample_values') or [], 6),
            }
            for c in columns if c.get('role') in {'dimension', 'time'}
        ][:20],
        'dashboard_blueprint': dashboard_blueprint,
        'business_insight_snapshot': {
            'kpi_summary': insights.get('kpi_summary') or {},
            'narrative_summary': insights.get('narrative_summary') or '',
            'anomalies': _safe_list(insights.get('anomalies') or [], 8),
            'opportunities': _safe_list(((profile.get('pattern_profile') or {}).get('opportunities')) or [], 8),
        },
        'download_ready': True,
    }


def _build_prompt(profile: Dict[str, Any], analysis_result: Dict[str, Any]) -> str:
    cols = []
    for c in (profile.get('column_profiles') or [])[:35]:
        cols.append(
            f"- {c.get('name')} | role={c.get('role')} | semantic={c.get('semantic_type')} | "
            f"null={c.get('null_pct')} | unique={c.get('unique_count')} | hints={','.join(c.get('hints') or [])}"
        )
    return f"""You are a senior analytics architect.
Return ONLY valid JSON. No markdown.

Build an advanced data profile for a dashboard builder from this profiled dataset.
Focus on dashboard design, KPI logic, filter design, business semantics, quality risks, and JSON download usefulness.

Dataset: {profile.get('filename')}
Rows: {profile.get('row_count')}
Columns: {profile.get('column_count')}
Measures: {profile.get('measures')}
Dimensions: {profile.get('dimensions')}
Time columns: {profile.get('time_columns')}
Target columns: {profile.get('target_columns')}
Business roles: {profile.get('business_roles')}
Classification: {profile.get('analysis_classification')}
Semantics summary: {(profile.get('business_semantics') or {}).get('summary')}
AI context summary: {profile.get('ai_context_summary')}
Quality flags: {profile.get('quality_flags')}

COLUMN PROFILES:
{chr(10).join(cols)}

Return this exact top-level shape:
{{
  "version": "1.0",
  "source": "ai_generated",
  "generated_at": "ISO timestamp string",
  "dataset_identity": {{"filename":"","rows":0,"columns":0,"file_type":""}},
  "executive_summary": ["3 to 5 concise bullets"],
  "schema_overview": {{"measures":[],"dimensions":[],"time_columns":[],"target_columns":[],"forecast_columns":[],"actual_columns":[]}},
  "quality_assessment": {{"flags":[],"high_null_columns":[],"high_cardinality_dimensions":[],"notes":[]}},
  "semantic_layer": {{"dataset_type":"","summary":"","overall_confidence":0,"roles":{{}}}},
  "measure_catalog": [{{"name":"","semantic_type":"","business_role":"","recommended_aggregations":[],"notes":""}}],
  "dimension_catalog": [{{"name":"","semantic_type":"","cardinality":"","recommended_as_filter":true,"notes":""}}],
  "dashboard_blueprint": {{
    "primary_kpis": [],
    "primary_filters": [],
    "time_axis": "",
    "primary_dimension": "",
    "primary_measure": "",
    "target_measure": "",
    "recommended_story": [],
    "decision_questions": []
  }},
  "business_insight_snapshot": {{"narrative_summary":"","opportunities":[],"anomalies":[]}},
  "download_ready": true
}}
"""


def build_advanced_profile(profile: Dict[str, Any], analysis_result: Dict[str, Any], user=None) -> Dict[str, Any]:
    fallback = _fallback_advanced_profile(profile, analysis_result)
    ctx = get_ai_access_context(user, feature='upload_screening', estimated_tokens=1800)
    api_key = getattr(settings, 'ANTHROPIC_API_KEY', '')
    if not (ctx.get('ai_enabled') and api_key and anthropic):
        return fallback
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(
            model='claude-sonnet-4-20250514',
            max_tokens=1800,
            system='You produce strict JSON analytics metadata for BI applications.',
            messages=[{'role': 'user', 'content': _build_prompt(profile, analysis_result)}],
        )
        text = (msg.content[0].text or '').strip()
        start = text.find('{')
        end = text.rfind('}')
        if start >= 0 and end > start:
            text = text[start:end+1]
        parsed = json.loads(text)
        if not isinstance(parsed, dict):
            return fallback
        parsed.setdefault('version', '1.0')
        parsed['source'] = 'ai_generated'
        parsed.setdefault('generated_at', timezone.now().isoformat())
        parsed.setdefault('download_ready', True)
        return parsed
    except Exception:
        return fallback
