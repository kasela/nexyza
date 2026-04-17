from __future__ import annotations

from typing import Any, Dict, List

from .narrative_dashboard_engine import build_narrative_dashboard
from .insight_explanation_engine import explain_narrative_cards
from .exception_table_engine import build_exception_tables


SEVERITY_WEIGHT = {
    'critical': 100,
    'high': 80,
    'medium': 55,
    'low': 30,
}

SECTION_WEIGHT = {
    'executive': 90,
    'trend': 80,
    'performance': 75,
    'ranking': 68,
    'inventory': 72,
    'composition': 48,
    'diagnostics': 40,
}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _money(value: Any) -> str:
    v = _safe_float(value)
    sign = '-' if v < 0 else ''
    v = abs(v)
    if v >= 1_000_000_000:
        return f"{sign}{v/1_000_000_000:.2f}B"
    if v >= 1_000_000:
        return f"{sign}{v/1_000_000:.2f}M"
    if v >= 1_000:
        return f"{sign}{v/1_000:.1f}K"
    return f"{sign}{v:,.0f}"


def _pct(value: Any, digits: int = 2) -> str:
    try:
        return f"{float(value):.{digits}f}%"
    except Exception:
        return '—'


def _get_profile(analysis: Dict[str, Any]) -> Dict[str, Any]:
    return (analysis or {}).get('profile_json') or {}


def _get_insights(analysis: Dict[str, Any]) -> Dict[str, Any]:
    profile = _get_profile(analysis)
    screening = (analysis or {}).get('screening_json') or {}
    return profile.get('business_insights') or screening.get('business_insights') or {}


def _get_roles(analysis: Dict[str, Any]) -> Dict[str, Any]:
    profile = _get_profile(analysis)
    screening = (analysis or {}).get('screening_json') or {}
    return profile.get('business_roles') or screening.get('business_roles') or {}


def detect_decision_signals(analysis: Dict[str, Any]) -> List[Dict[str, Any]]:
    insights = _get_insights(analysis)
    roles = _get_roles(analysis)
    kpi = insights.get('kpi_summary') or {}
    signals: List[Dict[str, Any]] = []

    achievement_pct_total = kpi.get('achievement_pct_total')
    if achievement_pct_total is not None:
        sev = 'critical' if _safe_float(achievement_pct_total) < 70 else 'high' if _safe_float(achievement_pct_total) < 90 else 'medium'
        signals.append({
            'type': 'delivery',
            'severity': sev,
            'title': 'Overall target delivery',
            'message': f"Overall achievement is {_pct(achievement_pct_total)}.",
            'action': 'Start with target vs actual and variance before exploring lower-priority charts.',
            'score': SEVERITY_WEIGHT[sev] + 10,
            'keywords': ['achievement', 'target', 'variance', 'attainment'],
        })

    worst_branch = kpi.get('worst_branch')
    if worst_branch:
        signals.append({
            'type': 'underperformance',
            'severity': 'critical',
            'title': 'Weakest segment',
            'message': f"{worst_branch} is the weakest entity on current delivery.",
            'action': 'Surface branch ranking and variance views early, then drill into the responsible manager or region.',
            'score': SEVERITY_WEIGHT['critical'] + 12,
            'keywords': [str(worst_branch).lower(), 'branch', 'ranking', 'variance'],
        })

    best_branch = kpi.get('best_branch')
    if best_branch:
        signals.append({
            'type': 'benchmark',
            'severity': 'medium',
            'title': 'Benchmark candidate',
            'message': f"{best_branch} is the current top performer.",
            'action': 'Use this leader as the benchmark pattern for weaker segments.',
            'score': SEVERITY_WEIGHT['medium'] + 8,
            'keywords': [str(best_branch).lower(), 'top', 'achievement', 'ranking'],
        })

    inventory_alerts = insights.get('inventory_alerts') or []
    if inventory_alerts:
        top_alert = inventory_alerts[0]
        entity = top_alert.get('dimension_value') or 'A segment'
        gap_value = top_alert.get('gap_value')
        signals.append({
            'type': 'inventory',
            'severity': 'high',
            'title': 'Inventory pressure',
            'message': f"{entity} shows stock build-up risk with a gap of {_money(gap_value)}.",
            'action': 'Prioritise stock movement, turnover, and purchase-vs-sales diagnostics after the main performance view.',
            'score': SEVERITY_WEIGHT['high'] + 9,
            'keywords': [str(entity).lower(), 'inventory', 'stock', 'turnover', 'purchase', 'gap'],
        })

    if roles.get('actual_column') and roles.get('target_column'):
        signals.append({
            'type': 'variance',
            'severity': 'high',
            'title': 'Variance matters',
            'message': 'The uploaded file supports direct target-versus-actual decision making.',
            'action': 'Keep variance and attainment visuals above composition and diagnostics.',
            'score': SEVERITY_WEIGHT['high'] + 5,
            'keywords': ['variance', 'target', 'actual', 'achievement'],
        })

    return sorted(signals, key=lambda x: x.get('score', 0), reverse=True)


