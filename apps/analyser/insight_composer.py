from __future__ import annotations

from typing import Any, Dict

from .insight_engine import generate_chart_insight


def compose_chart_insight(chart, payload: Dict[str, Any]) -> Dict[str, str]:
    return generate_chart_insight(chart, payload)
