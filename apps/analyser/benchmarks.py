from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, Optional

import pandas as pd


@dataclass
class BenchmarkSummary:
    mode: str
    current_value: float
    benchmark_value: float
    variance_value: float
    variance_pct: Optional[float]
    label: str
    source_column: str = ''
    period_label: str = ''
    confidence: float = 0.0
    benchmark_kind: str = ''

    def to_dict(self):
        return {
            'mode': self.mode,
            'current_value': round(self.current_value, 2),
            'benchmark_value': round(self.benchmark_value, 2),
            'variance_value': round(self.variance_value, 2),
            'variance_pct': None if self.variance_pct is None else round(self.variance_pct, 4),
            'label': self.label,
            'source_column': self.source_column,
            'period_label': self.period_label,
            'confidence': round(self.confidence, 3),
            'benchmark_kind': self.benchmark_kind,
        }


def _safe_pct(numerator: float, denominator: float) -> Optional[float]:
    if not denominator:
        return None
    return numerator / denominator


def _series(df: pd.DataFrame, metric: str) -> pd.Series:
    if metric not in df.columns or df.empty:
        return pd.Series(dtype='float64')
    return pd.to_numeric(df[metric], errors='coerce').dropna()


def _empty(mode: str, label: str = 'No benchmark available') -> BenchmarkSummary:
    return BenchmarkSummary(mode=mode, current_value=0.0, benchmark_value=0.0, variance_value=0.0, variance_pct=None, label=label)


def _current_value(df: pd.DataFrame, metric: str) -> Optional[float]:
    s = _series(df, metric)
    if s.empty:
        return None
    return float(s.iloc[-1])


def _best_time_key(df: pd.DataFrame, time_column: str = '', period_column: str = '') -> str:
    if time_column and period_column and time_column in df.columns and period_column in df.columns:
        return '__benchmark_period__'
    if time_column and time_column in df.columns:
        return time_column
    if period_column and period_column in df.columns:
        return period_column
    return ''


def _prepare_time_frame(df: pd.DataFrame, metric: str, time_column: str = '', period_column: str = '') -> pd.DataFrame:
    if metric not in df.columns:
        return pd.DataFrame(columns=['__value__'])
    frame = df.copy()
    if time_column and period_column and time_column in frame.columns and period_column in frame.columns:
        frame['__benchmark_period__'] = frame[period_column].astype(str).str.strip() + ' ' + frame[time_column].astype(str).str.strip()
    key = _best_time_key(frame, time_column=time_column, period_column=period_column)
    if not key:
        s = _series(frame, metric)
        return pd.DataFrame({'__value__': s.tolist()})
    frame['__value__'] = pd.to_numeric(frame[metric], errors='coerce')
    grouped = frame.groupby(key, dropna=False)['__value__'].sum(min_count=1).reset_index()
    grouped = grouped.dropna(subset=['__value__'])
    grouped['__period_label__'] = grouped[key].astype(str)
    return grouped


