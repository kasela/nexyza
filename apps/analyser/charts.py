"""
Chart data builder v3 — semantic-aware, robust, meaningful.
Handles: ratio/%, combined dates, month sorting, numeric coercion,
         proper axis labels, scatter, histograms, heatmaps, KPIs.
"""
import math
from types import SimpleNamespace
import pandas as pd
from .engine import load_dataframe
from .intelligence import force_numeric, sort_categorical_series as _sort_cat
from .derived_metrics import add_derived_metrics
from .insight_composer import compose_chart_insight
from .annotations import build_annotations
from .schema_normalization_engine import resolve_column_name

# ── Colour palettes ────────────────────────────────────────────────────────────
_RAW = {
    'violet':  ['rgba(139,92,246,{a})',  'rgba(167,139,250,{a})', 'rgba(196,181,253,{a})'],
    'blue':    ['rgba(59,130,246,{a})',  'rgba(96,165,250,{a})',  'rgba(147,197,253,{a})'],
    'emerald': ['rgba(16,185,129,{a})',  'rgba(52,211,153,{a})',  'rgba(110,231,183,{a})'],
    'amber':   ['rgba(245,158,11,{a})',  'rgba(251,191,36,{a})',  'rgba(252,211,77,{a})'],
    'rose':    ['rgba(244,63,94,{a})',   'rgba(251,113,133,{a})', 'rgba(253,164,175,{a})'],
    'cyan':    ['rgba(6,182,212,{a})',   'rgba(34,211,238,{a})',  'rgba(103,232,249,{a})'],
    'multi':   ['rgba(139,92,246,{a})','rgba(59,130,246,{a})','rgba(16,185,129,{a})',
                'rgba(245,158,11,{a})','rgba(244,63,94,{a})','rgba(6,182,212,{a})',
                'rgba(236,72,153,{a})','rgba(251,146,60,{a})'],
}

def _palette(name: str, alpha: float = 0.75, count: int = 1) -> list:
    tpls = _RAW.get(name, _RAW['violet'])
    out  = [t.format(a=alpha) for t in tpls]
    while len(out) < count:
        out += out
    return out[:max(count, 1)]



def _resolve_series_by_name(df, column_name, *, prefer_last=False):
    """Return a single Series even when duplicate column names exist."""
    data = df.loc[:, column_name]
    if isinstance(data, pd.DataFrame):
        if data.shape[1] == 0:
            raise KeyError(column_name)
        data = data.iloc[:, -1 if prefer_last else 0]
    return data.copy()

def _sf(v):
    try:
        f = float(v)
        return None if (math.isnan(f) or math.isinf(f)) else round(f, 6)
    except (TypeError, ValueError):
        return None


def _fmt_hist_edge(v) -> str:
    """Format histogram bin edge avoiding scientific notation for large numbers."""
    try:
        f = float(v)
        if abs(f) >= 1_000:
            return f"{f:,.0f}"
        return f"{f:.3g}"
    except Exception:
        return str(v)


# ── Semantic metadata helpers ──────────────────────────────────────────────────

def _get_col_info(upload, col_name: str) -> dict:
    cols = (upload.analysis_result or {}).get('columns', [])
    hit = next((c for c in cols if c['name'] == col_name), None)
    if hit:
        return hit
    # Also resolve derived metric keys from the screening profile
    # e.g. 'achievement_pct', 'variance_to_target', 'stock_turnover'
    profile_json   = (upload.analysis_result or {}).get('profile_json') or {}
    screening_json = (upload.analysis_result or {}).get('screening_json') or {}
    if not profile_json or not screening_json:
        try:
            sp = getattr(upload, 'screening_profile', None)
            if sp is None:
                from .models import UploadAnalysisProfile
                sp = UploadAnalysisProfile.objects.filter(upload=upload).first()
            if sp:
                profile_json   = profile_json   or (sp.profile_json   or {})
                screening_json = screening_json or (sp.screening_json or {})
        except Exception:
            pass
    dm_meta = (profile_json.get('derived_metrics') or {})
    available = dm_meta.get('available') or []
    labels    = dm_meta.get('labels')    or {}
    sem_types = dm_meta.get('semantic_types') or {}
    summaries = dm_meta.get('summaries') or {}
    if col_name in available:
        summary = summaries.get(col_name) or {}
        return {
            'name':          col_name,
            'dtype':         'float64',
            'semantic_type': sem_types.get(col_name, 'metric'),
            'is_numeric':    True,
            'null_pct':      0.0,
            'unique_count':  12,
            'mean':          summary.get('mean'),
            'min':           summary.get('min'),
            'max':           summary.get('max'),
            'is_derived':    True,
            'label':         labels.get(col_name, col_name),
        }
    return {}

def _stype(upload, col_name: str) -> str:
    return _get_col_info(upload, col_name).get('semantic_type', 'text')

def _is_ratio(upload, col_name: str) -> bool:
    return _stype(upload, col_name) in ('ratio',)

# Derived metric ratio columns (achievement_pct, stock_turnover etc.) are stored
# in the dataframe already scaled (achievement_pct = 0–100, stock_turnover = 0–1).
# Do NOT multiply by 100 — the values are already in display-ready scale.
_DERIVED_RATIO_NO_SCALE = {
    'achievement_pct', 'variance_pct', 'margin_pct', 'cost_pct',
    'contribution_pct', 'actual_to_cost_ratio', 'achivement_to_purchasing_ratio',
    'given_target_to_achivement_ratio', 'given_target_to_purchasing_ratio',
    'stock_turnover',
}

def _multiplier(upload, col_name: str) -> float:
    if col_name in _DERIVED_RATIO_NO_SCALE:
        return 1.0
    return 100.0 if _is_ratio(upload, col_name) else 1.0


# ── DataFrame loading ──────────────────────────────────────────────────────────

def _load_df(upload):
    try:
        df = load_dataframe(upload.file.path, upload.file_type,
                            sheet_name=upload.active_sheet or None)
        cols = (upload.analysis_result or {}).get('columns', [])
        for c in cols:
            st   = c.get('semantic_type', 'text')
            name = c['name']
            if name in df.columns and st in ('metric','ratio','percentage','count',
                                              'currency','year','month'):
                df[name] = force_numeric(df[name])
        # Pass business_roles so derived metrics use exact profile column names
        profile_json   = (upload.analysis_result or {}).get('profile_json') or {}
        business_roles = profile_json.get('business_roles') or {}
        if not business_roles:
            try:
                sp = getattr(upload, 'screening_profile', None)
                if sp is None:
                    from .models import UploadAnalysisProfile
                    sp = UploadAnalysisProfile.objects.filter(upload=upload).first()
                if sp:
                    business_roles = (sp.profile_json or {}).get('business_roles') or {}
            except Exception:
                pass
        df, _derived = add_derived_metrics(df, business_roles=business_roles)
        return df
    except Exception:
        return None




def _resolve_chart_columns(df, chart):
    config_json = dict(chart.config_json or {})
    columns = list(df.columns)
    x_res = resolve_column_name(chart.x_axis, columns) if getattr(chart, 'x_axis', None) else None
    y_res = resolve_column_name(chart.y_axis, columns) if getattr(chart, 'y_axis', None) else None
    g_res = resolve_column_name(chart.group_by, columns) if getattr(chart, 'group_by', None) else None
    if config_json.get('target_column'):
        t_res = resolve_column_name(config_json.get('target_column'), columns)
        if t_res.resolved:
            config_json['target_column'] = t_res.resolved
    if config_json.get('benchmark_column'):
        b_res = resolve_column_name(config_json.get('benchmark_column'), columns)
        if b_res.resolved:
            config_json['benchmark_column'] = b_res.resolved
    if config_json.get('y2_axis'):
        y2_res = resolve_column_name(config_json.get('y2_axis'), columns)
        if y2_res.resolved:
            config_json['y2_axis'] = y2_res.resolved
    extras = []
    for m in (config_json.get('extra_measures') or []):
        m_res = resolve_column_name(m, columns)
        if m_res.resolved and m_res.resolved not in extras:
            extras.append(m_res.resolved)
    config_json['extra_measures'] = extras
    return SimpleNamespace(
        chart_type=chart.chart_type,
        x_axis=x_res.resolved if x_res and x_res.resolved else getattr(chart, 'x_axis', ''),
        y_axis=y_res.resolved if y_res and y_res.resolved else getattr(chart, 'y_axis', ''),
        group_by=g_res.resolved if g_res and g_res.resolved else getattr(chart, 'group_by', ''),
        aggregation=getattr(chart, 'aggregation', 'mean'),
        color=getattr(chart, 'color', 'violet'),
        title=getattr(chart, 'title', ''),
        config_json=config_json,
    )

# ── Main dispatch ──────────────────────────────────────────────────────────────

def build_chart_data(upload, chart) -> dict:
    df = _load_df(upload)
    if df is not None:
        chart = _resolve_chart_columns(df, chart)
    ctype = chart.chart_type

    if ctype == 'kpi':
        payload = _kpi(upload, chart)
    elif ctype == 'histogram':
        payload = _histogram(upload, chart)
    elif ctype == 'heatmap':
        payload = _heatmap(upload)
    else:
        combo_key = (chart.config_json or {}).get('combined_date_key', '')
        if combo_key and ctype in {'line', 'area', 'rolling_line', 'cumulative_line'}:
            payload = _time_series(upload, chart, combo_key)
        else:
            if df is None:
                payload = _from_preview(upload, chart)
            else:
                if ctype == 'pareto':
                    payload = _pareto(df, upload, chart)
                elif ctype == 'variance_bar':
                    payload = _variance_bar(df, upload, chart)
                elif ctype == 'waterfall':
                    payload = _waterfall(df, upload, chart)
                elif ctype == 'bullet':
                    payload = _bullet(df, upload, chart)
                elif ctype == 'progress_ring':
                    payload = _progress_ring(df, upload, chart)
                else:
                    payload = _standard(df, upload, chart)

    if isinstance(payload, dict) and not payload.get('error'):
        try:
            insight = compose_chart_insight(chart, payload)
            payload.update({
                'insight_summary': insight.get('summary', ''),
                'insight_driver': insight.get('driver', ''),
                'insight_risk': insight.get('risk', ''),
                'insight_next_step': insight.get('next_step', ''),
            })
            if (chart.config_json or {}).get('show_annotations', True):
                payload['annotations'] = build_annotations(payload)
        except Exception:
            pass
    return payload


# ── KPI ────────────────────────────────────────────────────────────────────────

