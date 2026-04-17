from __future__ import annotations

from .forecast_service import build_forecast_summary


def enrich_alerts_with_forecast(alerts, upload, date_column: str | None, metric: str | None):
    if not date_column or not metric:
        return alerts, None
    try:
        forecast_bundle = build_forecast_summary(upload, date_column=date_column, metric=metric)
        return alerts, forecast_bundle
    except Exception:
        return alerts, None
