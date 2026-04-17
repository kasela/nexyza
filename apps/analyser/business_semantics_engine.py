from __future__ import annotations

from typing import Any, Dict, List, Tuple
import re


CANON_ROLE_PATTERNS = {
    "branch": ["branch", "outlet", "store", "shop", "location"],
    "region": ["region", "cluster", "area", "zone", "territory"],
    "manager": ["manager", "rm", "regional_manager", "supervisor", "leader", "owner"],
    "customer": ["customer", "client", "member", "borrower", "debtor"],
    "product": ["product", "item", "sku", "article", "model"],
    "category": ["category", "segment", "group", "class", "department"],
    "subcategory": ["subcategory", "sub_category", "sub group", "subgroup", "subclass"],
    "period": ["date", "month", "year", "week", "day", "period", "quarter"],
    "target": ["target", "budget", "plan", "goal", "quota"],
    "actual": ["actual", "achievement", "achivement", "achieve", "sales", "revenue", "income", "amount", "value", "turnover"],
    "forecast": ["forecast", "projection", "projected", "estimate"],
    "cost": ["cost", "expense", "spend", "purchase", "purchasing", "cogs"],
    "profit": ["profit", "margin", "surplus", "gp", "net_profit"],
    "quantity": ["qty", "quantity", "units", "volume", "pieces", "count"],
    "balance": ["balance", "stock", "inventory", "outstanding", "receivable", "payable"],
    "rate": ["rate", "pct", "percent", "percentage", "ratio", "yield"],
}

ARCHETYPE_RULES = {
    "target_vs_actual": {
        "requires": ["actual", "target"],
        "charts": ["target_vs_actual_trend", "variance_by_dimension", "attainment_ranked_bar"],
        "kpis": ["total_target", "total_actual", "variance_to_target", "attainment_pct"],
        "questions": [
            "Which segments are missing target?",
            "Should rankings use value or attainment percent?",
        ],
    },
    "financial_statement": {
        "requires": ["actual"],
        "soft": ["cost", "profit"],
        "charts": ["profitability_bridge", "margin_by_dimension", "period_variance"],
        "kpis": ["revenue", "cost", "profit", "margin_pct"],
        "questions": [
            "Is this statement monthly or period-based?",
            "Should the first view prioritise profit or growth?",
        ],
    },
    "operational_performance": {
        "requires": ["actual"],
        "soft": ["branch", "manager", "region", "quantity"],
        "charts": ["top_bottom_segments", "trend_line", "exception_table"],
        "kpis": ["total_actual", "best_segment", "worst_segment", "run_rate"],
        "questions": [
            "Which organisational level matters most for decisions?",
            "Do you want exceptions or top performers emphasised first?",
        ],
    },
    "inventory_or_balance": {
        "requires": ["balance"],
        "soft": ["quantity", "cost"],
        "charts": ["balance_trend", "stock_concentration", "movement_waterfall"],
        "kpis": ["closing_balance", "stock_turnover", "slow_moving_items"],
        "questions": [
            "Is the priority stock risk, ageing, or movement?",
            "Should values be shown in units or money first?",
        ],
    },
}


def _canon(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(text or "").strip().lower()).strip("_")



def _score_name(canon: str, patterns: List[str]) -> float:
    score = 0.0
    for pattern in patterns:
        p = _canon(pattern)
        if canon == p:
            score = max(score, 0.96)
        elif canon.startswith(p) or canon.endswith(p):
            score = max(score, 0.88)
        elif p in canon:
            score = max(score, 0.78)
    return score



def _column_kind(profile_col: Dict[str, Any]) -> str:
    role = profile_col.get("role")
    if role == "time":
        return "time"
    if role == "measure":
        return "measure"
    if role == "dimension":
        return "dimension"
    return "other"



