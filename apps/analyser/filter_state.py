from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class FilterState:
    dimension: str = ''
    value: str = ''
    comparison_mode: str = ''
    top_n: int = 10
    chart_type: str = ''
    aggregation: str = ''

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def normalise_filter_state(payload: dict[str, Any] | None) -> FilterState:
    payload = payload or {}
    return FilterState(
        dimension=str(payload.get('dimension', '') or ''),
        value=str(payload.get('value', '') or ''),
        comparison_mode=str(payload.get('comparison_mode', '') or ''),
        top_n=max(1, min(int(payload.get('top_n', 10) or 10), 50)),
        chart_type=str(payload.get('chart_type', '') or ''),
        aggregation=str(payload.get('aggregation', '') or ''),
    )
