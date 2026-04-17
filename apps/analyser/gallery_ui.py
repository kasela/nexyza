from __future__ import annotations

from copy import deepcopy
from typing import Any, Dict

from django.urls import reverse

DEFAULT_HEADER_STYLE = 'background:rgba(255,255,255,.03);border:1px solid rgba(255,255,255,.06);'
_SURFACE_STYLE_MAP = {
    'violet': 'background:rgba(124,58,237,.08);border:1px solid rgba(255,255,255,.06);',
    'blue': 'background:rgba(59,130,246,.08);border:1px solid rgba(255,255,255,.06);',
    'emerald': 'background:rgba(16,185,129,.08);border:1px solid rgba(255,255,255,.06);',
    'amber': 'background:rgba(245,158,11,.08);border:1px solid rgba(255,255,255,.06);',
}


def resolve_section_header_style(section_styles: Dict[str, Any] | None, key: str | None) -> str:
    if not section_styles or not key:
        return DEFAULT_HEADER_STYLE
    style = section_styles.get(key) or {}
    surface = str(style.get('surface') or '').strip().lower()
    return _SURFACE_STYLE_MAP.get(surface, DEFAULT_HEADER_STYLE)



def decorate_narrative_dashboard(narrative_dashboard: Dict[str, Any] | None, presentation_polish: Dict[str, Any] | None) -> Dict[str, Any]:
    dashboard = deepcopy(narrative_dashboard or {})
    section_styles = (presentation_polish or {}).get('section_styles') or {}

    for table in dashboard.get('exception_tables') or []:
        table['header_style'] = resolve_section_header_style(section_styles, table.get('key'))

    for section in dashboard.get('sections') or []:
        section['header_style'] = resolve_section_header_style(section_styles, section.get('key'))

    return dashboard



def build_share_ui(request, upload) -> Dict[str, Any]:
    can_share = bool(getattr(upload, 'share_enabled', False) and getattr(upload, 'share_token', ''))
    shared_view_path = reverse('analyser:shared', args=[upload.share_token]) if can_share else ''
    embed_path = reverse('embed:dashboard', args=[upload.share_token]) if can_share else ''
    base_url = request.build_absolute_uri('/')[:-1]

    share_url = f'{base_url}{shared_view_path}' if shared_view_path else ''
    embed_url = f'{base_url}{embed_path}' if embed_path else ''
    embed_snippet = (
        f'<iframe src="{embed_url}" width="100%" height="500" frameborder="0" '
        f'style="border-radius:12px"></iframe>'
        if embed_url else ''
    )

    return {
        'can_open_shared': can_share,
        'shared_view_path': shared_view_path,
        'shared_view_url': share_url,
        'share_url': share_url,
        'embed_url': embed_url,
        'embed_snippet': embed_snippet,
        'expires_at': getattr(upload, 'share_expires', None),
    }
