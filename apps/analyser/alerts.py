from __future__ import annotations

from typing import List, Dict

import pandas as pd


def build_alerts(df: pd.DataFrame, metric: str, target: str | None = None, benchmark_value: float | None = None) -> List[Dict]:
    alerts: List[Dict] = []
    if df.empty or metric not in df.columns:
        return alerts

    series = pd.to_numeric(df[metric], errors='coerce').dropna()
    if series.empty:
        return alerts

    current = float(series.iloc[-1])
    avg = float(series.mean())
    if current < avg * 0.8:
        alerts.append({
            'level': 'high',
            'title': 'Current value is materially below average',
            'detail': f'Latest {metric} is more than 20% below the dataset average.',
        })

    if len(series) >= 2:
        prev = float(series.iloc[-2])
        if prev and current < prev * 0.85:
            alerts.append({
                'level': 'medium',
                'title': 'Sharp period decline detected',
                'detail': f'{metric} dropped by more than 15% versus the previous point.',
            })

    if benchmark_value not in (None, 0):
        if current < benchmark_value * 0.9:
            alerts.append({
                'level': 'medium',
                'title': 'Below benchmark',
                'detail': f'Current {metric} is below the selected benchmark level.',
            })

    if target and target in df.columns:
        targets = pd.to_numeric(df[target], errors='coerce').dropna()
        if not targets.empty:
            target_value = float(targets.iloc[-1])
            if target_value and current < target_value:
                alerts.append({
                    'level': 'high',
                    'title': 'Target miss',
                    'detail': f'Current {metric} is below the latest {target} value.',
                })

    std = float(series.std()) if len(series) > 1 else 0.0
    if std and abs(current - avg) > (2 * std):
        alerts.append({
            'level': 'medium',
            'title': 'Outlier warning',
            'detail': f'Current {metric} is more than two standard deviations away from the mean.',
        })

    if not alerts:
        alerts.append({
            'level': 'low',
            'title': 'No major alert triggered',
            'detail': f'{metric} is currently within the normal operating band.',
        })
    return alerts
