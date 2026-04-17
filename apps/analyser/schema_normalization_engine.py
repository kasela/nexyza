from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional
import re
import pandas as pd


ALIAS_HINTS: dict[str, tuple[str, ...]] = {
    'target': ('target', 'plan', 'goal', 'budget', 'quota', 'benchmark'),
    'achievement': ('achievement', 'achivement', 'actual', 'sales', 'revenue', 'income'),
    'cluster': ('cluster', 'group'),
    'branch': ('branch', 'store', 'outlet', 'location'),
    'province': ('province', 'state'),
    'region': ('region', 'area', 'zone', 'territory'),
    'category': ('category', 'segment', 'class'),
    'manager': ('manager', 'regional_manager', 'owner', 'lead'),
    'month': ('month',),
    'year': ('year', 'fiscal_year'),
}


@dataclass(frozen=True)
class ColumnResolution:
    requested: str
    resolved: Optional[str]
    reason: str = 'exact'


def canonicalize_name(value: Any) -> str:
    text = str(value or '')
    text = text.replace('\ufeff', ' ').replace('\xa0', ' ')
    text = re.sub(r'[_\-/]+', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip().lower()
    text = re.sub(r'[^a-z0-9 ]+', '', text)
    return text.replace(' ', '_').strip('_')


def prettify_name(value: Any) -> str:
    text = str(value or '').replace('\ufeff', ' ').replace('\xa0', ' ')
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def _unique_columns(columns: Iterable[Any]) -> list[str]:
    seen: dict[str, int] = {}
    out: list[str] = []
    for raw in columns:
        pretty = prettify_name(raw) or 'Unnamed'
        base = pretty
        seen[base] = seen.get(base, 0) + 1
        if seen[base] > 1:
            pretty = f'{base} ({seen[base]})'
        out.append(pretty)
    return out


def normalize_numeric_series(series: pd.Series) -> pd.Series:
    if pd.api.types.is_numeric_dtype(series):
        return series
    if not pd.api.types.is_object_dtype(series) and not pd.api.types.is_string_dtype(series):
        return series

    cleaned = (
        series.astype(str)
        .str.replace('\u2212', '-', regex=False)
        .str.replace(',', '', regex=False)
        .str.replace(r'[$€£¥₹₨]', '', regex=True)
        .str.replace('%', '', regex=False)
        .str.strip()
    )
    cleaned = cleaned.replace({'': None, 'nan': None, 'None': None, 'null': None, 'N/A': None, 'n/a': None})
    numeric = pd.to_numeric(cleaned, errors='coerce')

    non_null = series.notna().sum()
    converted = numeric.notna().sum()
    ratio = (converted / non_null) if non_null else 0
    if ratio >= 0.75 and converted > 0:
        if series.astype(str).str.contains('%', regex=False).any():
            numeric = numeric / 100.0
        return numeric
    return series


def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    original_columns = [str(c) for c in out.columns]
    cleaned_columns = _unique_columns(original_columns)
    out.columns = cleaned_columns

    canonical_map = {col: canonicalize_name(col) for col in out.columns}
    reverse_map: dict[str, str] = {}
    for col, canon in canonical_map.items():
        reverse_map.setdefault(canon, col)

    for col in list(out.columns):
        out[col] = normalize_numeric_series(out[col])
        if pd.api.types.is_string_dtype(out[col]) or pd.api.types.is_object_dtype(out[col]):
            try:
                out[col] = out[col].map(lambda v: prettify_name(v) if isinstance(v, str) else v)
            except Exception:
                pass

    alias_map: dict[str, str] = {canonicalize_name(col): col for col in out.columns}
    for col in out.columns:
        canon = canonicalize_name(col)
        alias_map[prettify_name(col).lower()] = col
        alias_map[canon.replace('_', '')] = col
        for key, hints in ALIAS_HINTS.items():
            if any(h in canon for h in hints):
                alias_map.setdefault(key, col)
                for hint in hints:
                    alias_map.setdefault(hint, col)

    out.attrs['schema_normalization'] = {
        'original_columns': original_columns,
        'cleaned_columns': list(out.columns),
        'canonical_map': canonical_map,
        'alias_map': alias_map,
    }
    return out


def resolve_column_name(requested: Any, columns: Iterable[Any], alias_map: Optional[dict[str, str]] = None) -> ColumnResolution:
    req = prettify_name(requested)
    if not req:
        return ColumnResolution(requested=str(requested or ''), resolved=None, reason='empty')

    columns = [str(c) for c in columns]
    if req in columns:
        return ColumnResolution(requested=req, resolved=req, reason='exact')

    canon_req = canonicalize_name(req)
    canon_lookup = {canonicalize_name(c): c for c in columns}
    if canon_req in canon_lookup:
        return ColumnResolution(requested=req, resolved=canon_lookup[canon_req], reason='canonical')

    compact_lookup = {canonicalize_name(c).replace('_', ''): c for c in columns}
    compact_req = canon_req.replace('_', '')
    if compact_req in compact_lookup:
        return ColumnResolution(requested=req, resolved=compact_lookup[compact_req], reason='compact')

    alias_map = alias_map or {}
    for probe in (req.lower(), canon_req, compact_req):
        target = alias_map.get(probe)
        if target in columns:
            return ColumnResolution(requested=req, resolved=target, reason='alias')

    # fuzzy contains match as last resort
    for col in columns:
        canon_col = canonicalize_name(col)
        if canon_req and (canon_req in canon_col or canon_col in canon_req):
            return ColumnResolution(requested=req, resolved=col, reason='fuzzy')

    return ColumnResolution(requested=req, resolved=None, reason='missing')


def build_schema_metadata(df: pd.DataFrame) -> Dict[str, Any]:
    meta = dict(df.attrs.get('schema_normalization') or {})
    meta['column_count'] = len(df.columns)
    return meta