def _infer_column_role(profile_col: Dict[str, Any]) -> Tuple[str, float]:
    canon = profile_col.get("canonical_name") or _canon(profile_col.get("name"))
    hints = set(profile_col.get("hints") or [])
    kind = _column_kind(profile_col)
    best_role = "generic_measure" if kind == "measure" else "generic_dimension"
    best_score = 0.52 if kind in {"measure", "dimension"} else 0.45

    if kind == "time":
        return "period", max(float(profile_col.get("confidence") or 0.6), 0.72)

    for role, patterns in CANON_ROLE_PATTERNS.items():
        score = _score_name(canon, patterns)
        if role in hints:
            score = max(score, 0.92)
        if role in {"target", "actual", "forecast", "cost", "profit", "quantity", "balance", "rate"} and kind != "measure":
            score *= 0.55
        if role in {"branch", "region", "manager", "customer", "product", "category", "subcategory"} and kind != "dimension":
            score *= 0.6
        if score > best_score:
            best_role = role
            best_score = score

    return best_role, round(min(best_score, 0.98), 2)



def _pick_top(candidates: List[Dict[str, Any]], role: str) -> str:
    ranked = [c for c in candidates if c.get("semantic_role") == role]
    ranked.sort(key=lambda item: item.get("confidence", 0), reverse=True)
    return ranked[0]["column"] if ranked else ""



def _detect_hierarchies(dimensions: List[Dict[str, Any]]) -> List[List[str]]:
    role_to_cols: Dict[str, List[str]] = {}
    for item in dimensions:
        role_to_cols.setdefault(item.get("semantic_role") or "generic_dimension", []).append(item["column"])
    hierarchies: List[List[str]] = []
    if role_to_cols.get("region") and role_to_cols.get("branch"):
        hierarchies.append([role_to_cols["region"][0], role_to_cols["branch"][0]])
    if role_to_cols.get("manager") and role_to_cols.get("branch"):
        hierarchies.append([role_to_cols["manager"][0], role_to_cols["branch"][0]])
    if role_to_cols.get("category") and role_to_cols.get("subcategory"):
        hierarchies.append([role_to_cols["category"][0], role_to_cols["subcategory"][0]])
    return hierarchies



def _rank_archetypes(role_presence: Dict[str, bool], has_time: bool) -> List[Dict[str, Any]]:
    ranked = []
    for key, rule in ARCHETYPE_RULES.items():
        requires = rule.get("requires") or []
        soft = rule.get("soft") or []
        if requires and not all(role_presence.get(name) for name in requires):
            continue
        score = 0.55
        score += sum(0.18 for name in requires if role_presence.get(name))
        score += sum(0.07 for name in soft if role_presence.get(name))
        if has_time:
            score += 0.04
        ranked.append({
            "name": key,
            "confidence": round(min(score, 0.97), 2),
            "recommended_charts": rule.get("charts") or [],
            "recommended_kpis": rule.get("kpis") or [],
            "clarifying_questions": rule.get("questions") or [],
        })
    ranked.sort(key=lambda item: item.get("confidence", 0), reverse=True)
    return ranked or [{
        "name": "general_performance",
        "confidence": 0.58,
        "recommended_charts": ["trend_line", "ranked_bar", "kpi_summary"],
        "recommended_kpis": ["primary_measure", "top_segment", "trend_direction"],
        "clarifying_questions": [
            "Which measure matters most for decision making?",
            "Which dimension should drive the first comparison view?",
        ],
    }]



