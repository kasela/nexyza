"""
Nexyza Skills Manager
=======================
Handles uploading, caching, and using Anthropic Agent Skills.

Skills are uploaded once and reused across all API calls.
Skill IDs are cached in the database (via Django settings or a simple
  flat file) so you don't re-upload on every server restart.

Usage:
    from apps.analyser.skills_manager import get_skill_id, ai_recommend_charts_with_skill
"""

import os
import io
import zipfile
import logging
from pathlib import Path
from django.conf import settings

logger = logging.getLogger(__name__)

# ── Skill directory locations ─────────────────────────────────────────────────
SKILLS_DIR = Path(__file__).parent.parent.parent / 'skills'

SKILL_DIRS = {
    'chart_analysis': SKILLS_DIR / 'datalens-chart-analysis',
    'insights':       SKILLS_DIR / 'datalens-insights',
}

# ── Skill ID cache (stored in settings or env) ────────────────────────────────
# On first run, skills are uploaded and IDs written to .skill_ids file
SKILL_ID_CACHE_FILE = SKILLS_DIR / '.skill_ids'


def _load_cached_ids() -> dict:
    """Load skill IDs from cache file."""
    ids = {}
    if SKILL_ID_CACHE_FILE.exists():
        for line in SKILL_ID_CACHE_FILE.read_text().strip().splitlines():
            if '=' in line:
                k, v = line.split('=', 1)
                ids[k.strip()] = v.strip()
    return ids


def _save_cached_ids(ids: dict):
    """Save skill IDs to cache file."""
    SKILL_ID_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{k} = {v}" for k, v in ids.items()]
    SKILL_ID_CACHE_FILE.write_text('\n'.join(lines) + '\n')


def _build_skill_zip(skill_dir: Path) -> bytes:
    """Package a skill directory into a ZIP file for upload."""
    buf = io.BytesIO()
    skill_name = skill_dir.name
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(skill_dir.rglob('*')):
            if file_path.is_file() and not file_path.name.startswith('.'):
                arcname = f"{skill_name}/{file_path.relative_to(skill_dir)}"
                zf.write(file_path, arcname)
    return buf.getvalue()


def upload_skill(skill_key: str, force: bool = False) -> str:
    """
    Upload a skill to Anthropic and return its skill_id.
    Caches the ID so it won't re-upload unless force=True.
    """
    import anthropic

    cached = _load_cached_ids()
    if not force and skill_key in cached:
        logger.info(f"Using cached skill ID for {skill_key}: {cached[skill_key]}")
        return cached[skill_key]

    skill_dir = SKILL_DIRS.get(skill_key)
    if not skill_dir or not skill_dir.exists():
        raise FileNotFoundError(f"Skill directory not found: {skill_dir}")

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

    # Build ZIP and upload
    zip_bytes  = _build_skill_zip(skill_dir)
    skill_name = skill_dir.name

    logger.info(f"Uploading skill '{skill_name}' ({len(zip_bytes):,} bytes)...")

    # Use multipart form upload
    import requests
    response = requests.post(
        'https://api.anthropic.com/v1/skills',
        headers={
            'x-api-key':        settings.ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01',
            'anthropic-beta':    'skills-2025-10-02',
        },
        files={
            'files[]': (f'{skill_name}.zip', zip_bytes, 'application/zip'),
        },
        data={
            'display_title': {
                'chart_analysis': 'Nexyza Chart Analysis',
                'insights':       'Nexyza Business Insights',
            }.get(skill_key, skill_name),
        },
        timeout=60,
    )

    if not response.ok:
        raise RuntimeError(
            f"Skill upload failed ({response.status_code}): {response.text[:300]}"
        )

    skill_id = response.json().get('id') or response.json().get('skill_id')
    if not skill_id:
        raise RuntimeError(f"No skill_id in response: {response.json()}")

    # Cache it
    cached[skill_key] = skill_id
    _save_cached_ids(cached)
    logger.info(f"Skill '{skill_name}' uploaded: {skill_id}")
    return skill_id


def get_skill_id(skill_key: str) -> str | None:
    """
    Get skill_id for a skill key, uploading if not yet cached.
    Returns None if upload fails (so callers can fall back gracefully).
    """
    if not getattr(settings, 'ANTHROPIC_API_KEY', ''):
        return None
    try:
        return upload_skill(skill_key)
    except Exception as e:
        logger.warning(f"Could not get skill ID for '{skill_key}': {e}")
        return None


def list_skills() -> list:
    """List all skills uploaded to this Anthropic account."""
    import requests
    response = requests.get(
        'https://api.anthropic.com/v1/skills',
        headers={
            'x-api-key':        settings.ANTHROPIC_API_KEY,
            'anthropic-version': '2023-06-01',
            'anthropic-beta':    'skills-2025-10-02',
        },
        timeout=30,
    )
    if response.ok:
        return response.json().get('data', [])
    return []


def delete_cached_ids():
    """Clear the skill ID cache (forces re-upload on next use)."""
    if SKILL_ID_CACHE_FILE.exists():
        SKILL_ID_CACHE_FILE.unlink()
        logger.info("Skill ID cache cleared")


def upload_all_skills(force: bool = False) -> dict:
    """Upload all Nexyza skills. Returns {skill_key: skill_id} dict."""
    results = {}
    for key in SKILL_DIRS:
        try:
            results[key] = upload_skill(key, force=force)
        except Exception as e:
            logger.error(f"Failed to upload skill '{key}': {e}")
            results[key] = None
    return results
