from __future__ import annotations

from typing import Dict


def build_scenario_result(base_value: float, growth_pct: float = 0.0, cost_pct: float = 0.0, target_override: float | None = None) -> Dict:
    projected_value = base_value * (1 + (growth_pct / 100.0))
    cost_impact = projected_value * (cost_pct / 100.0)
    net_value = projected_value - cost_impact
    variance_to_target = None
    if target_override is not None:
        variance_to_target = net_value - target_override
    return {
        'base_value': round(base_value, 2),
        'growth_pct': round(growth_pct, 2),
        'cost_pct': round(cost_pct, 2),
        'target_override': None if target_override is None else round(target_override, 2),
        'projected_value': round(projected_value, 2),
        'cost_impact': round(cost_impact, 2),
        'net_value': round(net_value, 2),
        'variance_to_target': None if variance_to_target is None else round(variance_to_target, 2),
    }
