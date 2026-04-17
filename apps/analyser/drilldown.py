from __future__ import annotations

from typing import Any

import pandas as pd


AGG_MAP = {
    'sum': 'sum',
    'mean': 'mean',
    'count': 'count',
    'min': 'min',
    'max': 'max',
}


def build_drilldown(df: pd.DataFrame, dimension: str, metric: str = '', aggregation: str = 'sum', limit: int = 12) -> dict[str, Any]:
    if dimension not in df.columns:
        return {'labels': [], 'values': [], 'summary': 'Selected dimension is not available.'}

    work = df.copy()
    work[dimension] = work[dimension].astype(str).fillna('Unknown')

    if metric and metric in work.columns and pd.api.types.is_numeric_dtype(work[metric]):
        agg_fn = AGG_MAP.get(aggregation, 'sum')
        grouped = getattr(work.groupby(dimension)[metric], agg_fn)().sort_values(ascending=False).head(limit)
        summary = f'Top {len(grouped)} by {metric} ({agg_fn}).'
    else:
        grouped = work.groupby(dimension).size().sort_values(ascending=False).head(limit)
        summary = f'Top {len(grouped)} groups by row count.'

    labels = [str(v) for v in grouped.index.tolist()]
    values = [float(v) if hasattr(v, '__float__') else 0 for v in grouped.tolist()]
    return {
        'labels': labels,
        'values': values,
        'summary': summary,
    }
