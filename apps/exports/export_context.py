from __future__ import annotations

from typing import Any, Dict

from apps.analyser.decision_intelligence_engine import build_decision_dashboard
from apps.analyser.dashboard_layout_engine import build_dashboard_layout
from apps.analyser.insight_explanation_engine import attach_explanations
from apps.analyser.metric_type_rendering_engine import attach_metric_rendering
from apps.analyser.chart_confidence_engine import attach_confidence
from apps.analyser.governance_audit_engine import attach_governance, build_export_governance_block
from apps.analyser.dashboard_memory_engine import build_dashboard_memory, apply_memory_to_analysis
from apps.analyser.premium_presentation_engine import build_presentation_polish
from apps.whitelabel.branding_engine import build_branding_payload


def build_export_context(upload: Any, mode: str = 'executive', request: Any = None) -> Dict[str, Any]:
    analysis = upload.analysis_result or {}
    memory = build_dashboard_memory(upload, analysis, request=request)
    branding = build_branding_payload(user=getattr(upload, 'user', None), request=request)
    analysis = apply_memory_to_analysis(analysis, memory)
    charts = list(upload.chart_configs.all().order_by('sort_order', 'created_at')[:12])
    attach_metric_rendering(charts, analysis)
    attach_explanations(charts, analysis)
    attach_confidence(charts, analysis)
    attach_governance(charts, analysis)
    dashboard = build_decision_dashboard(analysis, charts, mode=mode)
    profile = analysis.get('profile_json') or {}
    layout = build_dashboard_layout(charts, profile)
    presentation_polish = build_presentation_polish(upload, analysis, dashboard, charts)
    ctx = {
        'upload': upload,
        'mode': mode,
        'analysis': analysis,
        'charts': charts,
        'dashboard': dashboard,
        'layout': layout,
        'profile': profile,
        'dashboard_memory': memory,
        'exception_tables': dashboard.get('exception_tables') or [],
        'decision_cards': dashboard.get('decision_cards') or [],
        'sections': dashboard.get('sections') or [],
        'presentation_polish': presentation_polish,
        'branding': branding,
        'scenario_context': analysis.get('scenario_context') or {},
    }
    ctx['governance'] = build_export_governance_block(ctx)
    return ctx
