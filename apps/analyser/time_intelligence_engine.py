from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

MONTH_ORDER = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
}

QUARTER_TO_MONTH = {"q1": 3, "q2": 6, "q3": 9, "q4": 12}


def _safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")


def _pick_time_columns(df: pd.DataFrame, profile: Optional[Dict[str, Any]] = None) -> Tuple[str, str]:
    profile = profile or {}
    time_columns = profile.get("time_columns") or []
    year_col = ""
    period_col = ""
    for col in time_columns:
        lc = str(col).strip().lower()
        if not year_col and (lc == "year" or "year" in lc):
            year_col = col
        elif not period_col:
            period_col = col
    if not year_col:
        for col in df.columns:
            lc = str(col).strip().lower()
            if lc == "year" or "year" in lc:
                year_col = col
                break
    if not period_col:
        for col in df.columns:
            lc = str(col).strip().lower()
            if lc in {"month", "quarter", "week", "date"} or "month" in lc or "quarter" in lc or "date" in lc:
                if col != year_col:
                    period_col = col
                    break
    return year_col, period_col


def _derive_period_key(frame: pd.DataFrame, year_col: str, period_col: str) -> pd.DataFrame:
    work = frame.copy()
    if year_col and year_col in work.columns:
        work[year_col] = _safe_numeric(work[year_col])
    if period_col and period_col in work.columns:
        s = work[period_col].astype(str).str.strip()
        lower = s.str.lower()
        month_num = lower.map(MONTH_ORDER)
        quarter_num = lower.map(QUARTER_TO_MONTH)
        if month_num.notna().any():
            work["__period_num__"] = month_num
            work["__period_label__"] = s
        elif quarter_num.notna().any():
            work["__period_num__"] = quarter_num
            work["__period_label__"] = s
        else:
            inferred = _safe_numeric(s)
            if inferred.notna().any():
                work["__period_num__"] = inferred
                work["__period_label__"] = s
            else:
                work["__period_num__"] = range(1, len(work) + 1)
                work["__period_label__"] = s
    else:
        work["__period_num__"] = range(1, len(work) + 1)
        work["__period_label__"] = range(1, len(work) + 1)

    if year_col and year_col in work.columns and work[year_col].notna().any():
        work["__year__"] = work[year_col].fillna(0).astype(int)
    else:
        work["__year__"] = 0

    work["__sort__"] = work["__year__"] * 100 + _safe_numeric(work["__period_num__"]).fillna(0)
    work["__time_label__"] = work["__period_label__"].astype(str)
    if year_col and year_col in work.columns and work[year_col].notna().any():
        work["__time_label__"] = work["__period_label__"].astype(str) + " " + work["__year__"].astype(str)
    return work


def build_time_series_frame(
    df: pd.DataFrame,
    metric: str,
    *,
    profile: Optional[Dict[str, Any]] = None,
    year_col: str = "",
    period_col: str = "",
    agg: str = "sum",
) -> pd.DataFrame:
    if metric not in df.columns or df.empty:
        return pd.DataFrame(columns=["time_label", "value", "sort_key", "year", "period_num"])

    if not year_col and not period_col:
        year_col, period_col = _pick_time_columns(df, profile)

    frame = df.copy()
    frame[metric] = _safe_numeric(frame[metric])
    frame = frame.dropna(subset=[metric])
    if frame.empty:
        return pd.DataFrame(columns=["time_label", "value", "sort_key", "year", "period_num"])

    work = _derive_period_key(frame, year_col, period_col)
    grouped = work.groupby(["__sort__", "__year__", "__period_num__", "__time_label__"], dropna=False)[metric]
    if agg == "mean":
        grouped = grouped.mean().reset_index(name="value")
    elif agg == "count":
        grouped = grouped.count().reset_index(name="value")
    elif agg == "max":
        grouped = grouped.max().reset_index(name="value")
    elif agg == "min":
        grouped = grouped.min().reset_index(name="value")
    else:
        grouped = grouped.sum(min_count=1).reset_index(name="value")
    grouped = grouped.sort_values("__sort__").reset_index(drop=True)
    grouped.rename(columns={"__sort__": "sort_key", "__year__": "year", "__period_num__": "period_num", "__time_label__": "time_label"}, inplace=True)
    return grouped