def _kpi(upload, chart) -> dict:
    y     = chart.y_axis
    agg   = chart.aggregation or 'mean'
    cinfo = _get_col_info(upload, y)
    st    = cinfo.get('semantic_type', 'text')
    label = chart.title or y
    is_derived = cinfo.get('is_derived', False)

    if st in ('year','month','id','high_card','text','boolean','time_cat'):
        return {'kpi': True, 'value': 'N/A', 'label': label, 'sparkline': []}

    # Derived metrics (achievement_pct, variance_to_target, stock_turnover etc.)
    # are added as columns by add_derived_metrics() — always load df for them.
    mult = _multiplier(upload, y)
    # achievement_pct is stored as 0–100 in profile summaries but as 0–1 ratio in df
    # detect by checking if mean from profile summary is > 1 and type is ratio
    dm_mean = cinfo.get('mean')
    if is_derived and st == 'ratio' and dm_mean is not None and float(dm_mean or 0) > 1:
        # already a percentage value in the profile (e.g. 90.36 not 0.9036)
        mult = 1.0

    if agg == 'count':
        val = upload.row_count
    else:
        raw = None
        if is_derived:
            # Must load df — derived column only exists after add_derived_metrics()
            df = _load_df(upload)
            if df is not None and y in df.columns:
                s = pd.to_numeric(df[y], errors='coerce').dropna()
                if len(s):
                    raw = {'mean': s.mean, 'sum': s.sum,
                           'min':  s.min,  'max': s.max}.get(agg, s.sum)()
            elif dm_mean is not None:
                # Fallback to precomputed summary from profile
                raw = {'mean': dm_mean, 'sum': cinfo.get('mean'),
                       'min': cinfo.get('min'), 'max': cinfo.get('max')}.get(agg, dm_mean)
        else:
            raw = cinfo.get(agg) if agg in ('mean','min','max') else None
            if raw is None:
                df = _load_df(upload)
                if df is not None and y in df.columns:
                    s = pd.to_numeric(df[y], errors='coerce').dropna()
                    if len(s):
                        raw = {'mean': s.mean, 'sum': s.sum,
                               'min':  s.min,  'max': s.max}.get(agg, s.mean)()
        if raw is None:
            return {'kpi': True, 'value': 'N/A', 'label': label, 'sparkline': []}
        val = float(raw) * mult

    if st in ('ratio',) and agg != 'count':
        fmt = f"{val:.1f}%"
    elif st == 'percentage' and agg != 'count':
        fmt = f"{val:.1f}%"
    elif abs(val) >= 1_000_000:
        fmt = f"{val/1_000_000:.2f}M"
    elif abs(val) >= 1_000:
        fmt = f"{val:,.0f}"
    elif isinstance(val, float) and val != int(val):
        fmt = f"{val:.2f}"
    else:
        fmt = f"{int(val):,}"

    spark = (cinfo.get('histogram') or {}).get('values', [])
    cjson = chart.config_json or {}
    target_col = cjson.get('target_column') or ''
    comparison = None
    if target_col:
        df = _load_df(upload)
        if df is not None and y in df.columns and target_col in df.columns:
            actual_series = pd.to_numeric(df[y], errors='coerce')
            target_series = pd.to_numeric(df[target_col], errors='coerce')
            actual_total = actual_series.sum()
            target_total = target_series.sum()
            if pd.notna(actual_total) and pd.notna(target_total):
                variance = actual_total - target_total
                comparison = {
                    'target_value': _sf(target_total),
                    'variance_value': _sf(variance),
                    'variance_direction': 'positive' if variance >= 0 else 'negative',
                }
    return {'kpi': True, 'value': fmt, 'label': label, 'sparkline': spark, 'color': chart.color, 'comparison': comparison}


# ── Time series with combined Month+Year ───────────────────────────────────────

def _time_series(upload, chart, combo_key: str) -> dict:
    combos = (upload.analysis_result or {}).get('combined_dates', [])
    combo  = next((c for c in combos
                   if c.get('display_name') == combo_key or c.get('name') == combo_key), None)

    df = _load_df(upload)
    if df is None:
        return {'error': 'Could not load file'}

    y     = chart.y_axis
    agg   = chart.aggregation or 'mean'
    mult  = _multiplier(upload, y)
    cjson = chart.config_json or {}
    y_lbl = cjson.get('y_label') or (f'{y} (%)' if _is_ratio(upload, y) else y)

    # ── No combo found: try using the combo_key as a plain time column ────
    if not combo:
        # Check if combo_key is a direct column in the df (e.g. Month)
        if combo_key and combo_key in df.columns and y in df.columns:
            try:
                from .intelligence import sort_categorical_series as _sort_cat, MONTH_ORDER
                df_work = df.copy()
                df_work[y] = pd.to_numeric(df_work[y], errors='coerce')
                df_work = df_work.dropna(subset=[y])
                agg_fn = {'mean':'mean','sum':'sum','count':'count','min':'min','max':'max'}.get(agg,'mean')
                # Include Year if present for proper sorting
                year_col = next((c for c in df.columns if c.lower() == 'year'), None)
                if year_col:
                    df_work[year_col] = pd.to_numeric(df_work[year_col], errors='coerce')
                    grouped = df_work.groupby([year_col, combo_key])[y].agg(agg_fn).reset_index()
                    from .intelligence import MONTH_NAMES
                    def _period_sort(row):
                        yr = int(row[year_col]) if pd.notna(row[year_col]) else 9999
                        mn = MONTH_NAMES.get(str(row[combo_key]).strip().lower(), 0)
                        return yr * 100 + mn
                    grouped['_sort'] = grouped.apply(_period_sort, axis=1)
                    grouped = grouped.sort_values('_sort')
                    def _period_lbl(row):
                        mn = MONTH_NAMES.get(str(row[combo_key]).strip().lower(), 0)
                        abbr = MONTH_ORDER[mn - 1][:3] if 1 <= mn <= 12 else str(row[combo_key])
                        return f"{abbr} {int(row[year_col])}" if pd.notna(row[year_col]) else str(row[combo_key])
                    labels = [_period_lbl(r) for _, r in grouped.iterrows()]
                    vals   = [_sf(v * mult) for v in grouped[y].tolist()]
                else:
                    grouped = df_work.groupby(combo_key)[y].agg(agg_fn).reset_index()
                    idxs    = _sort_cat(grouped[combo_key].tolist())
                    labels  = [grouped[combo_key].tolist()[i] for i in idxs]
                    vals    = [_sf(grouped[y].tolist()[i] * mult) for i in idxs]

                # Add target overlay if configured; also honour extra_measures from AI specs
                target_col = cjson.get('target_column') or ''
                extra_measures_ts = [m for m in (cjson.get('extra_measures') or []) if m and m != y]
                # If target_column not set but extra_measures has a target, use it
                if not target_col and extra_measures_ts:
                    target_col = extra_measures_ts[0]
                # Build additional series: target first, then remaining extra_measures
                overlay_cols = []
                if target_col:
                    overlay_cols.append(target_col)
                for m in extra_measures_ts:
                    if m != target_col and m not in overlay_cols:
                        overlay_cols.append(m)

                datasets = [{
                    'label': y_lbl, 'data': vals,
                    'backgroundColor': _palette(chart.color, 0.75)[0],
                    'borderColor': _palette(chart.color, 1.0)[0],
                    'borderWidth': 2.5, 'tension': 0.4,
                    'fill': chart.chart_type in ('area',),
                    'pointRadius': min(4, max(2, 14 - len(vals))),
                    'pointHoverRadius': 6,
                }]
                OVERLAY_COLORS = [
                    ('rgba(251,191,36,1)', 'rgba(251,191,36,0.15)'),
                    ('rgba(16,185,129,1)', 'rgba(16,185,129,0.15)'),
                    ('rgba(244,63,94,1)',  'rgba(244,63,94,0.15)'),
                ]
                for oi, oc in enumerate(overlay_cols):
                    if oc not in df.columns:
                        continue
                    df_work2 = df.copy()
                    df_work2[oc] = pd.to_numeric(df_work2[oc], errors='coerce')
                    if year_col:
                        tg = df_work2.groupby([year_col, combo_key])[oc].agg('sum').reset_index()
                        tg['_sort'] = tg.apply(lambda r: (int(r[year_col]) if pd.notna(r[year_col]) else 9999)*100, axis=1)
                        tg = tg.sort_values('_sort')
                        t_vals = [_sf(v) for v in tg[oc].tolist()]
                    else:
                        tg = df_work2.groupby(combo_key)[oc].agg('sum').reset_index()
                        idxs2 = _sort_cat(tg[combo_key].tolist())
                        t_vals = [_sf(tg[oc].tolist()[i]) for i in idxs2]
                    bc, bgc = OVERLAY_COLORS[oi % len(OVERLAY_COLORS)]
                    datasets.append({
                        'label': oc, 'data': t_vals,
                        'borderColor': bc, 'backgroundColor': bgc,
                        'borderWidth': 1.5, 'borderDash': [5, 3], 'tension': 0.4,
                        'pointRadius': min(3, max(2, 14 - len(t_vals))), 'pointHoverRadius': 5,
                        'fill': False,
                    })

                return {
                    'labels': labels, 'datasets': datasets,
                    'chart_type': 'line',
                    'x_label': cjson.get('x_label', combo_key),
                    'y_label': y_lbl,
                }
            except Exception as e:
                return _standard(df, upload, chart) if df is not None else {'error': str(e)}
        return _standard(df, upload, chart) if df is not None else {'error': 'Combo not found'}

    from .intelligence import build_time_series_df

    try:
        grouped = build_time_series_df(df, combo, y, agg)
        if grouped.empty:
            return {'error': 'No data after date combination'}

        if chart.chart_type == 'rolling_line':
            window = max(2, int((chart.config_json or {}).get('rolling_window') or 3))
            grouped['value'] = grouped['value'].rolling(window=window, min_periods=1).mean()
        elif chart.chart_type == 'cumulative_line':
            grouped['value'] = grouped['value'].cumsum()

        if mult != 1:
            grouped['value'] = grouped['value'] * mult

        labels = grouped['period_label'].tolist()
        vals   = [_sf(v) for v in grouped['value'].tolist()]
        ctype  = chart.chart_type

        datasets = [{
            'label':           y_lbl,
            'data':            vals,
            'backgroundColor': _palette(chart.color, 0.75)[0],
            'borderColor':     _palette(chart.color, 1.0)[0],
            'borderWidth':     2.5,
            'tension':         0.4,
            'fill':            ctype in ('area',),
            'pointRadius':     min(4, max(2, 14 - len(vals))),
            'pointHoverRadius': 6,
        }]

        # Target / extra_measures overlays for combo-date time series
        target_col_c = cjson.get('target_column') or ''
        extra_ts_c   = [m for m in (cjson.get('extra_measures') or []) if m and m != y]
        if not target_col_c and extra_ts_c:
            target_col_c = extra_ts_c[0]
        overlay_cols_c = ([target_col_c] if target_col_c else []) + [m for m in extra_ts_c if m != target_col_c]
        OV_COLORS = [('rgba(251,191,36,1)', 'rgba(251,191,36,0.15)'), ('rgba(16,185,129,1)', 'rgba(16,185,129,0.15)')]
        for oi, oc in enumerate(overlay_cols_c):
            try:
                tg = build_time_series_df(df, combo, oc, 'sum')
                if not tg.empty:
                    t_vals = [_sf(v) for v in tg['value'].tolist()]
                    bc, bgc = OV_COLORS[oi % len(OV_COLORS)]
                    datasets.append({
                        'label': oc, 'data': t_vals,
                        'borderColor': bc, 'backgroundColor': bgc,
                        'borderWidth': 1.5, 'borderDash': [5, 3], 'tension': 0.4,
                        'pointRadius': min(3, max(2, 14 - len(t_vals))), 'pointHoverRadius': 5,
                        'fill': False,
                    })
            except Exception:
                pass

        return {
            'labels': labels,
            'datasets': datasets,
            'chart_type': 'line' if ctype in ('line','area','rolling_line','cumulative_line') else 'bar',
            'x_label':   cjson.get('x_label', combo_key),
            'y_label':   y_lbl,
        }
    except Exception as e:
        return {'error': str(e)}


# ── Standard chart ─────────────────────────────────────────────────────────────


