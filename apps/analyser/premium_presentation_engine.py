from __future__ import annotations

from typing import Any, Dict, Iterable, List


def _priority_from_chart(chart: Any) -> str:
    meta = getattr(chart, 'confidence_meta', {}) or {}
    score = float(meta.get('final_chart_confidence') or 0)
    if score >= 0.82:
        return 'primary'
    if score >= 0.62:
        return 'secondary'
    return 'supporting'


def _tone_from_priority(priority: str) -> str:
    return {
        'primary': 'violet',
        'secondary': 'blue',
        'supporting': 'slate',
    }.get(priority, 'slate')


def _section_surface(index: int) -> str:
    sequence = ['violet', 'blue', 'emerald', 'amber', 'slate']
    return sequence[index % len(sequence)]


def build_presentation_polish(upload: Any, analysis: Dict[str, Any], dashboard: Dict[str, Any], charts: Iterable[Any]) -> Dict[str, Any]:
    charts = list(charts or [])
    visible_chart_count = len(charts)
    high_conf = sum(1 for c in charts if (getattr(c, 'confidence_meta', {}) or {}).get('final_chart_confidence', 0) >= 0.82)
    mid_conf = sum(1 for c in charts if 0.62 <= (getattr(c, 'confidence_meta', {}) or {}).get('final_chart_confidence', 0) < 0.82)
    suppressed = int((dashboard or {}).get('suppressed_count') or 0)

    hero = (dashboard or {}).get('hero') or {}
    hero_emphasis = 'calm'
    if hero.get('status') and any(k in hero.get('status', '').lower() for k in ['critical', 'risk', 'below', 'behind']):
        hero_emphasis = 'urgent'
    elif high_conf >= 3:
        hero_emphasis = 'strong'

    section_styles: Dict[str, Dict[str, Any]] = {}
    for idx, section in enumerate((dashboard or {}).get('sections') or []):
        key = section.get('key') or f'section-{idx}'
        section_styles[key] = {
            'surface': _section_surface(idx),
            'density': 'compact' if len(section.get('charts') or []) > 3 else 'comfortable',
            'has_tables': bool(section.get('tables')),
        }

    chart_styles: Dict[str, Dict[str, Any]] = {}
    for chart in charts:
        cid = str(getattr(chart, 'id', ''))
        priority = _priority_from_chart(chart)
        chart_styles[cid] = {
            'priority': priority,
            'tone': _tone_from_priority(priority),
            'show_callout': priority == 'primary',
        }

    export_notes: List[str] = []
    if visible_chart_count:
        export_notes.append(f"{visible_chart_count} decision-ready visual{' ' if False else ''}{'' if visible_chart_count == 1 else 's'} included.")
    if high_conf:
        export_notes.append(f"{high_conf} high-confidence item{'' if high_conf == 1 else 's'} promoted for executive reading.")
    if suppressed:
        export_notes.append(f"{suppressed} weak visual{'' if suppressed == 1 else 's'} suppressed to keep the story concise.")
    if mid_conf and not high_conf:
        export_notes.append('Most visuals are moderate-confidence and should be reviewed with context.')

    return {
        'hero_emphasis': hero_emphasis,
        'section_styles': section_styles,
        'chart_styles': chart_styles,
        'export_notes': export_notes,
        'board_spacing': 'relaxed',
        'kpi_density': 'tight' if visible_chart_count > 4 else 'balanced',
    }
