from __future__ import annotations

from typing import Dict, List

from apps.forecasting.engine import run_forecast


def build_forecast_summary(upload, date_column: str, metric: str, periods: int = 6, method: str = 'linear') -> Dict:
    data = run_forecast(upload, date_column, metric, periods=periods, method=method)
    actuals: List[float] = data.get('actuals', [])
    forecast_values: List[float] = data.get('forecast', [])
    last_actual = actuals[-1] if actuals else None
    next_forecast = forecast_values[0] if forecast_values else None
    delta = None
    if last_actual not in (None, 0) and next_forecast is not None:
        delta = (next_forecast - last_actual) / last_actual
    return {
        'data': data,
        'summary': {
            'last_actual': last_actual,
            'next_forecast': next_forecast,
            'delta_pct': delta,
            'trend': data.get('trend', 'flat'),
            'method': data.get('method', method),
        }
    }