def _count_frequency(df, upload, chart, x_col: str) -> dict:
    """Build a frequency/distribution chart by counting occurrences of x_col values."""
    from .intelligence import _sort_cat
    df = _load_df(upload)
    if df is not None:
        chart = _resolve_chart_columns(df, chart)
    ctype = chart.chart_type
    cjson = chart.config_json or {}

    try:
        vc     = df[x_col].dropna().value_counts()
        x_st   = _stype(upload, x_col)

        if x_st in ('year', 'month', 'time_cat', 'date'):
            # Sort chronologically
            raw_labels = [str(k) for k in vc.index.tolist()]
            idxs       = _sort_cat(raw_labels)
            labels     = [raw_labels[i] for i in idxs]
            vals       = [int(vc.iloc[idxs[i]]) for i in range(len(idxs))]
        else:
            # Sort by frequency descending, top 25
            vc     = vc.head(25)
            labels = [str(k) for k in vc.index.tolist()]
            vals   = [int(v) for v in vc.values.tolist()]

        if not labels:
            return {'labels': [], 'datasets': []}

        real = 'bar' if ctype in ('horizontal_bar', 'variance_bar') else ('line' if ctype in ('area', 'rolling_line', 'cumulative_line') else ctype)
        if ctype in ('pie', 'doughnut'):
            bg = _palette(chart.color, 0.75, len(vals))
            bd = _palette(chart.color, 1.0,  len(vals))
        else:
            bg = _palette(chart.color, 0.75)[0]
            bd = _palette(chart.color, 1.0)[0]

        return {
            'labels': labels,
            'datasets': [{
                'label':           f'Count of {x_col}',
                'data':            vals,
                'backgroundColor': bg,
                'borderColor':     bd,
                'borderWidth':     2,
                'borderRadius':    4 if ctype in ('bar', 'horizontal_bar') else 0,
            }],
            'chart_type':    real,
            'is_horizontal': ctype == 'horizontal_bar',
            'x_label':       cjson.get('x_label', x_col),
            'y_label':       'Count',
        }
    except Exception as e:
        return {'error': str(e)}



def _apply_series_transforms(grouped, x_col, y_col, chart, upload):
    cjson = chart.config_json or {}
    df = _load_df(upload)
    if df is not None:
        chart = _resolve_chart_columns(df, chart)
    ctype = chart.chart_type
    top_n = int(cjson.get('top_n') or 10)
    bottom_n = bool(cjson.get('bottom_n'))

    if ctype == 'rolling_line':
        window = max(2, int(cjson.get('rolling_window') or 3))
        grouped[y_col] = grouped[y_col].rolling(window=window, min_periods=1).mean()
    elif ctype == 'cumulative_line':
        grouped[y_col] = grouped[y_col].cumsum()
    elif ctype in {'horizontal_bar', 'variance_bar', 'pareto'}:
        grouped = grouped.sort_values(y_col, ascending=bottom_n).head(top_n)
    return grouped


def _pareto(df, upload, chart) -> dict:
    x, y = chart.x_axis, chart.y_axis
    agg = chart.aggregation or 'sum'
    if x not in df.columns or y not in df.columns:
        return {'error': f'Column not found: {x!r} or {y!r}'}

    working = df.copy()
    working[y] = force_numeric(working[y])
    working = working.dropna(subset=[y])
    if working.empty:
        return {'error': f'No numeric values found in {y!r}'}

    grouped = working.groupby(x)[y].agg(agg).reset_index().sort_values(y, ascending=False)
    top_n = int((chart.config_json or {}).get('top_n') or 10)
    grouped = grouped.head(top_n)
    total = grouped[y].sum() or 1
    grouped['cumulative_pct'] = grouped[y].cumsum() / total * 100

    labels = [str(v) for v in grouped[x].tolist()]
    bar_vals = [_sf(v) for v in grouped[y].tolist()]
    line_vals = [_sf(v) for v in grouped['cumulative_pct'].tolist()]

    return {
        'labels': labels,
        'datasets': [
            {
                'label': y,
                'data': bar_vals,
                'backgroundColor': _palette(chart.color, 0.75)[0],
                'borderColor': _palette(chart.color, 1.0)[0],
                'borderWidth': 2,
                'borderRadius': 4,
                'type': 'bar',
                'order': 2,
            },
            {
                'label': 'Cumulative %',
                'data': line_vals,
                'backgroundColor': 'rgba(96,165,250,0.25)',
                'borderColor': 'rgba(96,165,250,1)',
                'borderWidth': 2.5,
                'type': 'line',
                'tension': 0.35,
                'yAxisID': 'y2',
                'order': 1,
            }
        ],
        'chart_type': 'bar',
        'x_label': (chart.config_json or {}).get('x_label') or x,
        'y_label': (chart.config_json or {}).get('y_label') or y,
        'has_dual_axis': True,
        'y2_label': 'Cumulative %',
    }


def _variance_bar(df, upload, chart) -> dict:
    x, y = chart.x_axis, chart.y_axis
    cjson = chart.config_json or {}
    target_col = cjson.get('target_column') or ''
    agg = chart.aggregation or 'sum'
    if not target_col or target_col not in df.columns:
        return {'error': 'Variance chart requires a target column in chart config.'}
    if x not in df.columns or y not in df.columns:
        return {'error': f'Column not found: {x!r} or {y!r}'}

    target_key = target_col if target_col != y else f'{target_col}__target'
    working = pd.DataFrame({
        x: _resolve_series_by_name(df, x),
        y: force_numeric(_resolve_series_by_name(df, y)),
        target_key: force_numeric(_resolve_series_by_name(df, target_col, prefer_last=(target_col == y))),
    })
    working = working.dropna(subset=[y, target_key])
    if working.empty:
        return {'error': 'No comparable numeric values found for actual vs target.'}

    grouped = working.groupby(x)[[y, target_key]].agg(agg).reset_index()
    grouped['variance'] = grouped[y] - grouped[target_key]
    grouped = grouped.sort_values('variance', ascending=False)
    top_n = int(cjson.get('top_n') or 10)
    grouped = grouped.head(top_n)

    labels = [str(v) for v in grouped[x].tolist()]
    vals = [_sf(v) for v in grouped['variance'].tolist()]
    bg = ['rgba(16,185,129,0.75)' if (v or 0) >= 0 else 'rgba(244,63,94,0.75)' for v in vals]
    bd = ['rgba(16,185,129,1)' if (v or 0) >= 0 else 'rgba(244,63,94,1)' for v in vals]
    return {
        'labels': labels,
        'datasets': [{
            'label': f'{y} variance vs {target_col}',
            'data': vals,
            'backgroundColor': bg,
            'borderColor': bd,
            'borderWidth': 2,
            'borderRadius': 4,
        }],
        'chart_type': 'bar',
        'x_label': cjson.get('x_label') or x,
        'y_label': cjson.get('y_label') or 'Variance',
    }



def _waterfall(df, upload, chart) -> dict:
    x, y = chart.x_axis, chart.y_axis
    agg = chart.aggregation or 'sum'
    cjson = chart.config_json or {}
    if x not in df.columns or y not in df.columns:
        return {'error': f'Column not found: {x!r} or {y!r}'}

    working = pd.DataFrame({
        x: _resolve_series_by_name(df, x),
        y: force_numeric(_resolve_series_by_name(df, y)),
    }).dropna(subset=[y])
    if working.empty:
        return {'error': f'No numeric values found in {y!r}'}

    grouped = working.groupby(x)[y].agg(agg).reset_index()
    sort_desc = not bool(cjson.get('bottom_n'))
    grouped = grouped.sort_values(y, ascending=not sort_desc)
    top_n = int(cjson.get('top_n') or 10)
    grouped = grouped.head(top_n)
    grouped['start'] = grouped[y].cumsum().shift(fill_value=0)
    grouped['end'] = grouped['start'] + grouped[y]

    labels = [str(v) for v in grouped[x].tolist()]
    vals = [_sf(v) for v in grouped[y].tolist()]
    starts = [_sf(v) for v in grouped['start'].tolist()]
    bg = ['rgba(16,185,129,0.75)' if (v or 0) >= 0 else 'rgba(244,63,94,0.75)' for v in vals]
    bd = ['rgba(16,185,129,1)' if (v or 0) >= 0 else 'rgba(244,63,94,1)' for v in vals]
    return {
        'labels': labels,
        'datasets': [{
            'label': y,
            'data': vals,
            'base': starts,
            'backgroundColor': bg,
            'borderColor': bd,
            'borderWidth': 2,
            'borderRadius': 4,
        }],
        'chart_type': 'bar',
        'x_label': cjson.get('x_label') or x,
        'y_label': cjson.get('y_label') or y,
        'waterfall_mode': True,
    }


def _bullet(df, upload, chart) -> dict:
    x, y = chart.x_axis, chart.y_axis
    cjson = chart.config_json or {}
    target_col = cjson.get('target_column') or ''
    agg = chart.aggregation or 'sum'
    if not target_col or target_col not in df.columns:
        return {'error': 'Bullet chart requires a target column in chart config.'}
    if x not in df.columns or y not in df.columns:
        return {'error': f'Column not found: {x!r} or {y!r}'}

    target_key = target_col if target_col != y else f'{target_col}__target'
    working = pd.DataFrame({
        x: _resolve_series_by_name(df, x),
        y: force_numeric(_resolve_series_by_name(df, y)),
        target_key: force_numeric(_resolve_series_by_name(df, target_col, prefer_last=(target_col == y))),
    }).dropna(subset=[y, target_key])
    if working.empty:
        return {'error': 'No comparable numeric values found for actual vs target.'}

    grouped = working.groupby(x)[[y, target_key]].agg(agg).reset_index()
    grouped = grouped.sort_values(y, ascending=False)
    top_n = int(cjson.get('top_n') or 10)
    grouped = grouped.head(top_n)

    labels = [str(v) for v in grouped[x].tolist()]
    actual_vals = [_sf(v) for v in grouped[y].tolist()]
    target_vals = [_sf(v) for v in grouped[target_key].tolist()]
    return {
        'labels': labels,
        'datasets': [
            {
                'label': y,
                'data': actual_vals,
                'backgroundColor': _palette(chart.color, 0.75)[0],
                'borderColor': _palette(chart.color, 1.0)[0],
                'borderWidth': 2,
                'borderRadius': 4,
                'type': 'bar',
                'order': 2,
            },
            {
                'label': target_col,
                'data': target_vals,
                'backgroundColor': 'rgba(0,0,0,0)',
                'borderColor': 'rgba(251,191,36,1)',
                'pointBackgroundColor': 'rgba(251,191,36,1)',
                'pointBorderColor': 'rgba(251,191,36,1)',
                'pointRadius': 5,
                'showLine': False,
                'type': 'line',
                'order': 1,
            },
        ],
        'chart_type': 'bar',
        'x_label': cjson.get('x_label') or x,
        'y_label': cjson.get('y_label') or y,
        'bullet_mode': True,
    }


def _progress_ring(df, upload, chart) -> dict:
    y = chart.y_axis
    cjson = chart.config_json or {}
    target_col = cjson.get('target_column') or cjson.get('benchmark_column') or ''
    agg = chart.aggregation or 'sum'
    if y not in df.columns:
        return {'error': f'Column not found: {y!r}'}

    actual = force_numeric(_resolve_series_by_name(df, y)).dropna()
    if actual.empty:
        return {'error': f'No numeric values found in {y!r}'}
    actual_total = getattr(actual, agg, actual.sum)() if hasattr(actual, agg) else actual.sum()

    target_total = None
    if target_col and target_col in df.columns:
        target = force_numeric(_resolve_series_by_name(df, target_col, prefer_last=(target_col == y))).dropna()
        if not target.empty:
            target_total = getattr(target, agg, target.sum)() if hasattr(target, agg) else target.sum()
    if target_total in (None, 0) or pd.isna(target_total):
        target_total = actual_total or 1

    progress = max(0.0, min(float(actual_total) / float(target_total) * 100.0, 100.0))
    remainder = max(0.0, 100.0 - progress)
    return {
        'labels': ['Progress', 'Remaining'],
        'datasets': [{
            'label': chart.title or y,
            'data': [_sf(progress), _sf(remainder)],
            'backgroundColor': [_palette(chart.color, 0.85)[0], 'rgba(148,163,184,0.25)'],
            'borderColor': [_palette(chart.color, 1.0)[0], 'rgba(148,163,184,0.35)'],
            'borderWidth': 2,
        }],
        'chart_type': 'doughnut',
        'center_label': f'{progress:.1f}%',
        'x_label': '',
        'y_label': cjson.get('y_label') or y,
        'progress_mode': True,
    }

