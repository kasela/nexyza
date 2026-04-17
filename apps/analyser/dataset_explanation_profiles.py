from __future__ import annotations

from typing import Any, Dict

DOMAIN_PROFILES: Dict[str, Dict[str, Any]] = {
    "sales": {
        "keywords": ["sales", "revenue", "achievement", "target", "quota", "deal", "customer"],
        "nouns": {"metric": "commercial performance", "entity": "segment", "issue": "sales gap"},
        "actions": {
            "executive": "Focus on under-delivering segments and recovery actions against target.",
            "manager": "Review underperforming segments, pipeline drivers, and target recovery plans.",
            "analyst": "Validate segmentation, seasonality, and benchmark definitions before drilling deeper.",
        },
    },
    "finance": {
        "keywords": ["expense", "cost", "profit", "margin", "budget", "variance", "cash"],
        "nouns": {"metric": "financial result", "entity": "cost centre", "issue": "budget variance"},
        "actions": {
            "executive": "Escalate adverse variances and review margin or cost containment actions.",
            "manager": "Trace the variance drivers and compare cost centres against budget and prior period.",
            "analyst": "Reconcile calculations, time windows, and source mappings before interpretation.",
        },
    },
    "operations": {
        "keywords": ["volume", "throughput", "cycle", "delay", "ticket", "sla", "downtime"],
        "nouns": {"metric": "operating result", "entity": "process area", "issue": "throughput risk"},
        "actions": {
            "executive": "Prioritise bottlenecks and service risks affecting delivery or throughput.",
            "manager": "Review bottlenecks, lagging teams, and exception queues by period.",
            "analyst": "Check flow consistency, anomalies, and control limits before proposing action.",
        },
    },
    "inventory": {
        "keywords": ["stock", "inventory", "closing stock", "opening stock", "purchasing", "turnover"],
        "nouns": {"metric": "inventory performance", "entity": "stock location", "issue": "stock build-up"},
        "actions": {
            "executive": "Review stock build-up and slow-moving segments before adding fresh supply.",
            "manager": "Compare turnover, stock movement, and purchase gaps across locations.",
            "analyst": "Validate inventory flow assumptions and check outlier locations before escalation.",
        },
    },
    "hr": {
        "keywords": ["headcount", "attendance", "attrition", "absence", "employee", "staff"],
        "nouns": {"metric": "workforce outcome", "entity": "team", "issue": "people risk"},
        "actions": {
            "executive": "Review people risks and hotspot teams requiring intervention.",
            "manager": "Compare attrition, attendance, and team performance drivers.",
            "analyst": "Validate population definitions and time windows before detailed conclusions.",
        },
    },
    "general_business": {
        "keywords": [],
        "nouns": {"metric": "business result", "entity": "segment", "issue": "performance gap"},
        "actions": {
            "executive": "Focus on the largest gap versus benchmark and the strongest recovery lever.",
            "manager": "Review weakest segments first, then compare them with the best performers.",
            "analyst": "Validate the benchmark and segment definitions before extending the analysis.",
        },
    },
}


def detect_dataset_domain(analysis: Dict[str, Any]) -> str:
    profile = (analysis or {}).get("profile_json") or {}
    fields = [str(c).lower() for c in (profile.get("preview_columns") or [])]
    for v in ((profile.get("business_roles") or {}).values()):
        if v:
            fields.append(str(v).lower())
    haystack = " ".join(fields)
    best_name, best_score = "general_business", 0
    for name, cfg in DOMAIN_PROFILES.items():
        score = sum(1 for kw in cfg.get("keywords", []) if kw in haystack)
        if score > best_score:
            best_name, best_score = name, score
    return best_name


def resolve_audience(analysis: Dict[str, Any]) -> str:
    guidance = (analysis or {}).get("analysis_user_guidance") or {}
    audience = str(guidance.get("preferred_audience") or guidance.get("audience") or "executive").lower()
    return audience if audience in {"executive", "manager", "analyst"} else "executive"


def get_explanation_profile(analysis: Dict[str, Any]) -> Dict[str, Any]:
    domain = detect_dataset_domain(analysis)
    audience = resolve_audience(analysis)
    cfg = DOMAIN_PROFILES.get(domain, DOMAIN_PROFILES["general_business"])
    return {
        "domain": domain,
        "audience": audience,
        "nouns": cfg.get("nouns", {}),
        "action_text": (cfg.get("actions") or {}).get(audience) or DOMAIN_PROFILES["general_business"]["actions"]["executive"],
    }
