from __future__ import annotations

from typing import Any, Dict

from .business_semantics_engine import infer_business_semantics
from .universal_data_intelligence_engine import (
    build_ai_context_summary,
    build_universal_business_insights,
    classify_dataset,
    derive_generic_metrics,
    detect_measure_roles,
    detect_primary_intents,
)


def enrich_profile_for_business(profile: Dict[str, Any], analysis_result: Dict[str, Any]) -> Dict[str, Any]:
    enriched = dict(profile)
    enriched['preview'] = analysis_result.get('preview') or {}

    roles = detect_measure_roles(enriched)
    if roles.get('target_column'):
        targets = list(enriched.get('target_columns') or [])
        if roles['target_column'] not in targets:
            targets.insert(0, roles['target_column'])
        enriched['target_columns'] = targets
    if roles.get('actual_column'):
        actuals = list(enriched.get('actual_columns') or [])
        if roles['actual_column'] not in actuals:
            actuals.insert(0, roles['actual_column'])
        enriched['actual_columns'] = actuals

    semantics = infer_business_semantics(enriched, analysis_result)

    enriched['business_roles'] = {
        'primary_dimension': roles.get('primary_dimension') or (semantics.get('roles') or {}).get('primary_dimension'),
        'secondary_dimension': roles.get('secondary_dimension') or (semantics.get('roles') or {}).get('comparison_dimension'),
        'target_column': roles.get('target_column') or (semantics.get('roles') or {}).get('target_measure'),
        'actual_column': roles.get('actual_column') or (semantics.get('roles') or {}).get('primary_measure'),
        'purchasing_column': roles.get('cost_column'),
        'cost_column': roles.get('cost_column'),
        'profit_column': roles.get('profit_column'),
        'opening_stock_column': roles.get('opening_stock_column'),
        'closing_stock_column': roles.get('closing_stock_column'),
        'volume_column': roles.get('volume_column'),
        'period_column': (semantics.get('roles') or {}).get('period_column'),
    }

    intents = detect_primary_intents(enriched, roles)
    classification = classify_dataset(enriched, roles, intents)
    derived = derive_generic_metrics(enriched, roles)
    insights = build_universal_business_insights(enriched, roles, derived, classification)

    enriched['business_semantics'] = semantics

    enriched['universal_intelligence'] = {
        'schema_agnostic': True,
        'detected_intents': intents,
        'supported_dimensions': list(enriched.get('dimensions') or []),
        'supported_measures': list(enriched.get('measures') or []),
        'supported_time_columns': list(enriched.get('time_columns') or []),
    }
    enriched['analysis_classification'] = classification
    enriched['derived_metrics'] = derived
    enriched['business_insights'] = insights
    enriched['ai_context_summary'] = build_ai_context_summary(enriched, roles, derived, classification, insights)
    if semantics.get('summary'):
        enriched['ai_context_summary'] = f"{enriched['ai_context_summary']} | semantics: {semantics.get('summary')}".strip(' |')
    return enriched