def _standard(df, upload, chart) -> dict:

    ctype  = chart.chart_type
    x, y   = chart.x_axis, chart.y_axis
    agg    = chart.aggregation or 'mean'
    group  = chart.group_by
    cjson  = chart.config_json or {}

    # Multi-measure: additional y columns beyond the primary y_axis
    extra_measures = [m for m in (cjson.get('extra_measures') or []) if m and m != y]
    y2_col         = cjson.get('y2_axis', '')   # column for right y-axis

    if not x or not y:
        # If agg is count and x exists, we can still do a frequency chart
        if agg == 'count' and x and x in df.columns:
            return _count_frequency(df, upload, chart, x)
        return {'labels': [], 'datasets': []}

    # Fuzzy column name matching — handles case differences & extra spaces
    def _find_col(name, df):
        if name in df.columns:
            return name
        nl = name.lower().strip().replace(' ','_').replace('-','_')
        for c in df.columns:
            if c.lower().strip().replace(' ','_').replace('-','_') == nl:
                return c
        return name   # return original (will fail later with clear error)

    x = _find_col(x, df)
    y = _find_col(y, df)

    # If agg=count, use frequency chart (works for ALL column types)
    if agg == 'count':
        return _count_frequency(df, upload, chart, x)

    if x not in df.columns or y not in df.columns:
        return {'error': f'Column not found: {x!r} or {y!r}'}

    try:
        df_w = df.copy()
        df_w[y] = force_numeric(df_w[y])
        if _stype(upload, x) in ('metric','ratio','percentage','count','currency','year','month'):
            df_w[x] = force_numeric(df_w[x])
        df_w = df_w.dropna(subset=[y])
        if df_w.empty:
            # Try harder — maybe the column is numeric but stored as strings
            df_w = df.copy()
            df_w[y] = force_numeric(df_w[y])
            df_w = df_w.dropna(subset=[y])
            if df_w.empty:
                # If y is text/same as x, fall back to COUNT distribution of x
                y_stype = _stype(upload, y)
                if y_stype in ('category','high_card','text','id','boolean') or x == y:
                    # Count occurrences of x values — valid for distribution charts
                    try:
                        vc = df[x].value_counts().head(20)
                        if vc.empty:
                            return {'error': f'No data in column "{x}"'}
                        labels = [str(k) for k in vc.index.tolist()]
                        vals   = [int(v) for v in vc.values.tolist()]
                        real   = 'bar' if ctype in ('horizontal_bar', 'variance_bar') else ('line' if ctype in ('area', 'rolling_line', 'cumulative_line') else ctype)
                        if ctype in ('pie','doughnut'):
                            bg = _palette(chart.color, 0.75, len(vals))
                            bd = _palette(chart.color, 1.0,  len(vals))
                        else:
                            bg = _palette(chart.color, 0.75)[0]
                            bd = _palette(chart.color, 1.0)[0]
                        return {
                            'labels': labels, 'datasets': [{
                                'label': f'Count of {x}', 'data': vals,
                                'backgroundColor': bg, 'borderColor': bd,
                                'borderWidth': 2, 'borderRadius': 4,
                            }],
                            'chart_type': real,
                            'is_horizontal': ctype == 'horizontal_bar',
                            'x_label': x, 'y_label': 'Count',
                        }
                    except Exception:
                        pass
                    return {'error': f'Column "{y}" is text — no numeric data to plot'}
                return {'error': f'No numeric values found in "{y}"'}

        mult   = _multiplier(upload, y)
        y_lbl  = cjson.get('y_label') or (f'{y} (%)' if _is_ratio(upload, y) else y)
        x_lbl  = cjson.get('x_label') or x

        # Scatter
        if ctype == 'scatter':
            df_w[x] = force_numeric(df_w[x])
            df_w[y] = force_numeric(df_w[y])
            df_w    = df_w.dropna(subset=[x, y])
            mx      = _multiplier(upload, x)
            return {
                'chart_type': 'scatter',
                'datasets': [{
                    'label':           f'{y_lbl} vs {x_lbl}',
                    'data':            [{'x': round(float(r[x]) * mx, 4), 'y': round(float(r[y]) * mult, 4)}
                                        for _, r in df_w[[x,y]].head(300).iterrows()
                                        if pd.notna(r[x]) and pd.notna(r[y])],
                    'backgroundColor': _palette(chart.color, 0.55)[0],
                    'borderColor':     _palette(chart.color, 0.9)[0],
                    'pointRadius':     4,
                    'pointHoverRadius': 7,
                }],
                'x_label': x_lbl, 'y_label': y_lbl,
            }

        # Grouped pivot
        if group and group in df_w.columns:
            pivot = df_w.groupby([x, group])[y].agg(agg).unstack(fill_value=0)
            raw_l = [str(l) for l in pivot.index.tolist()]
            idxs  = _sort_cat(raw_l)
            labels = [raw_l[i] for i in idxs]
            mc     = _palette('multi', 0.75, len(pivot.columns))
            mcb    = _palette('multi', 1.0,  len(pivot.columns))
            datasets = []
            for ci, col in enumerate(pivot.columns):
                vals = [_sf(pivot[col].tolist()[i]) for i in idxs]
                if mult != 1:
                    vals = [v * mult if v is not None else None for v in vals]
                datasets.append({
                    'label':           str(col),
                    'data':            vals,
                    'backgroundColor': mc[ci],
                    'borderColor':     mcb[ci],
                    'borderWidth':     2, 'tension': 0.4,
                    'fill':            ctype in ('area',),
                    'borderRadius':    4 if ctype in ('bar','horizontal_bar') else 0,
                })
            real = 'bar' if ctype in ('horizontal_bar', 'variance_bar') else ('line' if ctype in ('area', 'rolling_line', 'cumulative_line') else ctype)
            return {'labels': labels, 'datasets': datasets, 'chart_type': real,
                    'is_horizontal': ctype == 'horizontal_bar',
                    'x_label': x_lbl, 'y_label': y_lbl}

        # Single series — handle x==y (count distribution) separately
        if x == y:
            # Count occurrences: value_counts of x
            vc = df_w[x].value_counts().head(20)
            labels = [str(k) for k in vc.index.tolist()]
            vals   = [int(v) for v in vc.values.tolist()]
            real   = 'bar' if ctype in ('horizontal_bar', 'variance_bar') else ('line' if ctype in ('area', 'rolling_line', 'cumulative_line') else ctype)
            if ctype in ('pie','doughnut'):
                bg = _palette(chart.color, 0.75, len(vals))
                bd = _palette(chart.color, 1.0,  len(vals))
            else:
                bg = _palette(chart.color, 0.75)[0]
                bd = _palette(chart.color, 1.0)[0]
            return {
                'labels': labels, 'datasets': [{
                    'label': f'Count of {x}', 'data': vals,
                    'backgroundColor': bg, 'borderColor': bd,
                    'borderWidth': 2, 'borderRadius': 4,
                }],
                'chart_type': real,
                'is_horizontal': ctype == 'horizontal_bar',
                'x_label': cjson.get('x_label', x),
                'y_label': 'Count',
            }
        grouped = df_w.groupby(x)[y].agg(agg).reset_index().dropna(subset=[y])
        x_st    = _stype(upload, x)
        raw_l   = [str(l) for l in grouped[x].tolist()]
        idxs    = _sort_cat(raw_l)

        if x_st in ('year','month','time_cat','date'):
            grouped = grouped.iloc[idxs].reset_index(drop=True)
        elif x_st == 'high_card' or ctype == 'horizontal_bar':
            grouped = grouped.sort_values(y, ascending=False).head(20)
        else:
            grouped = grouped.sort_values(y, ascending=False).head(25)

        grouped = _apply_series_transforms(grouped, x, y, chart, upload)

        if mult != 1:
            grouped[y] = grouped[y] * mult

        labels   = [str(v) for v in grouped[x].tolist()]
        vals     = [_sf(v) for v in grouped[y].tolist()]
        real = 'bar' if ctype in ('horizontal_bar', 'variance_bar') else ('line' if ctype in ('area', 'rolling_line', 'cumulative_line') else ctype)
        has_dual = bool(y2_col and y2_col in df_w.columns and y2_col != y)

        # ── Multi-measure: collect all y columns ─────────────────────────────
        all_measures = [y] + [m for m in extra_measures if m in df_w.columns and m != y]
        MULTI_COLORS = ['violet','blue','emerald','amber','rose','cyan','multi']
        MC_BG  = ['rgba(139,92,246,0.7)','rgba(59,130,246,0.7)','rgba(16,185,129,0.7)',
                  'rgba(245,158,11,0.7)','rgba(244,63,94,0.7)','rgba(6,182,212,0.7)']
        MC_BD  = ['rgba(139,92,246,1)','rgba(59,130,246,1)','rgba(16,185,129,1)',
                  'rgba(245,158,11,1)','rgba(244,63,94,1)','rgba(6,182,212,1)']

        if ctype in ('pie','doughnut'):
            bg = _palette(chart.color, 0.75, len(vals))
            bd = _palette(chart.color, 1.0,  len(vals))
            datasets = [{'label': y_lbl, 'data': vals,
                         'backgroundColor': bg, 'borderColor': bd,
                         'borderWidth': 2}]
        elif len(all_measures) > 1:
            # Multi-measure grouped chart
            datasets = []
            for mi, measure in enumerate(all_measures):
                is_y2   = (measure == y2_col)
                m_mult  = _multiplier(upload, measure)
                m_lbl   = cjson.get(f'label_{measure}') or measure
                if measure == y:
                    m_vals = vals
                else:
                    df_m = df_w.copy()
                    df_m[measure] = force_numeric(df_m[measure])
                    m_grouped = df_m.dropna(subset=[measure]).groupby(x)[measure].agg(agg).reset_index()
                    x_st2 = _stype(upload, x)
                    if x_st2 in ('year','month','time_cat','date'):
                        raw2 = [str(l) for l in m_grouped[x].tolist()]
                        idxs2 = _sort_cat(raw2)
                        m_grouped = m_grouped.iloc[idxs2].reset_index(drop=True)
                    else:
                        # Align to same labels as primary
                        lbl_map = {str(row[x]): row[measure] for _, row in m_grouped.iterrows()}
                        m_grouped_vals = [_sf(lbl_map.get(lbl)) for lbl in labels]
                    if x_st2 in ('year','month','time_cat','date'):
                        m_vals = [_sf(v) * m_mult if _sf(v) is not None else None
                                  for v in m_grouped[measure].tolist()]
                    else:
                        lbl_map = {str(row[x]): _sf(row[measure]) for _, row in m_grouped.iterrows()}
                        m_vals  = [lbl_map.get(lbl) for lbl in labels]
                        if m_mult != 1:
                            m_vals = [v * m_mult if v is not None else None for v in m_vals]

                # Determine chart type per measure (secondary = line, primary = bar/line)
                ds_type = 'line' if (is_y2 and real == 'bar') else real

                ds = {
                    'label':           m_lbl if not _is_ratio(upload, measure) else f'{m_lbl} (%)',
                    'data':            m_vals,
                    'backgroundColor': MC_BG[mi % len(MC_BG)],
                    'borderColor':     MC_BD[mi % len(MC_BD)],
                    'borderWidth':     2.5 if ds_type == 'line' else 2,
                    'tension':         0.4,
                    'fill':            ctype == 'area' and mi == 0,
                    'borderRadius':    4 if real in ('bar','horizontal_bar') else 0,
                    'type':            ds_type,
                    'order':           0 if is_y2 else mi + 1,
                }
                if is_y2:
                    ds['yAxisID'] = 'y2'
                datasets.append(ds)
        else:
            # Single measure
            bg = _palette(chart.color, 0.75)[0]
            bd = _palette(chart.color, 1.0)[0]
            datasets = [{'label': y_lbl, 'data': vals,
                         'backgroundColor': bg, 'borderColor': bd,
                         'borderWidth': 2, 'tension': 0.4,
                         'fill': ctype == 'area',
                         'borderRadius': 4 if ctype in ('bar','horizontal_bar') else 0}]

        target_overlay = cjson.get('target_column') or ''
        if target_overlay and target_overlay in df_w.columns and target_overlay != y and ctype in ('bar', 'horizontal_bar', 'line', 'area', 'rolling_line', 'cumulative_line'):
            try:
                df_t = df.copy()
                df_t[target_overlay] = force_numeric(df_t[target_overlay])
                t_grouped = df_t.dropna(subset=[target_overlay]).groupby(x)[target_overlay].agg(agg).reset_index()
                lbl_map = {str(row[x]): _sf(row[target_overlay]) for _, row in t_grouped.iterrows()}
                t_vals = [lbl_map.get(lbl) for lbl in labels]
                datasets.append({
                    'label': f'{target_overlay} target',
                    'data': t_vals,
                    'backgroundColor': 'rgba(245,158,11,0.20)',
                    'borderColor': 'rgba(245,158,11,1)',
                    'borderWidth': 2.5,
                    'tension': 0.35,
                    'fill': False,
                    'type': 'line' if real == 'bar' else real,
                    'order': 0,
                })
            except Exception:
                pass

        result = {
            'labels': labels, 'datasets': datasets,
            'chart_type': real,
            'is_horizontal': ctype == 'horizontal_bar',
            'x_label': x_lbl, 'y_label': y_lbl,
            'has_dual_axis': has_dual,
        }
        # Dual y-axis metadata for Chart.js scales config
        if has_dual and len(all_measures) > 1:
            y2_lbl = y2_col
            if _is_ratio(upload, y2_col):
                y2_lbl = f'{y2_col} (%)'
            result['y2_label'] = y2_lbl

        return result

    except Exception as e:
        return {'error': str(e)}


