"""
Forecasting engine — Linear, Moving Average, Exponential Smoothing, AI.
"""
import math
import statistics
import pandas as pd
from apps.analyser.engine import load_dataframe


def _safe(v):
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 4)
    except Exception:
        return None


def forecast_linear(values, periods):
    n = len(values)
    if n < 2: raise ValueError("Need ≥ 2 data points")
    xs = list(range(n))
    mx, my = sum(xs)/n, sum(values)/n
    num   = sum((xs[i]-mx)*(values[i]-my) for i in range(n))
    denom = sum((xs[i]-mx)**2 for i in range(n))
    slope = num/denom if denom else 0
    intercept = my - slope*mx
    fc = [slope*(n+i)+intercept for i in range(periods)]
    res = [values[i]-(slope*xs[i]+intercept) for i in range(n)]
    margin = 1.5*(statistics.stdev(res) if len(res)>1 else 0)
    return {
        'forecast': [round(f,4) for f in fc],
        'lower':    [round(f-margin,4) for f in fc],
        'upper':    [round(f+margin,4) for f in fc],
        'method':   'linear',
        'trend':    'up' if slope>0 else ('down' if slope<0 else 'flat'),
        'slope':    round(slope,4),
    }


def forecast_moving_avg(values, periods, window=3):
    if len(values) < window: window = max(1, len(values))
    recent = values[-window:]
    avg    = sum(recent)/len(recent)
    std    = statistics.stdev(recent) if len(recent)>1 else 0
    fc     = [avg]*periods
    margins = [1.5*std*(i+1)**0.5 for i in range(periods)]
    return {
        'forecast': [round(f,4) for f in fc],
        'lower':    [round(avg-m,4) for m in margins],
        'upper':    [round(avg+m,4) for m in margins],
        'method':   'moving_avg',
        'trend':    'flat',
        'window':   window,
    }


def forecast_exp_smooth(values, periods, alpha=0.3):
    if not values: raise ValueError("No data")
    s = values[0]
    for v in values[1:]:
        s = alpha*v + (1-alpha)*s
    fc = [round(s,4)]*periods
    # Uncertainty widens over time
    std = statistics.stdev(values) if len(values)>1 else 0
    margins = [1.5*std*(i+1)**0.4 for i in range(periods)]
    return {
        'forecast': fc,
        'lower':    [round(s-m,4) for m in margins],
        'upper':    [round(s+m,4) for m in margins],
        'method':   'exponential',
        'alpha':    alpha,
        'trend':    'up' if fc[0]>values[-1] else ('down' if fc[0]<values[-1] else 'flat'),
    }


def run_forecast(upload, date_col, value_col, periods=6, method='linear'):
    """Run forecast and return structured data dict."""
    df = load_dataframe(upload.file.path, upload.file_type,
                        sheet_name=upload.active_sheet or None)

    # Clean and sort
    df = df[[date_col, value_col]].dropna()
    df[value_col] = pd.to_numeric(df[value_col], errors='coerce')
    df = df.dropna(subset=[value_col])

    # Detect if date column is parseable
    try:
        df[date_col] = pd.to_datetime(df[date_col], infer_datetime_format=True)
        df = df.sort_values(date_col)
        labels = [str(d.date()) if hasattr(d,'date') else str(d)
                  for d in df[date_col].tolist()]
    except Exception:
        labels = [str(v) for v in df[date_col].tolist()]

    values  = [_safe(v) for v in df[value_col].tolist()]
    values  = [v for v in values if v is not None]
    if len(values) < 2:
        raise ValueError(f"Not enough numeric data in '{value_col}'")

    # Future labels
    future_labels = [f"F+{i+1}" for i in range(periods)]

    if method == 'linear':
        res = forecast_linear(values, periods)
    elif method == 'moving_avg':
        res = forecast_moving_avg(values, periods)
    elif method == 'exponential':
        res = forecast_exp_smooth(values, periods)
    else:
        res = forecast_linear(values, periods)

    return {
        'labels':         labels,
        'future_labels':  future_labels,
        'actuals':        [round(v,4) for v in values],
        'forecast':       res['forecast'],
        'lower':          res['lower'],
        'upper':          res['upper'],
        'method':         res['method'],
        'trend':          res.get('trend','flat'),
        'periods':        periods,
        'value_col':      value_col,
        'date_col':       date_col,
    }


def ai_forecast_narrative(upload, forecast_data: dict) -> str:
    """Generate AI narrative about the forecast."""
    import anthropic
    from django.conf import settings

    client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    vals   = forecast_data.get('actuals', [])
    fc     = forecast_data.get('forecast', [])
    trend  = forecast_data.get('trend', 'flat')

    last_actual = vals[-1] if vals else 0
    first_fc    = fc[0]  if fc  else 0
    last_fc     = fc[-1] if fc  else 0
    pct_change  = ((last_fc - last_actual) / (last_actual + 1e-9)) * 100

    prompt = f"""Forecast analysis for {upload.original_name}:
Column: {forecast_data['value_col']} | Method: {forecast_data['method']}
Historical data: {len(vals)} periods | Forecast periods: {forecast_data['periods']}
Last actual value: {last_actual:,.2f}
Forecast range: {first_fc:,.2f} to {last_fc:,.2f} (trend: {trend})
Projected change: {pct_change:+.1f}% by end of forecast period

Write a concise (2-3 paragraph) forecast narrative for a business analyst:
1. What the historical trend shows
2. What the forecast predicts and confidence level
3. Key business implications and risks

Be specific, actionable, and avoid statistical jargon."""

    msg = client.messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=500,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return msg.content[0].text