def infer_business_semantics(profile: Dict[str, Any], analysis_result: Dict[str, Any] | None = None) -> Dict[str, Any]:
    column_profiles = list(profile.get("column_profiles") or [])
    dimensions: List[Dict[str, Any]] = []
    measures: List[Dict[str, Any]] = []
    time_dimensions: List[Dict[str, Any]] = []
    ambiguities: List[str] = []

    for col in column_profiles:
        semantic_role, confidence = _infer_column_role(col)
        item = {
            "column": col.get("name"),
            "semantic_role": semantic_role,
            "confidence": confidence,
            "kind": _column_kind(col),
        }
        if item["kind"] == "measure":
            measures.append(item)
        elif item["kind"] == "dimension":
            dimensions.append(item)
        elif item["kind"] == "time":
            time_dimensions.append(item)
        if confidence < 0.66 and item["kind"] in {"measure", "dimension"}:
            ambiguities.append(f"{item['column']} needs confirmation")

    role_presence = {role: False for role in CANON_ROLE_PATTERNS}
    for item in dimensions + measures + time_dimensions:
        role_presence[item.get("semantic_role") or ""] = True
    role_presence["period"] = bool(time_dimensions)
    archetypes = _rank_archetypes(role_presence, has_time=bool(time_dimensions))
    primary_archetype = archetypes[0]

    recommended_dimensions = dimensions[:]
    recommended_dimensions.sort(key=lambda item: item.get("confidence", 0), reverse=True)
    recommended_measures = measures[:]
    recommended_measures.sort(key=lambda item: item.get("confidence", 0), reverse=True)

    primary_dimension = _pick_top(dimensions, "branch") or _pick_top(dimensions, "region") or _pick_top(dimensions, "manager") or (recommended_dimensions[0]["column"] if recommended_dimensions else "")
    comparison_dimension = _pick_top(dimensions, "manager") or _pick_top(dimensions, "region") or (recommended_dimensions[1]["column"] if len(recommended_dimensions) > 1 else "")
    primary_measure = _pick_top(measures, "actual") or _pick_top(measures, "profit") or _pick_top(measures, "balance") or (recommended_measures[0]["column"] if recommended_measures else "")
    target_measure = _pick_top(measures, "target")
    period_column = time_dimensions[0]["column"] if time_dimensions else ""

    top_kpis = list(dict.fromkeys(primary_archetype.get("recommended_kpis") or []))
    top_charts = list(dict.fromkeys(primary_archetype.get("recommended_charts") or []))
    top_questions = list(dict.fromkeys(primary_archetype.get("clarifying_questions") or []))

    if target_measure and "attainment_pct" not in top_kpis:
        top_kpis.append("attainment_pct")
    if period_column and "trend_line" not in top_charts and all("trend" not in c for c in top_charts):
        top_charts.append("trend_line")
    if comparison_dimension and "comparison_ranked_bar" not in top_charts:
        top_charts.append("comparison_ranked_bar")

    overall_confidence = round(sum(a.get("confidence", 0) for a in archetypes[:2]) / max(1, min(2, len(archetypes))), 2)
    if ambiguities:
        overall_confidence = round(max(0.42, overall_confidence - min(0.18, 0.03 * len(ambiguities))), 2)

    summary_bits = [primary_archetype["name"].replace("_", " ")]
    if primary_measure:
        summary_bits.append(f"primary measure: {primary_measure}")
    if primary_dimension:
        summary_bits.append(f"primary dimension: {primary_dimension}")
    if period_column:
        summary_bits.append(f"time axis: {period_column}")
    if target_measure:
        summary_bits.append(f"target: {target_measure}")

    return {
        "dataset_archetypes": archetypes,
        "primary_archetype": primary_archetype.get("name", "general_performance"),
        "primary_archetype_display": primary_archetype.get("name", "general_performance").replace("_", " ").title(),
        "primary_archetype_confidence": primary_archetype.get("confidence", 0.58),
        "overall_confidence": overall_confidence,
        "dimensions": recommended_dimensions,
        "measures": recommended_measures,
        "time_dimensions": time_dimensions,
        "hierarchies": _detect_hierarchies(dimensions),
        "roles": {
            "primary_dimension": primary_dimension,
            "comparison_dimension": comparison_dimension,
            "primary_measure": primary_measure,
            "target_measure": target_measure,
            "period_column": period_column,
        },
        "recommendations": {
            "kpis": top_kpis[:6],
            "charts": top_charts[:6],
            "questions": top_questions[:5],
        },
        "ambiguities": ambiguities[:8],
        "needs_user_clarification": bool(ambiguities) and overall_confidence < 0.76,
        "summary": "; ".join(summary_bits),
    }