# ── Histogram ─────────────────────────────────────────────────────────────────

def _histogram(upload, chart) -> dict:
    col   = chart.x_axis or chart.y_axis
    cinfo = _get_col_info(upload, col)
    st    = cinfo.get('semantic_type', 'text')
    hist  = cinfo.get('histogram')

    # Text/categorical columns → frequency bar chart instead of histogram
    if st in ('category', 'high_card', 'boolean', 'text', 'id', 'time_cat'):
        df = _load_df(upload)
        if df is not None and col in df.columns:
            vc = df[col].dropna().value_counts().head(25)
            if not vc.empty:
                return {
                    'labels': [str(k) for k in vc.index.tolist()],
                    'datasets': [{
                        'label': f'Count of {col}', 'data': [int(v) for v in vc.values.tolist()],
                        'backgroundColor': _palette(chart.color, 0.7)[0],
                        'borderColor': _palette(chart.color, 1.0)[0],
                        'borderWidth': 1, 'borderRadius': 3,
                    }],
                    'chart_type': 'bar', 'x_label': col, 'y_label': 'Count',
                }

    if hist:
        return {
            'labels': hist['labels'],
            'datasets': [{
                'label': col, 'data': hist['values'],
                'backgroundColor': _palette(chart.color, 0.7)[0],
                'borderColor':     _palette(chart.color, 1.0)[0],
                'borderWidth': 1, 'borderRadius': 3,
                'categoryPercentage': 1.0, 'barPercentage': 0.95,
            }],
            'chart_type': 'bar', 'x_label': col, 'y_label': 'Frequency',
        }

    df = _load_df(upload)
    if df is None or col not in df.columns:
        return {'error': f'Column {col!r} not found'}
    try:
        s = pd.to_numeric(df[col], errors='coerce').dropna()
        n_bins = max(2, min(10, s.nunique()))
        if len(s) < 2 or s.nunique() < 2:
            # Too few unique values — just show value counts as bar
            vc = s.value_counts()
            return {
                'labels': [str(v) for v in vc.index.tolist()],
                'datasets': [{
                    'label': col, 'data': [int(v) for v in vc.values.tolist()],
                    'backgroundColor': _palette(chart.color, 0.7)[0],
                    'borderColor': _palette(chart.color, 1.0)[0],
                    'borderWidth': 1, 'borderRadius': 3,
                }],
                'chart_type': 'bar', 'x_label': col, 'y_label': 'Count',
            }
        counts, edges = pd.cut(s, bins=n_bins, retbins=True)
        freq = counts.value_counts(sort=False)
        return {
            'labels': [f"{_fmt_hist_edge(edges[i])}–{_fmt_hist_edge(edges[i+1])}" for i in range(len(edges)-1)],
            'datasets': [{
                'label': col, 'data': [int(v) for v in freq.values],
                'backgroundColor': _palette(chart.color, 0.7)[0],
                'borderColor':     _palette(chart.color, 1.0)[0],
                'borderWidth': 1, 'borderRadius': 3,
                'categoryPercentage': 1.0, 'barPercentage': 0.95,
            }],
            'chart_type': 'bar', 'x_label': col, 'y_label': 'Frequency',
        }
    except Exception as e:
        return {'error': str(e)}


# ── Heatmap ───────────────────────────────────────────────────────────────────

def _heatmap(upload) -> dict:
    corr = (upload.analysis_result or {}).get('correlation')
    if not corr:
        return {'heatmap': True, 'columns': [], 'matrix': []}
    return {'heatmap': True, 'columns': corr['columns'], 'matrix': corr['matrix']}


# ── Preview fallback ──────────────────────────────────────────────────────────

def _from_preview(upload, chart) -> dict:
    from collections import defaultdict

    analysis = upload.analysis_result or {}
    x, y     = chart.x_axis, chart.y_axis
    ctype    = chart.chart_type
    agg      = chart.aggregation or 'mean'
    cjson    = chart.config_json or {}
    mult     = _multiplier(upload, y) if y else 1

    preview = analysis.get('preview', {})
    pcols   = preview.get('columns', [])
    prows   = preview.get('rows', [])

    if not pcols or not prows:
        return {'labels': [], 'datasets': []}
    # If y is same as x (text column), or y not in preview → use count mode
    use_count_mode = (not y) or (y == x) or (y and y not in pcols)
    if x not in pcols:
        return {'error': f'Column {x!r} not in preview'}

    xi = pcols.index(x)
    yi = pcols.index(y) if (y and y in pcols and y != x) else None

    groups: dict = defaultdict(list)
    for row in prows:
        try:
            k = str(row[xi]).strip()
            if yi is not None:
                v = _sf(str(row[yi]))
                if v is not None:
                    groups[k].append(v)
            else:
                # Count mode — just count occurrences of each x value
                groups[k].append(1)
        except (IndexError, TypeError):
            pass

    if not groups:
        return {'labels': [], 'datasets': []}

    def _agg(vals):
        fn = {'mean': lambda v: sum(v)/len(v), 'sum': sum, 'count': len,
              'min': min, 'max': max}.get(agg, lambda v: sum(v)/len(v))
        return fn(vals)

    raw_l = list(groups.keys())
    idxs  = _sort_cat(raw_l)
    items = [(raw_l[i], groups[raw_l[i]]) for i in idxs]

    if _stype(upload, x) not in ('year','month','time_cat','date') and ctype not in ('line','area'):
        items = sorted(items, key=lambda t: -_agg(t[1]))[:25]

    labels = [k for k, _ in items]
    vals   = [round(_agg(v) * mult, 4) for _, v in items]
    y_lbl  = cjson.get('y_label') or ('Count' if (not y or y == x or (y and y not in pcols)) else (f'{y} (%)' if _is_ratio(upload, y) else y))
    real   = 'bar' if ctype in ('horizontal_bar', 'variance_bar') else ('line' if ctype in ('area', 'rolling_line', 'cumulative_line') else ctype)

    if ctype in ('pie','doughnut'):
        bg = _palette(chart.color, 0.75, len(vals))
        bd = _palette(chart.color, 1.0,  len(vals))
    else:
        bg = _palette(chart.color, 0.75)[0]
        bd = _palette(chart.color, 1.0)[0]

    return {
        'labels': labels,
        'datasets': [{
            'label': y_lbl, 'data': vals,
            'backgroundColor': bg, 'borderColor': bd,
            'borderWidth': 2, 'tension': 0.4,
            'fill': ctype == 'area',
            'borderRadius': 4 if ctype in ('bar','horizontal_bar') else 0,
        }],
        'chart_type': real,
        'is_horizontal': ctype == 'horizontal_bar',
        'x_label': cjson.get('x_label', x),
        'y_label': y_lbl,
    }


# ── Auto-generation entry point ───────────────────────────────────────────────

def auto_generate_charts(upload) -> list:
    """Try AI first; fall back to intelligent rule-based generation."""
    from django.conf import settings

    if getattr(settings, 'ANTHROPIC_API_KEY', ''):
        try:
            from .ai_charts import ai_recommend_charts, apply_ai_recommendations
            configs = ai_recommend_charts(upload.analysis_result, upload.original_name)
            created = apply_ai_recommendations(upload, configs)
            if created:
                return created
        except Exception as e:
            import logging
            logging.getLogger(__name__).warning(f'AI chart gen failed: {e}')

    return _rule_based(upload)


