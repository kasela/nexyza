from __future__ import annotations

from math import isnan
from typing import Any, Dict, List


def _coerce_num(v):
    try:
        f = float(v)
        if isnan(f):
            return None
        return f
    except Exception:
        return None


def _dataset_values(payload: Dict[str, Any]) -> List[float]:
    datasets = payload.get("datasets") or []
    if not datasets:
        return []
    values: List[float] = []
    for item in datasets[0].get("data") or []:
        if isinstance(item, dict):
            val = item.get("y", item.get("value"))
        else:
            val = item
        num = _coerce_num(val)
        if num is not None:
            values.append(num)
    return values


def _change_text(current: float, previous: float | None) -> str:
    if previous in (None, 0):
        return f"Latest value is {current:,.2f}."
    delta = current - previous
    pct = abs(delta) / abs(previous) * 100 if previous else 0
    direction = "up" if delta >= 0 else "down"
    return f"Latest value is {current:,.2f}, {direction} {abs(delta):,.2f} ({pct:.1f}%) from the previous point."


def _share_text(top: float, total: float) -> str:
    if not total:
        return "Contribution share could not be computed from the visible total."
    return f"It contributes about {(top / total) * 100:.1f}% of the visible total."


def generate_chart_insight(chart, payload: Dict[str, Any]) -> Dict[str, str]:
    labels = payload.get("labels") or []
    values = _dataset_values(payload)

    if payload.get("kpi"):
        value = _coerce_num(payload.get('value'))
        target = _coerce_num(payload.get('target'))
        label = payload.get('label', chart.title)
        if value is None:
            return {
                "summary": f"{label} is available but could not be quantified reliably.",
                "driver": "Underlying metric payload needs numeric validation.",
                "risk": "Avoid using this KPI for decisions until the measure is numeric.",
                "next_step": "Check column typing or switch to a validated measure."
            }
        if target not in (None, 0):
            variance = value - target
            rate = (value / target) * 100
            status = "above" if variance >= 0 else "below"
            return {
                "summary": f"{label} is {value:,.2f}, running {status} target by {abs(variance):,.2f}.",
                "driver": f"Achievement is {rate:.1f}% against the configured target.",
                "risk": "Large target gaps should be reviewed by period and segment before acting.",
                "next_step": "Open the matching variance or trend chart to identify where the gap comes from."
            }
        return {
            "summary": f"{label} is {value:,.2f}.",
            "driver": "This KPI aggregates the selected metric across the current filter context.",
            "risk": "Without target or prior-period context, the headline value can hide weak segments.",
            "next_step": "Pair this KPI with a trend or comparison chart for stronger interpretation."
        }

    if len(values) < 2 and chart.chart_type != 'histogram':
        return {
            "summary": f"{chart.title} does not yet have enough usable data points.",
            "driver": "The current axis selection produced too little structured data for a reliable insight.",
            "risk": "Sparse charts can mislead by overstating one point or category.",
            "next_step": "Switch axes or aggregation, or use a stronger measure/dimension pair."
        }

    max_val = max(values) if values else 0
    min_val = min(values) if values else 0
    max_idx = values.index(max_val) if values else 0
    min_idx = values.index(min_val) if values else 0
    max_label = labels[max_idx] if labels and max_idx < len(labels) else "top segment"
    min_label = labels[min_idx] if labels and min_idx < len(labels) else "bottom segment"
    latest = values[-1] if values else 0
    previous = values[-2] if len(values) > 1 else None

    if chart.chart_type in {"line", "area", "rolling_line", "cumulative_line"}:
        span = max_val - min_val
        return {
            "summary": _change_text(latest, previous),
            "driver": f"Peak period is {max_label} at {max_val:,.2f}; total visible swing is {span:,.2f}.",
            "risk": f"The weakest period is {min_label} at {min_val:,.2f}; check whether that drop is seasonal or operational.",
            "next_step": "Compare this series against target, forecast, or a rolling average to judge momentum."
        }

    if chart.chart_type in {"bar", "horizontal_bar", "pie", "doughnut"}:
        total = sum(values)
        gap = max_val - min_val
        return {
            "summary": f"Top contributor is {max_label} at {max_val:,.2f}.",
            "driver": _share_text(max_val, total),
            "risk": f"Gap between the strongest and weakest segment is {gap:,.2f}, with {min_label} at the bottom.",
            "next_step": "Review top and bottom segments together to identify concentration or underperformance."
        }

    if chart.chart_type == 'pareto':
        total = sum(values)
        top3 = sum(values[:3]) if len(values) >= 3 else total
        return {
            "summary": f"{max_label} is the largest contributor at {max_val:,.2f}.",
            "driver": f"The top 3 visible segments contribute {(top3 / total * 100) if total else 0:.1f}% of the visible total.",
            "risk": "High contribution concentration increases dependence on a small number of segments.",
            "next_step": "Protect the top contributors and investigate whether smaller segments can be improved profitably."
        }

    if chart.chart_type == 'variance_bar':
        positives = [v for v in values if v > 0]
        negatives = [v for v in values if v < 0]
        return {
            "summary": f"Largest favorable variance is {max_val:,.2f} at {max_label}." if max_val >= abs(min_val) else f"Largest unfavorable variance is {min_val:,.2f} at {min_label}.",
            "driver": f"{len(positives)} segments are above target and {len(negatives)} are below target in the visible set.",
            "risk": "Material negative variances should be decomposed by volume, rate, or mix before taking action.",
            "next_step": "Drill into the weakest negative segment to understand the main variance driver."
        }

    if chart.chart_type == 'bullet':
        total = sum(values)
        return {
            "summary": f"Best visible segment is {max_label} at {max_val:,.2f}.",
            "driver": f"Visible actual total is {total:,.2f}; read the benchmark markers to judge target attainment.",
            "risk": "A good total can still hide weak segments if benchmark gaps are uneven.",
            "next_step": "Sort by target gap or open the paired variance chart for a clearer shortfall view."
        }

    if chart.chart_type == 'histogram':
        return {
            "summary": f"Distribution spans from {min_val:,.2f} to {max_val:,.2f}.",
            "driver": f"Visible spread is {max_val - min_val:,.2f}; use this to judge dispersion rather than performance rank.",
            "risk": "Skewed distributions can make averages look healthier than most observations really are.",
            "next_step": "Compare this distribution by a key segment or overlay a target threshold if available."
        }

    if chart.chart_type == 'scatter':
        return {
            "summary": f"Scatter contains {len(values)} plotted points for relationship analysis.",
            "driver": "Use cluster patterns and slope direction to judge whether the two measures move together.",
            "risk": "A few outliers can distort the apparent relationship when the base data is noisy.",
            "next_step": "Validate the same relationship with a grouped comparison or filtered segment view."
        }

    return {
        "summary": f"Highest visible value is {max_val:,.2f} at {max_label}.",
        "driver": f"Lowest visible value is {min_val:,.2f} at {min_label}.",
        "risk": "Check whether the spread between high and low segments is operationally acceptable.",
        "next_step": "Compare this metric by another dimension or period for stronger context."
    }
