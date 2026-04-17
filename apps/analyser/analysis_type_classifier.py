from __future__ import annotations

from typing import Any, Dict

from .universal_data_intelligence_engine import classify_dataset, detect_measure_roles, detect_primary_intents


def classify_analysis_type(profile: Dict[str, Any]) -> Dict[str, Any]:
    roles = detect_measure_roles(profile)
    intents = detect_primary_intents(profile, roles)
    return classify_dataset(profile, roles, intents)
