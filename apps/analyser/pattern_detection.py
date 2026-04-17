from __future__ import annotations

from typing import Any, Dict, List


def detect_patterns(profile: Dict[str, Any]) -> Dict[str, Any]:
    measures = profile.get("measures", [])
    dimensions = profile.get("dimensions", [])
    time_columns = profile.get("time_columns", [])
    targets = profile.get("target_columns", [])
    corr = profile.get("correlation") or {}

    patterns: List[str] = []
    notes: List[str] = []
    opportunities: List[Dict[str, Any]] = []

    if time_columns and measures:
        patterns.append("trend")
        opportunities.append({"intent": "trend", "priority": 95, "reason": "Time column and measure detected"})
    if dimensions and measures:
        patterns.append("ranking")
        opportunities.append({"intent": "ranking", "priority": 90, "reason": "Dimensions and measures available"})
        patterns.append("composition")
        opportunities.append({"intent": "composition", "priority": 82, "reason": "Contribution view possible"})
    actuals = profile.get('actual_columns', [])
    if targets and measures:
        patterns.append("target_tracking")
        patterns.append("variance")
        opportunities.append({"intent": "target_tracking", "priority": 94, "reason": "Target/budget-like column detected"})
    if targets and actuals and dimensions:
        patterns.append('performance_management')
        opportunities.append({"intent": "performance_management", "priority": 97, "reason": "Actual and target columns can be reviewed across business dimensions"})
    if len(measures) >= 2:
        patterns.append("distribution")
        opportunities.append({"intent": "distribution", "priority": 74, "reason": "Multiple measures enable spread analysis"})
    if len(measures) >= 2 and corr.get("columns") and corr.get("matrix"):
        patterns.append("correlation")
        opportunities.append({"intent": "correlation", "priority": 70, "reason": "Correlation matrix is available"})
    if time_columns and len(measures) >= 1 and profile.get("row_count", 0) >= 12:
        patterns.append("forecast")
        opportunities.append({"intent": "forecast", "priority": 84, "reason": "Forecastable time series likely available"})

    # Pareto / concentration based on low-cardinality dimensions hints
    low_dims = [c for c in profile.get("column_profiles", []) if c.get("role") == "dimension" and c.get("cardinality") == "low"]
    if low_dims and measures:
        patterns.append("concentration")
        opportunities.append({"intent": "contribution", "priority": 78, "reason": "Low-cardinality dimensions suit Pareto analysis"})

    if profile.get("quality_flags"):
        notes.append("Data quality flags detected: " + ", ".join(profile["quality_flags"]))

    return {
        "patterns": list(dict.fromkeys(patterns)),
        "opportunities": sorted(opportunities, key=lambda x: x["priority"], reverse=True),
        "notes": notes,
    }
