from __future__ import annotations

from collections import Counter
from typing import Any, Dict, List
import re

TIME_TYPES = {"date", "datetime", "year", "month", "time_cat"}
MEASURE_TYPES = {"metric", "currency", "ratio", "percentage", "count"}
DIMENSION_TYPES = {"category", "high_card", "date", "datetime", "year", "month", "time_cat"}


def _canon(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text or "").strip().lower()).strip("_")


def _top_values(col: Dict[str, Any], limit: int = 5) -> List[str]:
    vals = []
    for item in (col.get("top_values") or [])[:limit]:
        if isinstance(item, dict):
            vals.append(str(item.get("value", "")))
        else:
            vals.append(str(item))
    return vals


def profile_dataset(analysis_result: Dict[str, Any], filename: str = "") -> Dict[str, Any]:
    cols = analysis_result.get("columns") or []
    rows = int(analysis_result.get("rows") or 0)
    combined_dates = analysis_result.get("combined_dates") or []

    seen = Counter()
    column_profiles: List[Dict[str, Any]] = []
    duplicate_column_names = []

    for col in cols:
        name = str(col.get("name", "")).strip()
        if not name:
            continue
        seen[name] += 1
        if seen[name] == 2:
            duplicate_column_names.append(name)

        semantic = col.get("semantic_type") or "text"
        is_numeric = bool(col.get("is_numeric") or col.get("coerced_numeric") or semantic in MEASURE_TYPES)
        unique_count = int(col.get("unique_count") or 0)
        null_pct = float(col.get("null_pct") or 0)
        sample_values = _top_values(col)
        cardinality = (
            "low" if unique_count and unique_count <= 12 else
            "medium" if unique_count and unique_count <= 30 else
            "high"
        )
        confidence = 0.55
        if semantic in MEASURE_TYPES | TIME_TYPES | {"category", "high_card"}:
            confidence += 0.2
        if is_numeric and semantic in MEASURE_TYPES:
            confidence += 0.1
        if sample_values:
            confidence += 0.05
        if null_pct > 40:
            confidence -= 0.15
        if name in duplicate_column_names:
            confidence -= 0.10
        confidence = max(0.1, min(0.98, confidence))

        role = "other"
        if semantic in TIME_TYPES:
            role = "time"
        elif semantic in MEASURE_TYPES:
            role = "measure"
        elif semantic in {"category", "high_card"}:
            role = "dimension"

        hints = []
        canon = _canon(name)
        if any(k in canon for k in ["target", "budget", "plan"]):
            hints.append("target")
        if any(k in canon for k in ["forecast", "projection"]):
            hints.append("forecast")
        if any(k in canon for k in ["actual", "achievement", "achivement", "achieve", "sales", "revenue", "amount", "value", "income", "turnover"]):
            hints.append("actual")
        if any(k in canon for k in ["cost", "expense", "spend", "purchase", "purchasing"]):
            hints.append("cost")
        if any(k in canon for k in ["opening_stock", "openingstock", "opening_inventory"]):
            hints.append("opening_stock")
        if any(k in canon for k in ["closing_stock", "closingstock", "ending_stock", "ending_inventory"]):
            hints.append("closing_stock")
        if any(k in canon for k in ["profit", "margin"]):
            hints.append("profit")
        if semantic in TIME_TYPES:
            hints.append("time")

        column_profiles.append({
            "name": name,
            "canonical_name": canon,
            "semantic_type": semantic,
            "role": role,
            "is_numeric": is_numeric,
            "null_pct": null_pct,
            "unique_count": unique_count,
            "cardinality": cardinality,
            "sample_values": sample_values,
            "confidence": round(confidence, 2),
            "hints": hints,
            "stats": {
                "min": col.get("min"),
                "max": col.get("max"),
                "mean": col.get("mean"),
            },
        })

    measures = [c["name"] for c in column_profiles if c["role"] == "measure"]
    dimensions = [c["name"] for c in column_profiles if c["role"] == "dimension" and c.get("unique_count", 2) > 1]
    time_columns = [c["name"] for c in column_profiles if c["role"] == "time"]
    combined_date_names = [c.get("display_name") or c.get("name") for c in combined_dates if c.get("display_name") or c.get("name")]

    target_columns = [
        c["name"] for c in column_profiles
        if "target" in c["hints"] or any(k in c["canonical_name"] for k in ["budget", "plan"])
    ]
    forecast_columns = [c["name"] for c in column_profiles if "forecast" in c["hints"]]
    actual_columns = [c["name"] for c in column_profiles if "actual" in c["hints"]]

    profile = {
        "filename": filename,
        "row_count": rows,
        "column_count": len(column_profiles),
        "duplicate_column_names": duplicate_column_names,
        "column_profiles": column_profiles,
        "measures": measures,
        "dimensions": dimensions,
        "time_columns": combined_date_names + [c for c in time_columns if c not in combined_date_names],
        "target_columns": target_columns,
        "forecast_columns": forecast_columns,
        "actual_columns": actual_columns,
        "combined_dates": combined_dates,
        "semantic_groups": analysis_result.get("semantic_groups") or {},
        "correlation": analysis_result.get("correlation") or {},
        "preview_columns": ((analysis_result.get("preview") or {}).get("columns") or []),
        "quality_flags": [],
    }

    single_value_dims = [c["name"] for c in column_profiles if c["role"] == "dimension" and c.get("unique_count", 2) <= 1]
    if single_value_dims:
        profile["quality_flags"].append(f"single_value_dimensions_excluded:{','.join(single_value_dims)}")

    if not measures:
        profile["quality_flags"].append("no_measures_detected")
    if not dimensions:
        profile["quality_flags"].append("no_dimensions_detected")
    if profile["duplicate_column_names"]:
        profile["quality_flags"].append("duplicate_column_names")
    if rows < 12:
        profile["quality_flags"].append("small_dataset")
    return profile
