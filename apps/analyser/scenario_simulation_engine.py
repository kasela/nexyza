from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
import math
import pandas as pd

SESSION_KEY = 'dashboard_scenarios'


@dataclass
class ScenarioState:
    name: str = 'base'
    target_pct: float = 0.0
    actual_pct: float = 0.0
    growth_pct: float = 0.0
    selected_dimension: str = ''
    selected_value: str = ''

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


def _clean_float(value: Any, default: float = 0.0) -> float:
    try:
        if value in (None, ''):
            return default
        return float(value)
    except Exception:
        return default


def _safe_number(value: Any) -> Optional[float]:
    try:
        f = float(value)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return None


def _fmt(value: Optional[float], metric_type: str = 'number') -> str:
    if value is None:
        return '—'
    if metric_type == 'percentage':
        return f'{value:.2f}%'
    if abs(value) >= 1_000_000:
        return f'{value/1_000_000:.2f}M'
    if abs(value) >= 1_000:
        return f'{value:,.0f}'
    if value != int(value):
        return f'{value:,.2f}'
    return f'{int(value):,}'


def build_scenario_state(request, upload, analysis: Dict[str, Any]) -> ScenarioState:
    stored = ((request.session.get(SESSION_KEY) or {}).get(str(upload.pk)) or {}) if hasattr(request, 'session') else {}
    state = ScenarioState(
        name=stored.get('name') or 'base',
        target_pct=_clean_float(stored.get('target_pct'), 0.0),
        actual_pct=_clean_float(stored.get('actual_pct'), 0.0),
        growth_pct=_clean_float(stored.get('growth_pct'), 0.0),
        selected_dimension=stored.get('selected_dimension') or '',
        selected_value=stored.get('selected_value') or '',
    )

    get = getattr(request, 'GET', {})
    if get.get('scenario_apply') == '1':
        state.name = (get.get('scenario_name') or state.name or 'custom').strip()[:80] or 'custom'
        state.target_pct = _clean_float(get.get('target_pct'), state.target_pct)
        state.actual_pct = _clean_float(get.get('actual_pct'), state.actual_pct)
        state.growth_pct = _clean_float(get.get('growth_pct'), state.growth_pct)
        state.selected_dimension = (get.get('selected_dimension') or '').strip()
        state.selected_value = (get.get('selected_value') or '').strip()
        if hasattr(request, 'session'):
            bag = request.session.get(SESSION_KEY) or {}
            bag[str(upload.pk)] = state.to_dict()
            request.session[SESSION_KEY] = bag
            request.session.modified = True
    elif get.get('scenario_reset') == '1':
        state = ScenarioState()
        if hasattr(request, 'session'):
            bag = request.session.get(SESSION_KEY) or {}
            bag.pop(str(upload.pk), None)
            request.session[SESSION_KEY] = bag
            request.session.modified = True
    return state


def _find_primary_measure(profile: Dict[str, Any]) -> str:
    cls = (profile.get('analysis_classification') or {})
    return cls.get('primary_measure') or ((profile.get('measures') or [''])[0])


def _find_target_measure(profile: Dict[str, Any]) -> str:
    roles = profile.get('business_roles') or {}
    return roles.get('target_column') or ((profile.get('target_columns') or [''])[0])


def _find_actual_measure(profile: Dict[str, Any]) -> str:
    roles = profile.get('business_roles') or {}
    return roles.get('actual_column') or ((profile.get('actual_columns') or [''])[0]) or _find_primary_measure(profile)


def available_segment_values(df: pd.DataFrame, state: ScenarioState, profile: Dict[str, Any]) -> Dict[str, Any]:
    dims = profile.get('dimensions') or []
    selected_dimension = state.selected_dimension if state.selected_dimension in df.columns else ''
    values: List[str] = []
    if selected_dimension:
        values = [str(v) for v in df[selected_dimension].dropna().astype(str).unique().tolist()[:100]]
    return {
        'dimensions': [d for d in dims if d in df.columns][:8],
        'selected_dimension': selected_dimension,
        'values': values,
    }