def _score_chart(chart: Any, section_key: str, signals: List[Dict[str, Any]]) -> int:
    score = SECTION_WEIGHT.get(section_key, 35)
    title = ((getattr(chart, 'title', '') or '') + ' ' + (getattr(chart, 'chart_type', '') or '')).lower()
    ctype = (getattr(chart, 'chart_type', '') or '').lower()
    if ctype == 'kpi':
        score += 25
    elif ctype in {'line', 'area'}:
        score += 14
    elif ctype in {'horizontal_bar', 'bar', 'variance_bar'}:
        score += 12
    elif ctype in {'scatter', 'pie', 'doughnut'}:
        score -= 12

    for signal in signals[:5]:
        keywords = signal.get('keywords') or []
        if any(k and k in title for k in keywords):
            score += 18
        if signal.get('type') == 'variance' and ('variance' in title or 'target' in title or 'achievement' in title):
            score += 12
        if signal.get('type') == 'inventory' and any(k in title for k in ['stock', 'inventory', 'turnover', 'purchase', 'gap']):
            score += 12

    if 'distribution' in title or 'diagnostic' in title:
        score -= 6
    return score


def build_decision_dashboard(analysis: Dict[str, Any], charts: List[Any], mode: str = 'executive') -> Dict[str, Any]:
    base = build_narrative_dashboard(analysis, charts)
    signals = detect_decision_signals(analysis)

    scored_sections: List[Dict[str, Any]] = []
    scored_cards: List[Dict[str, Any]] = []
    for section in base.get('sections') or []:
        charts_in_section = []
        for chart in section.get('charts') or []:
            chart_score = _score_chart(chart, section.get('key', ''), signals)
            setattr(chart, '_decision_score', chart_score)
            charts_in_section.append(chart)
            scored_cards.append({'chart': chart, 'section': section.get('key', ''), 'score': chart_score})
        charts_in_section.sort(key=lambda c: getattr(c, '_decision_score', 0), reverse=True)
        scored_sections.append({**section, 'charts': charts_in_section})

    scored_cards.sort(key=lambda x: x['score'], reverse=True)

    if mode not in {'executive', 'explorer'}:
        mode = 'executive'

    if mode == 'executive':
        budget = 6
        executive_sections = []
        remaining = budget
        for section in scored_sections:
            if remaining <= 0:
                break
            kept = section['charts'][: min(len(section['charts']), 2 if section['key'] in {'executive', 'trend', 'performance'} else 1, remaining)]
            if kept:
                executive_sections.append({**section, 'charts': kept})
                remaining -= len(kept)
        sections = executive_sections
    else:
        sections = scored_sections

    decision_cards = []
    for signal in signals[:4]:
        label_map = {
            'delivery': ('Priority', '🧭'),
            'underperformance': ('Problem', '🔴'),
            'benchmark': ('Opportunity', '🟢'),
            'inventory': ('Risk', '🟠'),
            'variance': ('Observation', '🟡'),
        }
        label, emoji = label_map.get(signal.get('type'), ('Signal', '✨'))
        decision_cards.append({
            'label': label,
            'emoji': emoji,
            'title': signal.get('title', 'Key signal'),
            'body': signal.get('message', ''),
            'action': signal.get('action', ''),
            'severity': signal.get('severity', 'medium'),
        })

    base['sections'] = sections
    base['exception_tables'] = build_exception_tables(analysis)
    base['decision_cards'] = explain_narrative_cards(decision_cards)
    base['signals'] = signals
    base['mode'] = mode
    base['mode_label'] = 'Executive mode' if mode == 'executive' else 'Explorer mode'
    base['visible_chart_count'] = sum(len(s.get('charts') or []) for s in sections)
    base['top_chart_titles'] = [getattr(item['chart'], 'title', '') for item in scored_cards[:5]]
    return base
