from __future__ import annotations

from typing import Any, Dict, List


def build_annotations(payload: Dict[str, Any]) -> List[Dict[str, Any]]:
    labels = payload.get("labels") or []
    datasets = payload.get("datasets") or []
    if not labels or not datasets:
        return []

    primary = datasets[0].get("data") or []
    numeric = []
    for idx, value in enumerate(primary):
        if isinstance(value, (int, float)):
            numeric.append((idx, float(value)))
    if not numeric:
        return []

    annotations: List[Dict[str, Any]] = []
    max_idx, max_val = max(numeric, key=lambda item: item[1])
    min_idx, min_val = min(numeric, key=lambda item: item[1])
    latest_idx, latest_val = numeric[-1]

    annotations.append({
        "kind": "high",
        "label": f"Peak {labels[max_idx]}",
        "value": round(max_val, 2),
    })
    annotations.append({
        "kind": "low",
        "label": f"Low {labels[min_idx]}",
        "value": round(min_val, 2),
    })
    if len(numeric) > 1:
        prev_idx, prev_val = numeric[-2]
        delta = latest_val - prev_val
        annotations.append({
            "kind": "delta",
            "label": f"Latest {labels[latest_idx]}",
            "value": round(latest_val, 2),
            "delta": round(delta, 2),
        })
    return annotations
