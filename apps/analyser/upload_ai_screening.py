from __future__ import annotations

from typing import Any, Dict

from django.conf import settings

from .ai_profile_planner import build_dataset_profile, heuristic_chart_plan
from .analysis_type_classifier import classify_analysis_type
from .ai_question_designer import build_ai_question_pack
from .models import UploadAnalysisProfile
from .ai_policy import get_ai_access_context





def build_screening_summary(profile: Dict[str, Any], ai_context: Dict[str, Any]) -> Dict[str, Any]:
    opps = (profile.get('pattern_profile') or {}).get('opportunities') or []
    focus = [o.get('intent') for o in opps[:5] if o.get('intent')]
    classification = classify_analysis_type(profile)
    return {
        'ai_enabled': ai_context.get('ai_enabled', False),
        'ai_source': ai_context.get('source', 'manual'),
        'ai_reason': ai_context.get('reason', ''),
        'ai_message': ai_context.get('message', ''),
        'upgrade_required': ai_context.get('upgrade_required', False),
        'purchase_tokens_recommended': ai_context.get('purchase_tokens_recommended', False),
        'remaining_tokens': ai_context.get('remaining_tokens'),
        'recommended_focus': focus,
        'analysis_type': classification.get('analysis_type', 'general_performance'),
        'analysis_reason': classification.get('reason', ''),
        'ai_context_summary': profile.get('ai_context_summary', ''),
        'business_insights': profile.get('business_insights', {}),
        'business_roles': profile.get('business_roles', {}),
        'derived_metrics': profile.get('derived_metrics', {}),
        'business_semantics': profile.get('business_semantics', {}),
        'semantic_summary': ((profile.get('business_semantics') or {}).get('summary') or ''),
        'semantic_dataset_type': ((profile.get('business_semantics') or {}).get('primary_archetype_display') or classification.get('analysis_type', 'general_performance').replace('_', ' ').title()),
        'semantic_confidence': ((profile.get('business_semantics') or {}).get('overall_confidence') or 0),
        'semantic_kpis': (((profile.get('business_semantics') or {}).get('recommendations') or {}).get('kpis') or []),
        'semantic_charts': (((profile.get('business_semantics') or {}).get('recommendations') or {}).get('charts') or []),
        'semantic_questions': (((profile.get('business_semantics') or {}).get('recommendations') or {}).get('questions') or []),
        'decision_priorities': classification.get('priorities', []),
        'recommended_main_measure': ((profile.get('business_semantics') or {}).get('roles') or {}).get('primary_measure') or (profile.get('actual_columns') or profile.get('measures') or [''])[0],
        'recommended_time_column': ((profile.get('business_semantics') or {}).get('roles') or {}).get('period_column') or (profile.get('time_columns') or [''])[0],
        'recommended_target_column': ((profile.get('business_semantics') or {}).get('roles') or {}).get('target_measure') or (profile.get('target_columns') or [''])[0],
        'heuristic_chart_plan': heuristic_chart_plan(profile, target_count=10),
        'question_count': 0,
    }


def run_upload_screening(upload) -> UploadAnalysisProfile:
    analysis_result = upload.analysis_result or {}
    profile_json = build_dataset_profile(analysis_result, upload.original_name)
    ai_context = get_ai_access_context(getattr(upload, 'user', None), feature='upload_screening', estimated_tokens=2500)
    screening_json = build_screening_summary(profile_json, ai_context)
    question_pack = build_ai_question_pack(profile_json, ai_enabled=ai_context.get('ai_enabled', False))
    questions = question_pack.get('questions') or []
    screening_json['question_count'] = len(questions)
    screening_json['screening_ai_used'] = bool(ai_context.get('ai_enabled') and question_pack.get('source') == 'ai_generated')

    # Profile review chat is disabled — auto-screening provides sufficient context.
    requires_clarification = False

    obj, _ = UploadAnalysisProfile.objects.update_or_create(
        upload=upload,
        defaults={
            'profile_json': profile_json,
            'screening_json': {**screening_json, 'dataset_summary': question_pack.get('dataset_summary', ''), 'question_source': question_pack.get('source', 'manual_fallback')},
            'question_payload': questions,
            'requires_clarification': requires_clarification,
        }
    )
    return obj