def _rule_based(upload) -> list:
    """Semantic-aware rule-based chart generation."""
    from .models import ChartConfig

    upload.chart_configs.filter(is_auto=True).delete()

    analysis = upload.analysis_result or {}
    cols     = analysis.get('columns', [])
    sg       = analysis.get('semantic_groups', {})
    combos   = analysis.get('combined_dates', [])

    metrics    = sg.get('metric', []) + sg.get('currency', [])
    ratios     = sg.get('ratio', [])       # strict 0-1 decimals
    percentages= sg.get('percentage', [])  # 0-100 integer percentages
    all_pct    = ratios + percentages       # both shown as %
    counts  = sg.get('count', [])
    cats    = sg.get('category', [])
    ratios  = all_pct   # treat both ratio and percentage the same for chart generation
    years   = sg.get('year', [])
    months  = sg.get('month', []) + sg.get('time_cat', [])

    created = []
    order   = 0

    def _make(title, ctype, x='', y='', agg='mean', color='violet', size='md',
              group='', x_label='', y_label='', insight='', combo_key=''):
        nonlocal order
        extra = {'x_label': x_label or x, 'y_label': y_label or y,
                 'insight': insight, 'combined_date_key': combo_key}
        cfg = ChartConfig.objects.create(
            upload=upload, title=title, chart_type=ctype,
            x_axis=x, y_axis=y, aggregation=agg,
            color=color, size=size, group_by=group,
            sort_order=order, is_auto=True, config_json=extra,
        )
        order += 1
        try:
            cfg.cached_data = build_chart_data(upload, cfg)
            cfg.save(update_fields=['cached_data'])
        except Exception:
            pass
        created.append(cfg)

    KC = ['violet','blue','emerald','amber','rose','cyan']

    # KPIs — ratio cols (0-1) and percentage cols (0-100), both shown as %
    _orig_ratios   = sg.get('ratio', [])       # 0-1 decimals (e.g. 0.85)
    _orig_pcts     = sg.get('percentage', [])  # 0-100 integers (e.g. 85)
    _kpi_pct_cols  = _orig_ratios + _orig_pcts

    for i, col in enumerate(_kpi_pct_cols[:4]):
        ci   = next((c for c in cols if c['name'] == col), {})
        m    = ci.get('mean')
        stype= ci.get('semantic_type', '')
        if m is not None:
            display_avg = m * 100 if stype == 'ratio' else m   # ratio: ×100; pct: already %
            sfx = f" — avg {display_avg:.1f}%"
        else:
            sfx = ''
        _make(f"Avg {col.replace('_',' ').title()}{sfx}", 'kpi',
              y=col, agg='mean', color=KC[i % 6], size='sm',
              y_label=f'{col} (%)', insight=f"Average {col} across dataset")

    for i, col in enumerate(metrics[:2]):
        _make(f"Total {col.replace('_',' ').title()}", 'kpi',
              y=col, agg='sum', color=KC[(len(ratios)+i)%6], size='sm',
              insight=f"Sum of {col}")

    for col in counts[:1]:
        _make(f"Total {col.replace('_',' ').title()}", 'kpi',
              y=col, agg='sum', color='cyan', size='sm',
              insight=f"Total {col} across all records")

    # Time series using Month+Year combo
    for combo in combos[:1]:
        display = combo['display_name']
        for col in (ratios + metrics)[:2]:
            is_r = col in ratios
            _make(f"{col.replace('_',' ').title()} Trend Over Time",
                  'line', x=display, y=col,
                  agg='mean' if is_r else 'sum',
                  color='blue', size='full',
                  x_label='Period',
                  y_label=f'{col} (%)' if is_r else col,
                  insight=f"Monthly {col} trend — spot seasonality and growth",
                  combo_key=display)

    # Year-only trend
    if years and not combos:
        for col in (ratios + metrics)[:2]:
            is_r = col in ratios
            _make(f"{col.replace('_',' ').title()} by Year", 'bar',
                  x=years[0], y=col,
                  agg='mean' if is_r else 'sum',
                  color='blue', size='lg',
                  y_label=f'{col} (%)' if is_r else col,
                  insight=f"Year-on-year {col} trend")

    # Month pattern
    if months and not combos:
        for col in (ratios + metrics)[:1]:
            is_r = col in ratios
            _make(f"{col.replace('_',' ').title()} by Month", 'bar',
                  x=months[0], y=col,
                  agg='mean' if is_r else 'sum',
                  color='violet', size='lg',
                  y_label=f'{col} (%)' if is_r else col,
                  insight=f"Seasonal pattern — which months perform best")

    # Category breakdowns — skip high_card columns (too many unique values for charts)
    target_val = (ratios + metrics)[:1]
    # Filter to sensible cardinality: 2-30 unique values
    usable_cats = []
    for cat in cats:
        ci = next((c for c in cols if c['name'] == cat), {})
        uniq = ci.get('unique_count', 99)
        st   = ci.get('semantic_type','')
        if st != 'high_card' and 2 <= uniq <= 30:
            usable_cats.append(cat)
        elif st != 'high_card' and uniq > 30:
            # High cardinality — only use for horizontal_bar (top N)
            pass
    for i, cat in enumerate(usable_cats[:5]):
        if not target_val:
            continue
        col   = target_val[0]
        is_r  = col in ratios
        agg_f = 'mean' if is_r else 'sum'
        lbl   = f'{col} (%)' if is_r else col
        cinfo = next((c for c in cols if c['name'] == cat), {})
        uniq  = cinfo.get('unique_count', 99)

        if uniq > 12:
            _make(f"Top {cat.replace('_',' ').title()} by {col.replace('_',' ').title()}",
                  'horizontal_bar', x=cat, y=col, agg=agg_f,
                  color='emerald', size='lg',
                  y_label=cat, x_label=lbl,
                  insight=f"Ranking {cat} by {col} — identify top performers")
        elif 2 <= uniq <= 7:
            _make(f"{col.replace('_',' ').title()} Share by {cat.replace('_',' ').title()}",
                  'doughnut', x=cat, y=col, agg=agg_f,
                  color='multi', size='md',
                  insight=f"Proportional {col} contribution by {cat}")
        else:
            _make(f"{col.replace('_',' ').title()} by {cat.replace('_',' ').title()}",
                  'horizontal_bar', x=cat, y=col, agg=agg_f,
                  color='violet', size='lg',
                  y_label=cat, x_label=lbl,
                  insight=f"{col} performance across each {cat}")

    # High-cardinality categories: horizontal_bar top 20 only
    high_card_cols = sg.get('high_card', [])
    for cat in high_card_cols[:2]:
        if not target_val: continue
        col  = target_val[0]
        is_r = col in ratios
        _make(
            title=f"Top {cat.replace('_',' ').title()} by {col.replace('_',' ').title()}",
            ctype='horizontal_bar', x=cat, y=col,
            agg='mean' if is_r else 'sum',
            color='emerald', size='full',
            y_label=cat, x_label=f'{col} (%)' if is_r else col,
            insight=f"Top 20 {cat} ranked by {col} — identify best performers",
        )

    # Scatter: ratio vs ratio or metric vs metric
    pair = ratios if len(ratios) >= 2 else (metrics if len(metrics) >= 2 else [])
    if len(pair) >= 2:
        is_r = pair[0] in ratios
        _make(f"{pair[0].replace('_',' ').title()} vs {pair[1].replace('_',' ').title()}",
              'scatter', x=pair[0], y=pair[1], agg='mean',
              color='rose', size='md',
              x_label=f'{pair[0]} (%)' if is_r else pair[0],
              y_label=f'{pair[1]} (%)' if is_r else pair[1],
              insight=f"Relationship between {pair[0]} and {pair[1]}")

    # Heatmap
    corr = analysis.get('correlation')
    if corr and len(corr.get('columns', [])) >= 3:
        _make('Metric Correlation Heatmap', 'heatmap',
              color='violet', size='full',
              insight="Which metrics move together — discover key drivers")

    # Histograms
    for col in (metrics + counts)[:2]:
        ci = next((c for c in cols if c['name'] == col), {})
        if ci.get('histogram'):
            _make(f"{col.replace('_',' ').title()} Distribution",
                  'histogram', x=col, y=col, agg='count',
                  color='amber', size='md',
                  y_label='Frequency',
                  insight=f"How {col} values are distributed")

    # Target-aware upgrades
    target_col = next((c['name'] for c in cols if 'target' in c['name'].lower() or 'budget' in c['name'].lower()), '')
    actual_col = next((c['name'] for c in cols if c['semantic_type'] in ('metric', 'currency') and c['name'] != target_col), '')
    base_dim = usable_cats[0] if usable_cats else (years[0] if years else (months[0] if months else ''))
    if target_col and actual_col:
        _make(f"Total {actual_col.replace('_',' ').title()} vs {target_col.replace('_',' ').title()}",
              'kpi', y=actual_col, agg='sum', color='emerald', size='sm',
              insight=f"Headline actual vs target check for {actual_col}")
        created[-1].config_json['target_column'] = target_col
        created[-1].cached_data = build_chart_data(upload, created[-1])
        created[-1].save(update_fields=['config_json', 'cached_data'])

        if base_dim:
            _make(f"Variance by {base_dim.replace('_',' ').title()}",
                  'variance_bar', x=base_dim, y=actual_col, agg='sum',
                  color='rose', size='lg', y_label='Variance',
                  insight=f"Actual minus target by {base_dim}")
            created[-1].config_json['target_column'] = target_col
            created[-1].cached_data = build_chart_data(upload, created[-1])
            created[-1].save(update_fields=['config_json', 'cached_data'])

    # Pareto and rolling upgrades
    if usable_cats and metrics:
        _make(f"Pareto of {metrics[0].replace('_',' ').title()} by {usable_cats[0].replace('_',' ').title()}",
              'pareto', x=usable_cats[0], y=metrics[0], agg='sum',
              color='violet', size='full',
              insight=f"Top contributors and cumulative share of {metrics[0]}")

    for combo in combos[:1]:
        display = combo['display_name']
        if metrics:
            _make(f"Rolling {metrics[0].replace('_',' ').title()} Trend",
                  'rolling_line', x=display, y=metrics[0], agg='sum',
                  color='cyan', size='full', x_label='Period', y_label=metrics[0],
                  insight=f"Smoothed trend for {metrics[0]}", combo_key=display)
            _make(f"Cumulative {metrics[0].replace('_',' ').title()}",
                  'cumulative_line', x=display, y=metrics[0], agg='sum',
                  color='emerald', size='full', x_label='Period', y_label=metrics[0],
                  insight=f"Running total for {metrics[0]}", combo_key=display)

    return created


# --- Enhanced auto-generation helpers ---
def _col_meta_map(upload):
    return {c['name']: c for c in (upload.analysis_result or {}).get('columns', []) if isinstance(c, dict) and c.get('name')}


def _preferred_metrics(upload):
    meta = _col_meta_map(upload)
    guidance = ((upload.analysis_result or {}).get('user_guidance') or {})
    preferred_primary = guidance.get('primary_measure') or ''
    preferred_target = guidance.get('target_column') or ''
    metrics = []
    priority_terms = ('sales','revenue','actual','amount','value','profit','target','budget','forecast','variance','achievement')
    for name, info in meta.items():
        if info.get('semantic_type') in {'metric','currency','count','ratio','percentage'}:
            score = 0
            low = name.lower()
            for i, term in enumerate(priority_terms[::-1]):
                if term in low:
                    score += 10 + i
            if info.get('semantic_type') in {'currency','metric'}:
                score += 5
            if preferred_primary and name == preferred_primary:
                score += 1000
            if preferred_target and name == preferred_target:
                score += 500
            metrics.append((score, name))
    metrics.sort(reverse=True)
    return [name for _score, name in metrics] or list(meta.keys())


def _preferred_dimensions(upload):
    meta = _col_meta_map(upload)
    guidance = ((upload.analysis_result or {}).get('user_guidance') or {})
    preferred_time = guidance.get('time_column') or ''
    preferred_dim = guidance.get('primary_dimension') or ''
    dims = []
    priority_terms = ('period','date','month','year','quarter','branch','region','category','product','segment','department')
    for name, info in meta.items():
        st = info.get('semantic_type')
        if st in {'category','date','year','month','time_cat'}:
            uniq = info.get('unique_count') or 999
            low = name.lower()
            score = 0
            for i, term in enumerate(priority_terms[::-1]):
                if term in low:
                    score += 10 + i
            if st in {'date','year','month','time_cat'}:
                score += 20
            if 2 <= uniq <= 36:
                score += 8
            elif uniq <= 80:
                score += 4
            if preferred_time and name == preferred_time:
                score += 1000
            if preferred_dim and name == preferred_dim:
                score += 700
            dims.append((score, name))
    dims.sort(reverse=True)
    return [name for _score, name in dims]


