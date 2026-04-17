from dataclasses import dataclass, asdict
from typing import Dict, List


@dataclass
class IntentResult:
    dataset_mode: str
    recommended_intents: List[str]
    candidate_metrics: List[str]
    candidate_dimensions: List[str]
    notes: List[str]

    def to_dict(self):
        return asdict(self)


def infer_analysis_intents(df, semantic_map: Dict[str, str]) -> IntentResult:
    metric_types = {"metric", "currency", "ratio", "percentage", "count"}
    dim_types = {"category", "date", "year", "month", "time_cat"}

    metrics = [col for col, stype in semantic_map.items() if stype in metric_types]
    dims = [col for col, stype in semantic_map.items() if stype in dim_types]
    temporal = [col for col, stype in semantic_map.items() if stype in {"date", "year", "month", "time_cat"}]
    target_cols = [col for col in semantic_map if any(k in col.lower() for k in ("target", "budget", "plan", "forecast"))]

    intents: List[str] = []
    notes: List[str] = []

    if temporal:
        intents.append("trend")
    if target_cols:
        intents.append("target_tracking")
    if metrics and dims:
        intents.extend(["ranking", "composition"])
    if len(metrics) >= 2:
        intents.append("correlation")
    if metrics:
        intents.append("distribution")
    if target_cols and metrics:
        intents.append("variance")

    intents = list(dict.fromkeys(intents))

    if "target_tracking" in intents and temporal:
        dataset_mode = "performance_tracking"
    elif temporal and metrics:
        dataset_mode = "time_series_analysis"
    elif len(metrics) >= 2:
        dataset_mode = "metric_exploration"
    else:
        dataset_mode = "general_analysis"

    if not metrics:
        notes.append("No numeric measures detected; charting options will be limited.")
    if not dims:
        notes.append("No clear grouping dimensions detected; analysis will lean toward KPIs and distributions.")
    if temporal and not target_cols:
        notes.append("Time-based analysis is available; rolling trends and forecasting should be prioritised.")

    return IntentResult(
        dataset_mode=dataset_mode,
        recommended_intents=intents,
        candidate_metrics=metrics[:8],
        candidate_dimensions=dims[:8],
        notes=notes,
    )