def apply_scenario_to_df(df: pd.DataFrame, state: ScenarioState, profile: Dict[str, Any]) -> pd.DataFrame:
    scenario_df = df.copy()
    actual_col = _find_actual_measure(profile)
    target_col = _find_target_measure(profile)
    measure_cols = [c for c in [actual_col, target_col] if c and c in scenario_df.columns]
    if not measure_cols:
        return scenario_df

    mask = pd.Series(True, index=scenario_df.index)
    if state.selected_dimension and state.selected_value and state.selected_dimension in scenario_df.columns:
        mask = scenario_df[state.selected_dimension].astype(str) == str(state.selected_value)

    if actual_col and actual_col in scenario_df.columns and state.actual_pct:
        scenario_df.loc[mask, actual_col] = pd.to_numeric(scenario_df.loc[mask, actual_col], errors='coerce') * (1 + state.actual_pct / 100.0)
    if target_col and target_col in scenario_df.columns and state.target_pct:
        scenario_df.loc[mask, target_col] = pd.to_numeric(scenario_df.loc[mask, target_col], errors='coerce') * (1 + state.target_pct / 100.0)

    generic_measure = _find_primary_measure(profile)
    if state.growth_pct and generic_measure and generic_measure in scenario_df.columns and generic_measure not in {actual_col, target_col}:
        scenario_df.loc[mask, generic_measure] = pd.to_numeric(scenario_df.loc[mask, generic_measure], errors='coerce') * (1 + state.growth_pct / 100.0)

    return scenario_df


def build_scenario_context(df: pd.DataFrame, state: ScenarioState, profile: Dict[str, Any]) -> Dict[str, Any]:
    actual_col = _find_actual_measure(profile)
    target_col = _find_target_measure(profile)
    dimension = (profile.get('analysis_classification') or {}).get('primary_dimension') or ((profile.get('dimensions') or [''])[0])
    scenario_df = apply_scenario_to_df(df, state, profile)
    is_active = any(abs(v) > 1e-9 for v in [state.actual_pct, state.target_pct, state.growth_pct]) or bool(state.selected_dimension and state.selected_value)

    base_actual = _safe_number(pd.to_numeric(df[actual_col], errors='coerce').sum()) if actual_col in df.columns else None
    sim_actual = _safe_number(pd.to_numeric(scenario_df[actual_col], errors='coerce').sum()) if actual_col in scenario_df.columns else None
    base_target = _safe_number(pd.to_numeric(df[target_col], errors='coerce').sum()) if target_col in df.columns else None
    sim_target = _safe_number(pd.to_numeric(scenario_df[target_col], errors='coerce').sum()) if target_col in scenario_df.columns else None

    def pct(actual, target):
        if actual is None or target in (None, 0):
            return None
        return (actual / target) * 100.0

    base_att = pct(base_actual, base_target)
    sim_att = pct(sim_actual, sim_target)

    cards = [
        {
            'label': 'Scenario actual', 'value': _fmt(sim_actual), 'delta': _fmt((sim_actual or 0) - (base_actual or 0)), 'delta_direction': 'positive' if (sim_actual or 0) - (base_actual or 0) >= 0 else 'negative'
        },
        {
            'label': 'Scenario target', 'value': _fmt(sim_target), 'delta': _fmt((sim_target or 0) - (base_target or 0)), 'delta_direction': 'positive' if (sim_target or 0) - (base_target or 0) >= 0 else 'negative'
        },
        {
            'label': 'Achievement %', 'value': _fmt(sim_att, 'percentage'), 'delta': _fmt((sim_att or 0) - (base_att or 0), 'percentage'), 'delta_direction': 'positive' if (sim_att or 0) - (base_att or 0) >= 0 else 'negative'
        },
    ]

    compare_rows = []
    if dimension and dimension in df.columns and actual_col in df.columns:
        base_grp = df.groupby(dimension, dropna=False)[actual_col].sum().sort_values(ascending=False)
        sim_grp = scenario_df.groupby(dimension, dropna=False)[actual_col].sum().reindex(base_grp.index).fillna(0)
        diff = (sim_grp - base_grp).sort_values(ascending=False)
        for entity, delta in list(diff.head(5).items()):
            compare_rows.append({
                'entity': str(entity),
                'current': _fmt(_safe_number(base_grp.get(entity))),
                'scenario': _fmt(_safe_number(sim_grp.get(entity))),
                'delta': _fmt(_safe_number(delta)),
                'direction': 'positive' if delta >= 0 else 'negative',
            })

    notes = []
    if state.selected_dimension and state.selected_value:
        notes.append(f'Applied only to {state.selected_dimension}: {state.selected_value}.')
    else:
        notes.append('Applied across the full visible dataset.')
    if state.actual_pct:
        notes.append(f'Actual adjusted by {state.actual_pct:+.1f}%.')
    if state.target_pct:
        notes.append(f'Target adjusted by {state.target_pct:+.1f}%.')
    if state.growth_pct:
        notes.append(f'Generic growth assumption set to {state.growth_pct:+.1f}%.')
    if not is_active:
        notes = ['Base case active. Adjust the inputs to preview scenario impact.']

    return {
        'state': state.to_dict(),
        'active': is_active,
        'cards': cards,
        'rows': compare_rows,
        'notes': notes,
        'actual_column': actual_col,
        'target_column': target_col,
        'dimension': dimension,
    }
