from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict

from .models import BrandingConfig


def _safe_hex(value: str | None, fallback: str) -> str:
    value = (value or '').strip()
    if len(value) == 7 and value.startswith('#'):
        return value
    return fallback


def _hex_to_rgb_tuple(value: str, fallback: str = '#7c3aed') -> tuple[int, int, int]:
    value = _safe_hex(value, fallback).lstrip('#')
    try:
        return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        value = fallback.lstrip('#')
        return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))


def get_branding_for_user(user: Any) -> BrandingConfig | None:
    if not getattr(user, 'is_authenticated', False):
        return None
    try:
        return user.branding
    except Exception:
        return None


def build_branding_payload(user: Any = None, request: Any = None) -> Dict[str, Any]:
    branding = getattr(request, 'branding', None) if request is not None else None
    if branding is None:
        branding = get_branding_for_user(user)
    app_name = getattr(branding, 'app_name', None) or 'Nexyza'
    primary = _safe_hex(getattr(branding, 'primary_color', None), '#7c3aed')
    accent = _safe_hex(getattr(branding, 'accent_color', None), '#3b82f6')
    bg = _safe_hex(getattr(branding, 'bg_color', None), '#0d0b17')
    surface = _safe_hex(getattr(branding, 'surface_color', None), '#1e1b2e')
    generated = datetime.now().strftime('%Y-%m-%d %H:%M')
    footer_text = f"{app_name} • Generated {generated}"
    return {
        'app_name': app_name,
        'primary_color': primary,
        'accent_color': accent,
        'bg_color': bg,
        'surface_color': surface,
        'primary_rgb': _hex_to_rgb_tuple(primary),
        'accent_rgb': _hex_to_rgb_tuple(accent, '#3b82f6'),
        'bg_rgb': _hex_to_rgb_tuple(bg, '#0d0b17'),
        'surface_rgb': _hex_to_rgb_tuple(surface, '#1e1b2e'),
        'logo_path': getattr(getattr(branding, 'logo', None), 'path', ''),
        'logo_url': getattr(getattr(branding, 'logo', None), 'url', ''),
        'report_title': f'{app_name} Executive Dashboard',
        'footer_text': footer_text,
        'watermark': 'Confidential',
        'hide_vendor_branding': bool(getattr(branding, 'hide_datalens_branding', False)),
    }