def _rule_based(upload) -> list:
    """
    Profile-driven chart generation.
    Prioritises the pre-computed heuristic_chart_plan from the screening profile,
    then falls back to the legacy rule-based logic for any gaps.
    Derived metrics (achievement_pct, variance_to_target, stock_turnover, etc.)
    are fully supported — they are added to the dataframe via add_derived_metrics()
    before each chart is rendered.
    """
    from .models import ChartConfig

    upload.chart_configs.filter(is_auto=True).delete()
    analysis = upload.analysis_result or {}
    cols = analysis.get('columns', [])

    # ── Pull the rich profile from screening ─────────────────────────────────
    profile_json    = analysis.get('profile_json') or {}
    screening_json  = analysis.get('screening_json') or {}

    # Fallback: try the UploadAnalysisProfile db row if not in analysis_result
    if not profile_json or not screening_json:
        try:
            sp = getattr(upload, 'screening_profile', None)
            if sp is None:
                from .models import UploadAnalysisProfile
                sp = UploadAnalysisProfile.objects.filter(upload=upload).first()
            if sp:
                profile_json   = profile_json   or sp.profile_json   or {}
                screening_json = screening_json or sp.screening_json or {}
        except Exception:
            pass

    heuristic_plan  = screening_json.get('heuristic_chart_plan') or []
    business_roles  = profile_json.get('business_roles') or {}
    derived_meta    = (profile_json.get('derived_metrics') or {})
    available_dm    = derived_meta.get('available') or []
    dm_labels       = derived_meta.get('labels')    or {}
    business_ins    = profile_json.get('business_insights') or {}

    # Canonical role columns from profile
    role_target      = business_roles.get('target_column')    or screening_json.get('recommended_target_column') or ''
    role_actual      = business_roles.get('actual_column')    or screening_json.get('recommended_main_measure')  or ''
    role_dim         = business_roles.get('primary_dimension') or ''
    role_purchasing  = business_roles.get('purchasing_column') or ''
    role_open_stock  = business_roles.get('opening_stock_column') or ''
    role_close_stock = business_roles.get('closing_stock_column') or ''

    created  = []
    order    = 0
    signatures = set()
    skip_reasons = []

    def _save_payload(cfg):
        try:
            cfg.cached_data = build_chart_data(upload, cfg)
            cfg.save(update_fields=['cached_data'])
            return True
        except Exception as exc:
            skip_reasons.append(f"{cfg.title}: {exc}")
            return False

    def _make(title, ctype, x='', y='', agg='sum', color='violet', size='md',
              group='', x_label='', y_label='', insight='', combo_key='', extra=None):
        nonlocal order
        signature = (ctype, x or combo_key, y, agg, group)
        if signature in signatures:
            return None
        signatures.add(signature)
        extra_cfg = {
            'x_label': x_label or x or combo_key,
            'y_label': y_label or y,
            'insight': insight,
            'combined_date_key': combo_key,
            'show_annotations': True,
            'top_n': 10,
            'rolling_window': 3,
        }
        if extra:
            extra_cfg.update(extra)
        cfg = ChartConfig.objects.create(
            upload=upload, title=title, chart_type=ctype, x_axis=x, y_axis=y,
            group_by=group, aggregation=agg, color=color, size=size,
            sort_order=order, is_auto=True, config_json=extra_cfg
        )
        order += 1
        _save_payload(cfg)
        created.append(cfg)
        return cfg

    # ════════════════════════════════════════════════════════════════════
    # PASS 1: Execute the heuristic_chart_plan from the screening profile
    # This uses all pre-profiled knowledge: derived metrics, roles, archetypes
    # ════════════════════════════════════════════════════════════════════
    VALID_CHART_TYPES = {
        'kpi', 'bar', 'horizontal_bar', 'line', 'area', 'scatter',
        'pie', 'doughnut', 'histogram', 'heatmap', 'variance_bar',
        'bullet', 'progress_ring', 'waterfall', 'pareto',
        'rolling_line', 'cumulative_line',
    }
    COLOR_MAP = {
        'violet': 'violet', 'blue': 'blue', 'emerald': 'emerald',
        'amber': 'amber', 'rose': 'rose', 'cyan': 'cyan', 'multi': 'multi',
    }
    SIZE_MAP = {'sm': 'sm', 'md': 'md', 'lg': 'lg', 'full': 'full'}

    # ── Label cleaning helpers ────────────────────────────────────────────
    def _clean_title(t, ctype):
        """Remove trailing 'KPI', 'Headline KPI', 'Headline' suffixes from chart titles."""
        import re as _re
        t = (t or '').strip()
        if ctype == 'kpi':
            t = _re.sub(r'\s+(Headline\s+)?KPI\s*$', '', t, flags=_re.IGNORECASE).strip()
            t = _re.sub(r'\s+Headline\s*$', '', t, flags=_re.IGNORECASE).strip()
        return t or t

    def _clean_ylabel(lbl, ctype, dm_key, dm_labels_map):
        """Return a clean, audience-facing y-axis label."""
        # If we have a dm_labels entry, always use that
        if dm_key and dm_key in dm_labels_map:
            return dm_labels_map[dm_key]
        lbl = (lbl or '').strip()
        if ctype == 'kpi':
            import re as _re
            lbl = _re.sub(r'\s+(Headline\s+)?KPI\s*$', '', lbl, flags=_re.IGNORECASE).strip()
        return lbl

    for plan_item in heuristic_plan:
        if not plan_item.get('visible', True):
            continue
        ctype   = plan_item.get('chart_type', '')
        if ctype not in VALID_CHART_TYPES:
            continue
        raw_title = plan_item.get('title', '')
        title   = _clean_title(raw_title, ctype)
        x_axis  = plan_item.get('x_axis', '') or ''
        y_axis  = plan_item.get('y_axis', '') or ''
        agg     = plan_item.get('aggregation', 'sum') or 'sum'
        group   = plan_item.get('group_by', '') or ''
        color   = COLOR_MAP.get(plan_item.get('color', 'violet'), 'violet')
        size    = SIZE_MAP.get(plan_item.get('size', 'md'), 'md')
        x_label = plan_item.get('x_label', '') or ''
        raw_ylabel = plan_item.get('y_label', '') or ''
        insight = plan_item.get('insight', '') or ''
        target_col = plan_item.get('target_column', '') or ''
        dm_key  = plan_item.get('derived_metric_key', '') or ''
        extra_measures = plan_item.get('extra_measures', []) or []

        # For derived metric columns use dm_key as y_axis so add_derived_metrics() provides it
        effective_y = dm_key if dm_key and dm_key in available_dm else y_axis

        # Clean the y_label — remove "KPI" suffix noise, prefer dm_labels
        y_label = _clean_ylabel(raw_ylabel, ctype, dm_key, dm_labels)

        # For achievement_pct in time-series: mark as already-scaled (0-100)
        # The derived_metrics rewrite stores it as 0-100, not 0-1
        extra = {'insight': insight}
        if target_col:
            extra['target_column'] = target_col
        if x_label:
            extra['x_label'] = x_label
        if y_label:
            extra['y_label'] = y_label
        if extra_measures:
            extra['extra_measures'] = extra_measures
        if dm_key:
            extra['derived_metric_key'] = dm_key
            # Always use the canonical dm_label
            extra['y_label'] = dm_labels.get(dm_key, y_label) or y_label

        cfg = _make(
            title, ctype,
            x=x_axis, y=effective_y, agg=agg, color=color, size=size,
            group=group, x_label=x_label, y_label=y_label, insight=insight,
            extra=extra,
        )
        if cfg and target_col:
            cfg.config_json['target_column'] = target_col
            _save_payload(cfg)
            cfg.save(update_fields=['config_json', 'cached_data'])

    # ════════════════════════════════════════════════════════════════════
    # PASS 2: Profile-driven supplemental charts using derived metrics
    # These add coverage for derived metrics not in heuristic_plan
    # ════════════════════════════════════════════════════════════════════
    dim = role_dim
    _dim_label = dim.replace('_', ' ').title() if dim else 'Segment'
    if dim:
        # Achievement % ranked bar — most critical view for target_vs_actual
        if 'achievement_pct' in available_dm:
            _make(
                f'Achievement % by {_dim_label}', 'horizontal_bar',
                x=dim, y='achievement_pct', agg='mean',
                color='emerald', size='lg',
                x_label=dm_labels.get('achievement_pct', 'Achievement %'),
                y_label=dim,
                insight=f'Best-to-worst attainment ranking across {_dim_label.lower()} segments',
                extra={
                    'derived_metric_key': 'achievement_pct',
                    'y_label': dm_labels.get('achievement_pct', 'Achievement %'),
                    'target_column': role_target,
                    'reference_line': 100,
                }
            )

        # Variance to target bar
        if 'variance_to_target' in available_dm and role_actual and role_target:
            cfg = _make(
                f'Variance to Target by {_dim_label}', 'variance_bar',
                x=dim, y=role_actual, agg='sum',
                color='rose', size='full',
                x_label=dim, y_label=role_actual,
                insight=f'{_dim_label} segments above and below target — identify recovery priorities',
                extra={'target_column': role_target}
            )
            if cfg:
                cfg.config_json['target_column'] = role_target
                _save_payload(cfg)
                cfg.save(update_fields=['config_json', 'cached_data'])

        # Stock turnover ranking
        if 'stock_turnover' in available_dm:
            _make(
                f'Stock Turnover by {_dim_label}', 'horizontal_bar',
                x=dim, y='stock_turnover', agg='mean',
                color='amber', size='lg',
                x_label=dm_labels.get('stock_turnover', 'Stock Turnover'),
                y_label=dim,
                insight=f'{_dim_label} segments with lowest turnover are at risk of slow-moving stock',
                extra={'derived_metric_key': 'stock_turnover'}
            )

        # Profit Margin % ranking — key profitability view
        if 'profit_margin_pct' in available_dm:
            _make(
                f'Profit Margin % by {_dim_label}', 'horizontal_bar',
                x=dim, y='profit_margin_pct', agg='mean',
                color='emerald', size='lg',
                x_label=dm_labels.get('profit_margin_pct', 'Profit Margin %'),
                y_label=dim,
                insight=f'Which {_dim_label.lower()} segments are most profitable',
                extra={'derived_metric_key': 'profit_margin_pct'}
            )

        # Cost efficiency (actual vs purchasing ratio)
        if 'actual_to_cost_ratio' in available_dm and role_purchasing:
            _make(
                f'Cost Efficiency by {_dim_label}', 'horizontal_bar',
                x=dim, y='actual_to_cost_ratio', agg='mean',
                color='cyan', size='lg',
                x_label=dm_labels.get('actual_to_cost_ratio', 'Revenue / Purchasing'),
                y_label=dim,
                insight=f'Revenue generated per unit of purchasing spend across {_dim_label.lower()} segments',
                extra={'derived_metric_key': 'actual_to_cost_ratio'}
            )

        # Stock movement (closing - opening)
        if 'stock_movement' in available_dm and role_open_stock and role_close_stock:
            _make(
                f'Stock Movement by {_dim_label}', 'bar',
                x=dim, y='stock_movement', agg='sum',
                color='blue', size='lg',
                x_label=dim,
                y_label=dm_labels.get('stock_movement', 'Stock Movement'),
                insight=f'Net stock change per {_dim_label.lower()} — positive means stock built up',
                extra={'derived_metric_key': 'stock_movement'}
            )

        # Opening vs Closing stock comparison
        if role_open_stock and role_close_stock:
            _make(
                f'Opening vs Closing Stock by {_dim_label}', 'bar',
                x=dim, y=role_open_stock, agg='sum',
                color='multi', size='full',
                x_label=dim, y_label='Stock Value',
                insight=f'Side-by-side stock position per {_dim_label.lower()}',
                extra={'extra_measures': [role_close_stock]}
            )

        # Contribution donut — title reflects the actual measure and dimension
        if role_actual:
            _actual_label = role_actual.replace('_', ' ').title()
            _dim_label = dim.replace('_', ' ').title()
            _make(
                f'{_actual_label} by {_dim_label}',
                'doughnut',
                x=dim, y=role_actual, agg='sum',
                color='multi', size='md',
                x_label=dim, y_label=role_actual,
                insight=f'Share of total {_actual_label.lower()} per {_dim_label.lower()}'
            )

    # KPI cards from business_insights kpi_summary
    kpi_summary = business_ins.get('kpi_summary') or {}
    if role_actual:
        _actual_label = role_actual.replace('_', ' ').title()
        _make(f'Total {_actual_label}', 'kpi', y=role_actual, agg='sum',
              color='violet', size='sm',
              insight=f'Total {_actual_label.lower()}: {kpi_summary.get("total_primary_measure", "")}',
              extra={'target_column': role_target} if role_target else None)
    if role_target:
        _target_label = role_target.replace('_', ' ').title()
        _make(f'Total {_target_label}', 'kpi', y=role_target, agg='sum',
              color='blue', size='sm',
              insight=f'Total target: {kpi_summary.get("total_target", "")}')
    if 'achievement_pct' in available_dm:
        _make('Achievement %', 'kpi', y='achievement_pct', agg='mean',
              color='emerald', size='sm',
              insight=f'Avg attainment {kpi_summary.get("best_achievement_pct", "")}% best, {kpi_summary.get("worst_achievement_pct", "")}% worst',
              extra={'derived_metric_key': 'achievement_pct'})
    if 'profit_margin_pct' in available_dm:
        _make('Profit Margin %', 'kpi', y='profit_margin_pct', agg='mean',
              color='emerald', size='sm',
              insight='Average profit margin across all records',
              extra={'derived_metric_key': 'profit_margin_pct'})
    if 'variance_to_target' in available_dm:
        _make('Variance to Target', 'kpi', y='variance_to_target', agg='sum',
              color='rose', size='sm',
              insight='Total gap between achievement and target',
              extra={'derived_metric_key': 'variance_to_target'})

    # ════════════════════════════════════════════════════════════════════
    # PASS 3: Legacy fallback for any remaining standard charts
    # Only runs if profile-driven passes produced fewer than 8 charts
    # ════════════════════════════════════════════════════════════════════
    if len(created) >= 8:
        return created

    # Legacy from here — use remaining columns from analysis
    # NOTE: we continue appending to existing created/order/signatures
    guidance = (analysis.get('user_guidance') or {})
    goals = guidance.get('primary_goals') or []
    combos = analysis.get('combined_dates', [])
    # Do NOT reset created/order/signatures — append to profile-driven charts

    metric_names = _preferred_metrics(upload)
    dimension_names = _preferred_dimensions(upload)
    ratio_cols = [c['name'] for c in cols if c.get('semantic_type') in {'ratio', 'percentage'}]
    numericish = [c['name'] for c in cols if c.get('semantic_type') in {'metric', 'currency', 'count', 'ratio', 'percentage'}]

    target_terms = ('target', 'budget', 'plan', 'forecast', 'goal')
    actual_terms = ('sales', 'revenue', 'actual', 'amount', 'value', 'profit', 'income', 'cost', 'expense', 'qty', 'quantity', 'units')

    target_col = next((m for m in metric_names if any(k in m.lower() for k in target_terms)), '')
    actual_candidates = [m for m in metric_names if m != target_col]
    actual_col = next((m for m in actual_candidates if any(k in m.lower() for k in actual_terms)), actual_candidates[0] if actual_candidates else '')

    time_dims = []
    if combos:
        for combo in combos:
            display = combo.get('display_name') or combo.get('name')
            if display:
                time_dims.append(('combo', display))
    for name in dimension_names:
        low = name.lower()
        if any(k in low for k in ('date', 'period', 'month', 'year', 'quarter')):
            time_dims.append(('field', name))
    # de-duplicate while preserving order
    seen_td = set()
    uniq_time_dims = []
    for kind, name in time_dims:
        key = (kind, name)
        if key not in seen_td:
            seen_td.add(key)
            uniq_time_dims.append((kind, name))
    time_dims = uniq_time_dims

    non_time_dims = []
    for name in dimension_names:
        low = name.lower()
        if not any(k in low for k in ('date', 'period', 'month', 'year', 'quarter')):
            non_time_dims.append(name)
    if not non_time_dims:
        non_time_dims = [name for name in dimension_names[:3]]

    def _save_payload(cfg):
        try:
            cfg.cached_data = build_chart_data(upload, cfg)
            cfg.save(update_fields=['cached_data'])
            return True
        except Exception as exc:
            skip_reasons.append(f"{cfg.title}: {exc}")
            return False

    def _make(title, ctype, x='', y='', agg='sum', color='violet', size='md', group='', x_label='', y_label='', insight='', combo_key='', extra=None):
        nonlocal order
        signature = (ctype, x or combo_key, y, agg, group)
        if signature in signatures:
            return None
        signatures.add(signature)
        extra_cfg = {
            'x_label': x_label or x or combo_key,
            'y_label': y_label or y,
            'insight': insight,
            'combined_date_key': combo_key,
            'show_annotations': True,
            'top_n': 10,
            'rolling_window': 3,
        }
        if extra:
            extra_cfg.update(extra)
        cfg = ChartConfig.objects.create(
            upload=upload, title=title, chart_type=ctype, x_axis=x, y_axis=y, group_by=group,
            aggregation=agg, color=color, size=size, sort_order=order, is_auto=True, config_json=extra_cfg
        )
        order += 1
        _save_payload(cfg)
        created.append(cfg)
        return cfg

    # --- KPI layer ---
    for idx, col in enumerate(ratio_cols[:2]):
        _make(
            f'Average {col.replace("_", " ").title()}', 'kpi', y=col, agg='mean',
            color=['violet', 'blue'][idx % 2], size='sm',
            insight=f'Average {col} across the filtered dataset'
        )

    for idx, col in enumerate([c for c in [actual_col, target_col] if c][:2]):
        _make(
            f'Total {col.replace("_", " ").title()}', 'kpi', y=col, agg='sum',
            color=['emerald', 'amber'][idx % 2], size='sm',
            insight=f'Total {col} across all visible rows'
        )

    # --- Trend layer ---
    trend_metrics = [m for m in [actual_col, target_col] + metric_names if m][:3]
    for kind, dim in time_dims[:2]:
        for idx, metric in enumerate(trend_metrics[:2]):
            combo_key = dim if kind == 'combo' else ''
            x = dim
            _make(
                f'{metric.replace("_", " ").title()} Trend', 'line', x=x, y=metric, agg='sum',
                color=['blue', 'emerald', 'violet'][idx % 3], size='full', x_label='Period', y_label=metric,
                insight=f'Time trend of {metric}', combo_key=combo_key, extra={'target_column': target_col} if metric == actual_col and target_col else None
            )
        if actual_col:
            combo_key = dim if kind == 'combo' else ''
            x = dim
            _make(
                f'Rolling {actual_col.replace("_", " ").title()} Trend', 'rolling_line', x=x, y=actual_col, agg='sum',
                color='cyan', size='full', x_label='Period', y_label=actual_col,
                insight=f'Smoothed rolling trend of {actual_col}', combo_key=combo_key
            )
            _make(
                f'Cumulative {actual_col.replace("_", " ").title()}', 'cumulative_line', x=x, y=actual_col, agg='sum',
                color='emerald', size='full', x_label='Period', y_label=actual_col,
                insight=f'Cumulative running total of {actual_col}', combo_key=combo_key
            )

    # --- Ranking and composition ---
    rank_metrics = [m for m in [actual_col, target_col] + metric_names if m][:3]
    for dim in non_time_dims[:3]:
        for idx, metric in enumerate(rank_metrics[:2]):
            _make(
                f'{metric.replace("_", " ").title()} by {dim.replace("_", " ").title()}',
                'horizontal_bar', x=dim, y=metric, agg='sum', color=['violet', 'blue', 'emerald'][idx % 3], size='lg',
                insight=f'Ranking {dim} by {metric}', extra={'top_n': 15, 'target_column': target_col} if metric == actual_col and target_col else {'top_n': 15}
            )
        if actual_col:
            _make(
                f'Pareto of {actual_col.replace("_", " ").title()} by {dim.replace("_", " ").title()}',
                'pareto', x=dim, y=actual_col, agg='sum', color='amber', size='full',
                insight=f'Cumulative contribution of {actual_col} by {dim}', extra={'top_n': 15}
            )
        # low-card composition
        cmeta = next((c for c in cols if c.get('name') == dim), {})
        uniq = int(cmeta.get('unique_count') or 0)
        if actual_col and 2 <= uniq <= 8:
            _make(
                f'{actual_col.replace("_", " ").title()} Share by {dim.replace("_", " ").title()}',
                'doughnut', x=dim, y=actual_col, agg='sum', color='multi', size='md',
                insight=f'Contribution share of {actual_col} by {dim}'
            )

    # --- Comparison layer ---
    base_dim = non_time_dims[0] if non_time_dims else (dimension_names[0] if dimension_names else '')
    if actual_col and target_col:
        cfg = _make(
            f'Variance by {base_dim.replace("_", " ").title()}', 'variance_bar', x=base_dim, y=actual_col,
            agg='sum', color='rose', size='lg', insight=f'Actual versus target variance by {base_dim}'
        )
        if cfg:
            cfg.config_json['target_column'] = target_col
            _save_payload(cfg)
            cfg.save(update_fields=['config_json', 'cached_data'])

        cfg2 = _make(
            f'{actual_col.replace("_", " ").title()} vs {target_col.replace("_", " ").title()}',
            'bullet', x=base_dim, y=actual_col, agg='sum', color='blue', size='md',
            insight=f'Performance against target by {base_dim}'
        )
        if cfg2:
            cfg2.config_json['target_column'] = target_col
            _save_payload(cfg2)
            cfg2.save(update_fields=['config_json', 'cached_data'])

        cfg3 = _make(
            f'{actual_col.replace("_", " ").title()} Achievement', 'progress_ring', x=base_dim, y=actual_col,
            agg='sum', color='emerald', size='sm', insight=f'Overall achievement versus target for {actual_col}'
        )
        if cfg3:
            cfg3.config_json['target_column'] = target_col
            _save_payload(cfg3)
            cfg3.save(update_fields=['config_json', 'cached_data'])

    # --- Distribution & relationship ---
    dist_metrics = [m for m in [actual_col] + metric_names if m][:3]
    for metric in dist_metrics[:2]:
        _make(
            f'{metric.replace("_", " ").title()} Distribution', 'histogram', x=metric, y=metric, agg='count',
            color='amber', size='md', insight=f'How {metric} values are distributed'
        )

    scatter_candidates = [m for m in numericish if m not in {target_col}][:4]
    if len(scatter_candidates) >= 2:
        _make(
            f'{scatter_candidates[0].replace("_", " ").title()} vs {scatter_candidates[1].replace("_", " ").title()}',
            'scatter', x=scatter_candidates[0], y=scatter_candidates[1], agg='mean',
            color='rose', size='md', insight=f'Relationship between {scatter_candidates[0]} and {scatter_candidates[1]}'
        )

    corr = analysis.get('correlation')
    if corr and len(corr.get('columns', [])) >= 3:
        _make('Metric Correlation Heatmap', 'heatmap', color='violet', size='full', insight='Which metrics move together')

    # --- Fallback expansion: ensure a fuller chart set when data is usable ---
    min_target = 12 if 'Full analytical dashboard' in (guidance.get('output_mode') or '') else 8
    if len(created) < min_target:
        fallback_dims = non_time_dims + [d for d in dimension_names if d not in non_time_dims]
        fallback_metrics = metric_names + ratio_cols
        for dim in fallback_dims[:4]:
            for metric in fallback_metrics[:4]:
                if len(created) >= min_target:
                    break
                if not dim or not metric:
                    continue
                title = f'{metric.replace("_", " ").title()} by {dim.replace("_", " ").title()}'
                _make(title, 'bar', x=dim, y=metric, agg='mean' if metric in ratio_cols else 'sum', color='cyan', size='md', insight=f'Fallback analysis of {metric} by {dim}')
            if len(created) >= min_target:
                break

    # Persist some generation diagnostics to help future debugging
    analysis['auto_generation_debug'] = {
        'metrics': metric_names[:6],
        'dimensions': dimension_names[:6],
        'time_dimensions': [name for _kind, name in time_dims[:4]],
        'generated_count': len(created),
        'skip_reasons': skip_reasons[:12],
    }
    upload.analysis_result = analysis
    try:
        upload.save(update_fields=['analysis_result'])
    except Exception:
        pass

    return created
