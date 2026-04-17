from __future__ import annotations

from typing import Any, Dict

SESSION_PREFIX = 'nexyza_dashboard_memory:'
DEFAULTS = {
    'audience': 'executive',
    'focus': 'balanced',
    'grouping': '',
    'density': 'compact',
    'kpi_style': 'summary',
    'mode': 'executive',
}
ALLOWED = {
    'audience': {'executive', 'manager', 'analyst'},
    'focus': {'balanced', 'underperformance', 'growth', 'risk', 'trend', 'benchmark'},
    'grouping': set(),
    'density': {'compact', 'balanced', 'detailed'},
    'kpi_style': {'summary', 'comparison', 'sparkline'},
    'mode': {'executive', 'explorer'},
}


def _session_key(upload: Any) -> str:
    return f"{SESSION_PREFIX}{getattr(upload, 'id', '')}"


def _conversation_memory(analysis: Dict[str, Any]) -> Dict[str, Any]:
    brief = (analysis or {}).get('analysis_conversation_brief') or {}
    guidance = (analysis or {}).get('analysis_user_guidance') or {}
    memory: Dict[str, Any] = {}
    # tolerate several possible keys from previous chat flow
    audience = guidance.get('audience') or brief.get('audience') or guidance.get('preferred_audience')
    if audience:
        memory['audience'] = str(audience).lower()
    focus = guidance.get('focus') or brief.get('focus') or guidance.get('preferred_focus')
    if focus:
        memory['focus'] = str(focus).lower().replace(' ', '_')
    grouping = guidance.get('group_by') or brief.get('group_by') or guidance.get('preferred_grouping')
    if grouping:
        memory['grouping'] = str(grouping)
    density = guidance.get('density') or brief.get('density') or guidance.get('preferred_density')
    if density:
        memory['density'] = str(density).lower()
    kpi_style = guidance.get('kpi_style') or brief.get('kpi_style')
    if kpi_style:
        memory['kpi_style'] = str(kpi_style).lower()
    mode = guidance.get('mode') or brief.get('mode')
    if mode:
        memory['mode'] = str(mode).lower()
    return memory


def _sanitize(memory: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    clean = dict(DEFAULTS)
    dims = set(profile.get('dimensions') or [])
    for key, value in (memory or {}).items():
        if value in (None, ''):
            continue
        if key == 'grouping':
            if not dims or value in dims:
                clean[key] = value
            continue
        allowed = ALLOWED.get(key)
        if allowed and value in allowed:
            clean[key] = value
    return clean


def _request_memory(request: Any, profile: Dict[str, Any]) -> Dict[str, Any]:
    if request is None:
        return {}
    src = request.POST if getattr(request, 'method', 'GET') == 'POST' else request.GET
    out = {
        'audience': src.get('audience', ''),
        'focus': src.get('focus', ''),
        'grouping': src.get('grouping', ''),
        'density': src.get('density', ''),
        'kpi_style': src.get('kpi_style', ''),
        'mode': src.get('mode', ''),
    }
    return _sanitize(out, profile)


def build_dashboard_memory(upload: Any, analysis: Dict[str, Any], request: Any = None) -> Dict[str, Any]:
    profile = (analysis or {}).get('profile_json') or {}
    session_memory = {}
    if request is not None and hasattr(request, 'session'):
        session_memory = request.session.get(_session_key(upload), {}) or {}
    memory = _sanitize(_conversation_memory(analysis), profile)
    memory.update(_sanitize(session_memory, profile))
    req_memory = _request_memory(request, profile)
    # only override with request values user explicitly supplied
    for k, v in req_memory.items():
        if v not in ('', None):
            memory[k] = v
    memory = _sanitize(memory, profile)
    if request is not None and hasattr(request, 'session'):
        request.session[_session_key(upload)] = memory
    return memory


def apply_memory_to_analysis(analysis: Dict[str, Any], memory: Dict[str, Any]) -> Dict[str, Any]:
    analysis = dict(analysis or {})
    analysis['dashboard_memory'] = memory or {}
    return analysis