def build_time_intelligence(
    df: pd.DataFrame,
    metric: str,
    *,
    profile: Optional[Dict[str, Any]] = None,
    year_col: str = "",
    period_col: str = "",
    rolling_windows: Tuple[int, ...] = (3, 6, 12),
) -> Dict[str, Any]:
    series = build_time_series_frame(df, metric, profile=profile, year_col=year_col, period_col=period_col)
    if series.empty or len(series) < 2:
        return {
            "metric": metric,
            "available": False,
            "reason": "Not enough ordered time periods available",
            "series": [],
            "comparisons": {},
            "rolling": {},
            "seasonality": {},
            "forecast_hint": {},
        }

    values = series["value"].astype(float)
    labels = series["time_label"].astype(str).tolist()
    latest = float(values.iloc[-1])
    prev = float(values.iloc[-2]) if len(values) >= 2 else None

    def pct_change(curr: Optional[float], base: Optional[float]) -> Optional[float]:
        if curr is None or base in (None, 0):
            return None
        return (curr - base) / base

    comparisons: Dict[str, Any] = {}
    if prev is not None:
        comparisons["previous_period"] = {
            "label": labels[-2],
            "value": round(prev, 2),
            "delta": round(latest - prev, 2),
            "delta_pct": None if pct_change(latest, prev) is None else round(pct_change(latest, prev), 4),
        }
        comparisons["mom"] = comparisons["previous_period"]

    if len(values) >= 4:
        qoq_base = float(values.iloc[-4])
        comparisons["qoq"] = {
            "label": labels[-4],
            "value": round(qoq_base, 2),
            "delta": round(latest - qoq_base, 2),
            "delta_pct": None if pct_change(latest, qoq_base) is None else round(pct_change(latest, qoq_base), 4),
        }

    if len(values) >= 12:
        yoy_base = float(values.iloc[-12])
        comparisons["yoy"] = {
            "label": labels[-12],
            "value": round(yoy_base, 2),
            "delta": round(latest - yoy_base, 2),
            "delta_pct": None if pct_change(latest, yoy_base) is None else round(pct_change(latest, yoy_base), 4),
        }

    rolling: Dict[str, Any] = {}
    for window in rolling_windows:
        if len(values) >= window:
            avg = float(values.tail(window).mean())
            rolling[str(window)] = {
                "label": f"Rolling {window}",
                "value": round(avg, 2),
                "delta_vs_latest": round(latest - avg, 2),
                "delta_pct_vs_latest": None if pct_change(latest, avg) is None else round(pct_change(latest, avg), 4),
            }

    ytd = float(values.sum())
    cumulative = values.cumsum().round(2).tolist()

    seasonality: Dict[str, Any] = {}
    if "period_num" in series.columns and series["year"].nunique() >= 2:
        grp = series.groupby("period_num")["value"].mean().dropna()
        if not grp.empty:
            peak_period = int(grp.idxmax())
            weak_period = int(grp.idxmin())
            seasonality = {
                "available": True,
                "peak_period": peak_period,
                "weak_period": weak_period,
                "spread_pct": None if grp.min() in (0, None) else round((grp.max() - grp.min()) / grp.min(), 4),
            }
    else:
        seasonality = {"available": False}

    if len(values) >= 3:
        slope = float(values.diff().dropna().tail(3).mean())
    else:
        slope = float(values.diff().dropna().mean()) if len(values) >= 2 else 0.0
    forecast_hint = {
        "next_period_estimate": round(latest + slope, 2),
        "trend_direction": "up" if slope > 0 else ("down" if slope < 0 else "flat"),
        "method": "simple_momentum_hint",
    }

    return {
        "metric": metric,
        "available": True,
        "year_column": year_col or _pick_time_columns(df, profile)[0],
        "period_column": period_col or _pick_time_columns(df, profile)[1],
        "series": [
            {"label": row["time_label"], "value": round(float(row["value"]), 2), "sort_key": int(row["sort_key"])}
            for _, row in series.iterrows()
        ],
        "current": {"label": labels[-1], "value": round(latest, 2)},
        "comparisons": comparisons,
        "rolling": rolling,
        "ytd": {"label": "YTD", "value": round(ytd, 2)},
        "cumulative": [round(float(v), 2) for v in cumulative],
        "seasonality": seasonality,
        "forecast_hint": forecast_hint,
    }
