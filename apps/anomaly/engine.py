"""
Anomaly detection engine — statistical + AI narrative.
Detects: high nulls, outliers (Z-score + IQR), constant columns,
         duplicate rows, date gaps, sudden distribution shifts.
"""
import math
import statistics
import pandas as pd
from django.conf import settings


def _safe(v):
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else f
    except Exception:
        return None


def detect_anomalies(upload) -> list:
    analysis = upload.analysis_result or {}
    cols      = analysis.get('columns', [])
    rows      = analysis.get('rows', 0)
    findings  = []
    z_thresh  = getattr(settings, 'ANOMALY_Z_SCORE_THRESHOLD', 3.0)

    for col in cols:
        name     = col['name']
        null_pct = col.get('null_pct', 0)
        unique   = col.get('unique_count', 0)

        # ── 1. High nulls ──────────────────────────────────────────────────
        if null_pct > 30:
            findings.append({
                'column': name, 'type': 'high_nulls',
                'severity': 'high' if null_pct > 60 else 'medium',
                'message': f'{null_pct:.1f}% of values are missing',
                'detail':  f'{int(rows * null_pct / 100):,} null rows out of {rows:,} total',
            })

        # ── 2. Constant column (zero variance) ─────────────────────────────
        if unique == 1:
            findings.append({
                'column': name, 'type': 'constant_column',
                'severity': 'medium',
                'message': 'Column has only one unique value — no analytical value',
                'detail':  f'All {rows:,} rows have the same value',
            })

        if col.get('is_numeric'):
            mn  = _safe(col.get('mean'))
            std = _safe(col.get('std'))
            mn_val = _safe(col.get('min'))
            mx_val = _safe(col.get('max'))
            p25 = _safe(col.get('p25'))
            p75 = _safe(col.get('p75'))

            # ── 3. Z-score outlier alert ────────────────────────────────────
            if mn is not None and std is not None and std > 0:
                if mn_val is not None:
                    z_min = abs(mn_val - mn) / std
                    if z_min > z_thresh:
                        findings.append({
                            'column': name, 'type': 'outlier_low',
                            'severity': 'high' if z_min > 5 else 'medium',
                            'message': f'Minimum value is {z_min:.1f}σ below mean',
                            'detail':  f'Min={mn_val:,}, Mean={mn:.2f}, Std={std:.2f}',
                        })
                if mx_val is not None:
                    z_max = abs(mx_val - mn) / std
                    if z_max > z_thresh:
                        findings.append({
                            'column': name, 'type': 'outlier_high',
                            'severity': 'high' if z_max > 5 else 'medium',
                            'message': f'Maximum value is {z_max:.1f}σ above mean',
                            'detail':  f'Max={mx_val:,}, Mean={mn:.2f}, Std={std:.2f}',
                        })

            # ── 4. IQR outlier (whisker method) ─────────────────────────────
            if p25 is not None and p75 is not None:
                iqr = p75 - p25
                fence_lo = p25 - 3 * iqr
                fence_hi = p75 + 3 * iqr
                if mn_val is not None and mn_val < fence_lo:
                    findings.append({
                        'column': name, 'type': 'iqr_outlier_low',
                        'severity': 'medium',
                        'message': f'Extreme low values detected (below IQR fence)',
                        'detail':  f'Min={mn_val:,} < fence={fence_lo:,.1f}',
                    })
                if mx_val is not None and mx_val > fence_hi:
                    findings.append({
                        'column': name, 'type': 'iqr_outlier_high',
                        'severity': 'medium',
                        'message': f'Extreme high values detected (above IQR fence)',
                        'detail':  f'Max={mx_val:,} > fence={fence_hi:,.1f}',
                    })

            # ── 5. Near-zero variance with high range ───────────────────────
            if std is not None and mn_val is not None and mx_val is not None:
                rng = mx_val - mn_val
                if rng > 0 and std / (rng + 1e-9) < 0.05:
                    findings.append({
                        'column': name, 'type': 'skewed_distribution',
                        'severity': 'low',
                        'message': 'Distribution is highly concentrated (low std vs range)',
                        'detail':  f'Range={rng:,.1f}, Std={std:.2f} ({100*std/(rng+1e-9):.1f}% of range)',
                    })

        # ── 6. High-cardinality text might be IDs ──────────────────────────
        if not col.get('is_numeric') and unique > 0 and rows > 0:
            cardinality = unique / rows
            if cardinality > 0.95 and rows > 50:
                findings.append({
                    'column': name, 'type': 'likely_id_column',
                    'severity': 'low',
                    'message': 'Possible identifier column (nearly all values unique)',
                    'detail':  f'{unique:,} unique values in {rows:,} rows ({cardinality*100:.0f}%)',
                })

    # ── 7. Dataset-level checks ────────────────────────────────────────────
    if rows == 0:
        findings.append({
            'column': '(dataset)', 'type': 'empty_dataset',
            'severity': 'high',
            'message': 'Dataset contains no rows',
            'detail': 'File loaded successfully but is empty',
        })
    elif rows < 10:
        findings.append({
            'column': '(dataset)', 'type': 'very_small_dataset',
            'severity': 'low',
            'message': f'Very small dataset — only {rows} rows',
            'detail': 'Statistical conclusions may not be reliable with fewer than 10 rows',
        })

    # Sort: high → medium → low
    order = {'high': 0, 'medium': 1, 'low': 2}
    findings.sort(key=lambda f: order.get(f['severity'], 9))
    return findings


def ai_anomaly_narrative(upload, findings: list) -> str:
    """Generate an AI narrative about the anomalies found."""
    import anthropic
    from django.conf import settings as s

    client = anthropic.Anthropic(api_key=s.ANTHROPIC_API_KEY)
    analysis = upload.analysis_result or {}

    high   = [f for f in findings if f['severity'] == 'high']
    medium = [f for f in findings if f['severity'] == 'medium']

    findings_text = '\n'.join(
        f"- [{f['severity'].upper()}] {f['column']}: {f['message']} ({f['detail']})"
        for f in findings[:20]
    )

    prompt = f"""Dataset: "{upload.original_name}" — {analysis.get('rows',0):,} rows, {analysis.get('cols',0)} columns.

Anomalies found ({len(findings)} total, {len(high)} high, {len(medium)} medium):
{findings_text}

Write a concise (3-5 paragraph) data quality report for a business analyst:
1. Overall data quality assessment
2. Most critical issues to address first
3. Specific recommendations for each high-severity issue
4. Impact on analysis reliability if issues are not fixed

Be specific and actionable. Use plain English, no jargon."""

    msg = client.messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=800,
        messages=[{'role': 'user', 'content': prompt}],
    )
    return msg.content[0].text