def build_benchmark_summary(
    df: pd.DataFrame,
    metric: str,
    mode: str = 'average',
    *,
    time_column: str = '',
    period_column: str = '',
    target_column: str = '',
    group_column: str = '',
) -> BenchmarkSummary:
    if metric not in df.columns or df.empty:
        return _empty(mode)

    current_value = _current_value(df, metric)
    if current_value is None:
        return _empty(mode, 'No numeric benchmark available')

    frame = _prepare_time_frame(df, metric, time_column=time_column, period_column=period_column)
    if frame.empty and not target_column:
        return _empty(mode, 'No benchmark periods available')

    label = 'Average benchmark'
    benchmark_value: Optional[float] = None
    source_column = ''
    period_label = ''
    confidence = 0.6
    benchmark_kind = mode

    if mode == 'target' and target_column and target_column in df.columns:
        target_series = pd.to_numeric(df[target_column], errors='coerce').dropna()
        if not target_series.empty:
            benchmark_value = float(target_series.sum())
            current_value = float(_series(df, metric).sum())
            label = 'Target benchmark'
            source_column = target_column
            confidence = 0.95
            benchmark_kind = 'target'
    elif mode == 'previous_period' and len(frame) >= 2:
        benchmark_value = float(frame['__value__'].iloc[-2])
        current_value = float(frame['__value__'].iloc[-1])
        label = 'Previous period benchmark'
        period_label = str(frame['__period_label__'].iloc[-2])
        confidence = 0.9
        benchmark_kind = 'previous_period'
    elif mode == 'rolling_average':
        values = frame['__value__'].tail(4)
        if len(values) >= 2:
            benchmark_value = float(values.iloc[:-1].mean()) if len(values) > 1 else float(values.mean())
            current_value = float(frame['__value__'].iloc[-1])
            label = 'Rolling average benchmark'
            period_label = f"Last {max(len(values)-1, 1)} periods"
            confidence = 0.85
            benchmark_kind = 'rolling_average'
    elif mode == 'top_quartile':
        series = _series(df, metric)
        if len(series) >= 4:
            benchmark_value = float(series.quantile(0.75))
            current_value = float(series.iloc[-1])
            label = 'Top quartile benchmark'
            confidence = 0.8
            benchmark_kind = 'top_quartile'
    elif mode == 'peer_group' and group_column and group_column in df.columns:
        frame2 = df[[group_column, metric]].copy()
        frame2[metric] = pd.to_numeric(frame2[metric], errors='coerce')
        peer = frame2.groupby(group_column, dropna=False)[metric].mean().dropna()
        if not peer.empty:
            benchmark_value = float(peer.mean())
            current_value = float(_series(df, metric).mean())
            label = 'Peer group benchmark'
            source_column = group_column
            confidence = 0.8
            benchmark_kind = 'peer_group'
    elif mode == 'median':
        series = _series(df, metric)
        if not series.empty:
            benchmark_value = float(series.median())
            label = 'Median benchmark'
            confidence = 0.7
            benchmark_kind = 'median'
    elif mode == 'best':
        series = _series(df, metric)
        if not series.empty:
            benchmark_value = float(series.max())
            label = 'Best performer benchmark'
            confidence = 0.75
            benchmark_kind = 'best'
    else:
        series = _series(df, metric)
        if not series.empty:
            benchmark_value = float(series.mean())
            label = 'Average benchmark'
            confidence = 0.65
            benchmark_kind = 'average'

    if benchmark_value is None:
        return _empty(mode, 'No benchmark available for selected mode')

    variance_value = current_value - benchmark_value
    variance_pct = _safe_pct(variance_value, benchmark_value)
    return BenchmarkSummary(
        mode=mode,
        current_value=current_value,
        benchmark_value=benchmark_value,
        variance_value=variance_value,
        variance_pct=variance_pct,
        label=label,
        source_column=source_column,
        period_label=period_label,
        confidence=confidence,
        benchmark_kind=benchmark_kind,
    )


def build_benchmark_suite(
    df: pd.DataFrame,
    metric: str,
    *,
    time_column: str = '',
    period_column: str = '',
    target_column: str = '',
    group_column: str = '',
) -> Dict[str, Dict[str, Any]]:
    modes = ['target', 'previous_period', 'rolling_average', 'top_quartile', 'peer_group']
    suite: Dict[str, Dict[str, Any]] = {}
    for mode in modes:
        summary = build_benchmark_summary(
            df,
            metric,
            mode=mode,
            time_column=time_column,
            period_column=period_column,
            target_column=target_column,
            group_column=group_column,
        )
        if summary.label not in {'No benchmark available', 'No benchmark available for selected mode', 'No benchmark periods available', 'No numeric benchmark available'}:
            suite[mode] = summary.to_dict()

    preferred = next((m for m in ('target', 'previous_period', 'rolling_average', 'peer_group', 'top_quartile') if m in suite), '')
    return {
        'preferred_mode': preferred,
        'benchmarks': suite,
    }
