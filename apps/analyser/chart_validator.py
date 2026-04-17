from __future__ import annotations

from typing import Any, Dict, List, Tuple

VALID_TYPES = {"bar", "horizontal_bar", "line", "area", "rolling_line", "cumulative_line", "variance_bar", "pareto", "waterfall", "bullet", "progress_ring", "scatter", "pie", "doughnut", "histogram", "heatmap", "kpi"}
VALID_AGG = {"sum", "mean", "count", "min", "max"}
TARGET_DIVERSITY = {"kpi", "trend", "ranking", "comparison", "contribution", "distribution", "relationship"}


def _profile_lookup(profile: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    lookup = {c["name"]: c for c in profile.get("column_profiles", [])}
    derived = profile.get('derived_metrics') or {}
    labels = derived.get('labels') or {}
    semantic_types = derived.get('semantic_types') or {}
    for name in (derived.get('available') or []):
        lookup[name] = {
            'name': name,
            'semantic_type': semantic_types.get(name, 'metric'),
            'role': 'measure',
            'label': labels.get(name, name.replace('_', ' ').title()),
        }
    return lookup


def _best_time(profile: Dict[str, Any]) -> str:
    return (profile.get("time_columns") or [""])[0]


def _best_measure(profile: Dict[str, Any]) -> str:
    actuals = profile.get("actual_columns") or []
    if actuals:
        return actuals[0]
    measures = profile.get("measures") or []
    return measures[0] if measures else ""


def _best_dimension(profile: Dict[str, Any]) -> str:
    dims = profile.get("dimensions") or []
    return dims[0] if dims else ""


def _category_of(ctype: str) -> str:
    if ctype == 'kpi':
        return 'kpi'
    if ctype in {'line', 'area', 'rolling_line', 'cumulative_line'}:
        return 'trend'
    if ctype in {'variance_bar', 'bullet', 'waterfall', 'progress_ring'}:
        return 'comparison'
    if ctype in {'pareto', 'pie', 'doughnut'}:
        return 'contribution'
    if ctype in {'histogram', 'heatmap'}:
        return 'distribution'
    if ctype == 'scatter':
        return 'relationship'
    return 'ranking'


def _score(cfg: Dict[str, Any], profile: Dict[str, Any]) -> int:
    ctype = cfg.get('chart_type')
    x = cfg.get('x_axis') or ''
    y = cfg.get('y_axis') or ''
    score = 40
    if ctype == 'kpi':
        score += 18
    if ctype in {'line', 'rolling_line', 'cumulative_line'} and x in set(profile.get('time_columns') or []):
        score += 22
    if ctype in {'variance_bar', 'bullet', 'progress_ring'} and profile.get('target_columns'):
        score += 20
    goals = ((profile.get('user_guidance') or {}).get('primary_goals') or [])
    if 'Target vs achievement' in goals and ctype in {'variance_bar','bullet','progress_ring','line','bar','horizontal_bar'}:
        score += 14
    if 'Trend over time' in goals and ctype in {'line','rolling_line','cumulative_line'}:
        score += 10
    if 'Contribution / Pareto' in goals and ctype == 'pareto':
        score += 12
    if ctype == 'pareto':
        score += 16
    if y in set(profile.get('actual_columns') or []):
        score += 14
    if x in set(profile.get('dimensions') or []):
        score += 8
    if y in set(profile.get('measures') or []):
        score += 10
    if ctype == 'scatter' and len(profile.get('measures') or []) >= 2:
        score += 8
    if cfg.get('group_by'):
        score -= 2
    return score


def _repair(cfg: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    lookup = _profile_lookup(profile)
    cfg = dict(cfg)
    cfg["chart_type"] = cfg.get("chart_type") if cfg.get("chart_type") in VALID_TYPES else "bar"
    cfg["aggregation"] = cfg.get("aggregation") if cfg.get("aggregation") in VALID_AGG else "sum"
    cfg.setdefault("title", "Auto Chart")
    cfg.setdefault("group_by", "")
    cfg.setdefault("color", "violet")
    cfg.setdefault("size", "md")

    x = cfg.get("x_axis") or ""
    y = cfg.get("y_axis") or ""

    if cfg["chart_type"] == "kpi":
        cfg["x_axis"] = ""
        cfg["y_axis"] = y or _best_measure(profile)
        return cfg

    if cfg["chart_type"] in {"line", "area", "rolling_line", "cumulative_line"}:
        cfg["x_axis"] = x if x in lookup or x in profile.get("time_columns", []) else _best_time(profile)
        cfg["y_axis"] = y if y in lookup else _best_measure(profile)
        cfg["group_by"] = cfg.get("group_by") or ""
    elif cfg["chart_type"] in {"bar", "horizontal_bar", "pareto", "variance_bar", "bullet", "pie", "doughnut", "waterfall"}:
        cfg["x_axis"] = x if x in lookup or x in profile.get("time_columns", []) else _best_dimension(profile)
        cfg["y_axis"] = y if y in lookup else _best_measure(profile)
    elif cfg["chart_type"] == "scatter":
        measures = profile.get("measures") or []
        if len(measures) >= 2:
            cfg["x_axis"] = x if x in measures else measures[0]
            cfg["y_axis"] = y if y in measures and y != cfg["x_axis"] else measures[1]
        else:
            cfg["chart_type"] = "bar"
            cfg["x_axis"] = _best_dimension(profile)
            cfg["y_axis"] = _best_measure(profile)
    elif cfg["chart_type"] == "histogram":
        cfg["x_axis"] = ""
        cfg["y_axis"] = y if y in lookup else _best_measure(profile)
    elif cfg["chart_type"] == "heatmap":
        cfg["x_axis"] = x if x in lookup else _best_dimension(profile)
        cfg["y_axis"] = y if y in lookup else _best_measure(profile)
        cfg["group_by"] = cfg.get("group_by") or _best_time(profile)
    elif cfg["chart_type"] == "progress_ring":
        cfg["x_axis"] = x if x in lookup else _best_dimension(profile)
        cfg["y_axis"] = y if y in lookup else _best_measure(profile)

    if cfg['chart_type'] in {'variance_bar', 'bullet', 'progress_ring'} and not cfg.get('target_column'):
        targets = profile.get('target_columns') or []
        if targets:
            cfg['target_column'] = targets[0]

    return cfg


def validate_chart_configs(configs: List[Dict[str, Any]], profile: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    candidates: List[Dict[str, Any]] = []
    debug: List[Dict[str, Any]] = []
    derived_measures = set((profile.get('derived_metrics') or {}).get('available') or [])
    measures = set(profile.get("measures") or []) | derived_measures
    dims = set(profile.get("dimensions") or [])
    times = set(profile.get("time_columns") or [])
    targets = set(profile.get('target_columns') or [])
    forecasts = set(profile.get('forecast_columns') or [])

    for raw in configs or []:
        cfg = _repair(raw, profile)
        x = cfg.get("x_axis") or ""
        y = cfg.get("y_axis") or ""
        ctype = cfg.get("chart_type")

        reason = None
        if ctype != "kpi" and not x and ctype not in {"histogram", "scatter"}:
            reason = "missing_x"
        elif ctype != "kpi" and ctype not in {"progress_ring"} and not y:
            reason = "missing_y"
        elif ctype in {"line", "area", "rolling_line", "cumulative_line"} and x not in times:
            reason = "line_without_time_axis"
        elif ctype in {"bar", "horizontal_bar", "pareto", "variance_bar", "bullet", "pie", "doughnut", "waterfall"} and x not in dims and x not in times:
            reason = "dimension_not_detected"
        elif ctype in {"bar", "horizontal_bar", "line", "area", "rolling_line", "cumulative_line", "variance_bar", "pareto", "bullet", "waterfall", "kpi", "histogram", "progress_ring"} and y not in measures and y not in targets and y not in forecasts:
            reason = "measure_not_detected"
        elif ctype in {'variance_bar', 'bullet', 'progress_ring'} and not (cfg.get('target_column') or targets):
            reason = 'target_missing_for_comparison'
        elif ctype == 'scatter' and x == y:
            reason = 'scatter_same_axis'

        cfg['score'] = _score(cfg, profile)
        cfg['analysis_category'] = _category_of(ctype)

        if reason:
            debug.append({"config": cfg, "accepted": False, "reason": reason})
            continue
        candidates.append(cfg)

    # Rank strong charts first while keeping diversity.
    candidates.sort(key=lambda c: c.get('score', 0), reverse=True)
    accepted: List[Dict[str, Any]] = []
    seen = set()
    categories_present = set()

    for cfg in candidates:
        dedupe_key = (cfg.get('chart_type'), cfg.get('x_axis') or '', cfg.get('y_axis') or '', cfg.get('group_by') or '')
        if dedupe_key in seen:
            debug.append({"config": cfg, "accepted": False, "reason": "duplicate_spec"})
            continue
        accepted.append(cfg)
        seen.add(dedupe_key)
        categories_present.add(cfg.get('analysis_category'))
        debug.append({"config": cfg, "accepted": True, "reason": "accepted", "score": cfg.get('score')})

    # Keep the top 12, but prefer one of each major category first.
    if len(accepted) > 12:
        diversified: List[Dict[str, Any]] = []
        used = set()
        for cat in TARGET_DIVERSITY:
            for cfg in accepted:
                key = (cfg.get('chart_type'), cfg.get('x_axis') or '', cfg.get('y_axis') or '', cfg.get('group_by') or '')
                if cfg.get('analysis_category') == cat and key not in used:
                    diversified.append(cfg)
                    used.add(key)
                    break
        for cfg in accepted:
            key = (cfg.get('chart_type'), cfg.get('x_axis') or '', cfg.get('y_axis') or '', cfg.get('group_by') or '')
            if key not in used:
                diversified.append(cfg)
                used.add(key)
            if len(diversified) >= 12:
                break
        accepted = diversified

    return accepted, debug
