"""
Nexyza Intelligence Layer — v3
Deeply understands column semantics before any chart is created.

Responsibilities:
1. Semantic type detection (year, month, date, category, metric, id, ratio, percentage)
2. Date column combination (Month + Year → unified time series)
3. Smart numeric coercion (numbers stored as strings)
4. Dataset-level insight generation (relationships, patterns, anomalies)
5. Informed chart specification with meaningful titles & axis labels

Column semantic types
---------------------
  'year'        — numeric 1900–2100, likely represents a calendar year
  'month'       — numeric 1–12 or string month names
  'date'        — datetime parseable column
  'time_cat'    — ordered temporal category (Jan, Feb… or Q1, Q2…)
  'metric'      — core numeric KPI / measure
  'ratio'       — numeric between 0–1 (rates, achievement %)
  'percentage'  — numeric 0–100 (store as ratio internally)
  'count'       — non-negative integer, likely a count
  'currency'    — large positive numeric (revenue, cost, price)
  'category'    — low-cardinality string (<= 20 unique)
  'high_card'   — high-cardinality string (names, IDs)
  'id'          — unique-ish identifier
  'text'        — free-form text
  'boolean'     — binary values
"""

import re
import math
import statistics
from typing import Optional
import pandas as pd
import numpy as np


# ── Month name maps ───────────────────────────────────────────────────────────
MONTH_NAMES = {
    'jan':1,'feb':2,'mar':3,'apr':4,'may':5,'jun':6,
    'jul':7,'aug':8,'sep':9,'oct':10,'nov':11,'dec':12,
    'january':1,'february':2,'march':3,'april':4,'june':6,
    'july':7,'august':8,'september':9,'october':10,'november':11,'december':12,
}
MONTH_ORDER = ['January','February','March','April','May','June',
               'July','August','September','October','November','December',
               'Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec']
QUARTER_ORDER = ['Q1','Q2','Q3','Q4']


def _safe_float(v) -> Optional[float]:
    try:
        f = float(str(v).replace(',','').strip())
        return None if (math.isnan(f) or math.isinf(f)) else f
    except (ValueError, TypeError):
        return None


# ── Semantic type detection ───────────────────────────────────────────────────



# ── Aggressive numeric coercion ───────────────────────────────────────────────

def force_numeric(series: pd.Series) -> pd.Series:
    """
    Coerce ANY series to numeric regardless of formatting.
    Handles: "85%", "LKR 250,000", "$1,200", "Rs.500", "1.2k", "2.5M", plain ints/floats.
    Returns a float64 Series with NaN for unparseable values.
    """
    import re as _re

    # Already numeric — fast path
    if pd.api.types.is_numeric_dtype(series):
        return series.astype(float)

    s = series.astype(str).str.strip()

    # Currency prefixes / suffixes (order: multi-char before single-char)
    s = s.str.replace(
        r'(?i)^(lkr|rs\.?|usd|inr|aud|cad|gbp|eur|jpy)\s*', '', regex=True)
    s = s.str.replace(
        r'(?i)\s*(lkr|rs\.?|usd|inr|aud|cad|gbp|eur|jpy)$', '', regex=True)
    s = s.str.replace(r'(?i)^(\$|€|£|¥|₹)\s*', '', regex=True)  # symbol prefixes
    s = s.str.replace(r'%$', '', regex=True)         # trailing %
    s = s.str.replace(r',', '', regex=True)           # thousands separators
    s = s.str.replace(r'\s+', '', regex=True)         # whitespace

    # k/m/b/t suffixes  (1.2k → 1200, 3.5M → 3_500_000)
    def _expand(v: str) -> str:
        m = _re.match(r'^([+-]?\d+(?:\.\d+)?)\s*([kmbt])$', v.lower())
        if m:
            mult = {'k': 1e3, 'm': 1e6, 'b': 1e9, 't': 1e12}[m.group(2)]
            return str(float(m.group(1)) * mult)
        return v

    s = s.map(_expand)
    return pd.to_numeric(s, errors='coerce')


def detect_semantic_type(series: pd.Series, col_name: str) -> str:
    """Classify a column into a semantic type."""
    name_lower = col_name.lower().strip()
    clean      = series.dropna()
    n          = len(clean)
    if n == 0:
        return 'text'

    # ── Name-based hints ──────────────────────────────────────────────────────
    year_hints  = ('year','yr','fy','financial year','fiscal year')
    month_hints = ('month','mon','mth')
    date_hints  = ('date','day','time','period','as at','as of','when')
    id_hints    = ('id','code','no','number','ref','key','serial')
    name_hints  = ('name','branch','region','province','district','city','town',
                   'country','state','location','area','zone','territory',
                   'department','team','manager','staff','employee','category',
                   'type','class','segment','product','item','sku')
    metric_hints= ('amount','total','sum','revenue','sales','profit','loss',
                   'income','expense','cost','price','value','balance','payment',
                   'salary','wage','fee','charge','rate','score','mark')
    ratio_hints = ('achievement','ratio','rate','pct','percent','%','coverage',
                   'completion','attainment','efficiency','utilisation','utilization',
                   'growth','change','variance','target')
    count_hints = ('count','qty','quantity','units','number of','num','headcount',
                   'staff count','employees','seats','transactions','orders')

    is_name_year  = any(h in name_lower for h in year_hints)
    is_name_month = any(h in name_lower for h in month_hints)
    is_name_date  = any(h in name_lower for h in date_hints)

    # ── Try parsing as dates / periods ───────────────────────────────────────
    try:
        parsed = pd.to_datetime(clean, errors='coerce')
        if parsed.notna().sum() / n >= (0.8 if (is_name_date or re.search(r'date|time|day', name_lower)) else 0.9):
            return 'date'
    except Exception:
        pass

    # Period-like strings such as 2026-03, 2026/03, Mar-2026, 2026 Q1
    sample_vals = [str(v).strip().lower() for v in clean.head(30)]
    period_matches = sum(
        1 for v in sample_vals
        if re.match(r'^(19|20)\d{2}[-/]?(0?[1-9]|1[0-2])$', v)
        or re.match(r'^(0?[1-9]|1[0-2])[-/](19|20)\d{2}$', v)
        or re.match(r'^[a-z]{3,9}[-/ ]?(19|20)\d{2}$', v)
        or re.match(r'^(19|20)\d{2}[-/ ]?q[1-4]$', v)
    )
    if period_matches >= max(2, int(len(sample_vals) * 0.5)):
        return 'date'

    # ── Check for month name strings ──────────────────────────────────────────
    sample_vals = [str(v).strip().lower() for v in clean.head(20)]
    month_name_matches = sum(1 for v in sample_vals if v in MONTH_NAMES)
    if month_name_matches >= min(3, len(sample_vals) * 0.5):
        return 'time_cat'  # month names as categories

    # ── Quarter pattern ───────────────────────────────────────────────────────
    quarter_matches = sum(1 for v in sample_vals if re.match(r'^q[1-4]$', v.lower()))
    if quarter_matches >= min(2, len(sample_vals) * 0.4):
        return 'time_cat'

    # ── Numeric analysis ──────────────────────────────────────────────────────
    # Try force_numeric first — handles "85%", "LKR 250,000", "$1,200" etc.
    numeric_series = force_numeric(clean)
    numeric_frac   = numeric_series.notna().sum() / n

    if numeric_frac >= 0.85:
        vals      = numeric_series.dropna()
        v_min     = float(vals.min())
        v_max     = float(vals.max())
        v_mean    = float(vals.mean())
        unique_n  = int(vals.nunique())
        all_int   = (vals == vals.round()).all()

        # Year detection — strong heuristic
        if is_name_year or (all_int and 1900 <= v_min and v_max <= 2100 and unique_n <= 50):
            return 'year'

        # Month number detection — require name hint OR very small range (1-12) with <=12 unique
        # Guard against small count columns (staff counts, small metrics) being misclassified
        if is_name_month:
            return 'month'
        if all_int and 1 <= v_min and v_max <= 12 and unique_n <= 12:
            # Extra check: the column name should NOT suggest a quantity/count
            non_month_hints = ('staff','employee','count','qty','quantity','number','num',
                               'size','floor','level','age','score','grade','rank','seat')
            if not any(h in name_lower for h in non_month_hints):
                return 'month'

        # Ratio/achievement (0–1 range)
        if 0.0 <= v_min and v_max <= 1.05:
            if any(h in name_lower for h in ratio_hints):
                return 'ratio'
            if unique_n > 5:
                return 'ratio'

        # Percentage (0–100 range)
        if 0.0 <= v_min and v_max <= 105 and any(h in name_lower for h in ratio_hints):
            return 'percentage'

        # Count (non-negative integer)
        if all_int and v_min >= 0 and any(h in name_lower for h in count_hints):
            return 'count'

        # Currency (large positive)
        if v_mean > 1000 and any(h in name_lower for h in metric_hints):
            return 'currency'

        # Generic metric
        return 'metric'

    # ── Categorical string ────────────────────────────────────────────────────
    unique_n = int(clean.nunique())
    total_n  = len(series)

    if any(h in name_lower for h in id_hints) and unique_n / total_n > 0.8:
        return 'id'

    if unique_n <= 2:
        vals_lower = set(str(v).lower().strip() for v in clean)
        if vals_lower <= {'yes','no','true','false','1','0','y','n'}:
            return 'boolean'

    # ── Last resort: try force_numeric on string values ───────────────────────
    # Handles: "85%", "LKR 250,000", "$1,200", "Rs.500" etc.
    if numeric_frac < 0.85:
        forced = force_numeric(clean)
        forced_frac = forced.notna().sum() / n
        if forced_frac >= 0.8:
            # Successfully parsed as numeric — re-classify
            f_vals  = forced.dropna()
            f_min   = float(f_vals.min())
            f_max   = float(f_vals.max())
            f_mean  = float(f_vals.mean())
            all_int = (f_vals == f_vals.round()).all()

            if is_name_year or (all_int and 1900 <= f_min and f_max <= 2100 and f_vals.nunique() <= 50):
                return 'year'
            if is_name_month or (all_int and 1 <= f_min and f_max <= 12):
                return 'month'
            if 0.0 <= f_min and f_max <= 1.05 and any(h in name_lower for h in ratio_hints):
                return 'ratio'
            if 0.0 <= f_min and f_max <= 105 and any(h in name_lower for h in ratio_hints):
                return 'percentage'
            if all_int and f_min >= 0 and any(h in name_lower for h in count_hints):
                return 'count'
            if f_mean > 1000:
                return 'currency'
            if f_max <= 105 and f_min >= 0:
                return 'percentage'
            return 'metric'

    # High cardinality check BEFORE category — more than 30 unique strings = high_card
    if unique_n > 30 and unique_n / total_n > 0.3:
        return 'high_card'

    if unique_n <= 30:
        if any(h in name_lower for h in name_hints):
            return 'category'
        return 'category'

    if unique_n / total_n > 0.5:
        return 'high_card'

    return 'category'


def enrich_analysis(df: pd.DataFrame, analysis_result: dict) -> dict:
    """
    Add semantic types and combined date columns to analysis_result.
    Returns enriched result with new keys:
      - columns[i].semantic_type
      - columns[i].coerced_numeric (True if coercion needed)
      - combined_dates: list of {name, components, sample_values}
      - semantic_groups: {year:[], month:[], date:[], ratio:[], metric:[], category:[], ...}
    """
    cols = analysis_result.get('columns', [])

    # Detect semantic type for each column
    for col_info in cols:
        name   = col_info['name']
        if name not in df.columns:
            col_info['semantic_type'] = 'text'
            continue
        series = df[name]
        stype  = detect_semantic_type(series, name)
        col_info['semantic_type'] = stype

        # Flag columns that are numeric but stored as object
        if stype in ('metric','ratio','percentage','count','currency','year','month'):
            if str(series.dtype) == 'object':
                col_info['coerced_numeric'] = True
            # Re-compute numeric stats if they were missed
            if not col_info.get('is_numeric') or col_info.get('mean') is None:
                try:
                    ns = pd.to_numeric(series, errors='coerce').dropna()
                    if len(ns) > 0:
                        col_info['is_numeric']   = True
                        col_info['mean']   = round(float(ns.mean()), 4)
                        col_info['median'] = round(float(ns.median()), 4)
                        col_info['min']    = round(float(ns.min()), 4)
                        col_info['max']    = round(float(ns.max()), 4)
                        col_info['std']    = round(float(ns.std()), 4) if len(ns) > 1 else 0
                except Exception:
                    pass

    # Group columns by semantic type
    semantic_groups: dict[str, list[str]] = {}
    for col_info in cols:
        st = col_info.get('semantic_type', 'text')
        semantic_groups.setdefault(st, []).append(col_info['name'])

    # Detect combinable date columns (Month + Year → period)
    combined_dates = _detect_date_combinations(df, semantic_groups)

    analysis_result['semantic_groups']  = semantic_groups
    analysis_result['combined_dates']   = combined_dates
    return analysis_result


def _detect_date_combinations(df: pd.DataFrame, semantic_groups: dict) -> list:
    """Find Month+Year column pairs and build a combined date series."""
    combinations = []
    year_cols  = semantic_groups.get('year', [])
    month_cols = semantic_groups.get('month', []) + semantic_groups.get('time_cat', [])

    for y_col in year_cols:
        for m_col in month_cols:
            try:
                combined_name = f"{m_col}_{y_col}_combined"
                m_series = df[m_col].astype(str).str.strip()
                y_series = pd.to_numeric(df[y_col], errors='coerce')

                # Convert month names to numbers
                def month_to_num(v):
                    v_lower = v.lower()
                    return MONTH_NAMES.get(v_lower) or _safe_float(v)

                m_nums = m_series.map(month_to_num)
                if m_nums.notna().sum() < 2:
                    continue

                # Build period strings
                def build_period(m, y):
                    if pd.isna(m) or pd.isna(y):
                        return None
                    mo = int(m)
                    yr = int(y)
                    return f"{yr}-{mo:02d}"

                periods = [build_period(m, y) for m, y in zip(m_nums, y_series)]
                valid   = [p for p in periods if p]
                if len(valid) >= 2:
                    combinations.append({
                        'name':        combined_name,
                        'month_col':   m_col,
                        'year_col':    y_col,
                        'display_name': f"{m_col} / {y_col}",
                        'sample':      sorted(set(valid))[:12],
                        'count':       len(valid),
                    })
            except Exception:
                pass

    return combinations


def coerce_df_types(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    """
    Coerce columns to their semantic types using force_numeric for robustness.
    Handles messy formats: "85%", "LKR 250,000", "$1,200", etc.
    Returns a NEW DataFrame with numeric columns properly typed.
    """
    df = df.copy()
    for col_info in cols:
        name  = col_info['name']
        stype = col_info.get('semantic_type', 'text')
        if name not in df.columns:
            continue
        if stype in ('metric','ratio','percentage','count','currency','year','month'):
            df[name] = force_numeric(df[name])
        elif stype == 'time_cat':
            df[name] = df[name].astype(str).str.strip()
    return df


def build_time_series_df(df: pd.DataFrame, combo: dict,
                          value_col: str, agg: str = 'mean') -> pd.DataFrame:
    """
    Build a properly-sorted time series DataFrame from a Month+Year combination.
    Returns DataFrame with columns [period_label, value].
    """
    m_col = combo['month_col']
    y_col = combo['year_col']

    df2 = df.copy()
    df2[value_col] = pd.to_numeric(df2[value_col], errors='coerce')
    df2 = df2.dropna(subset=[value_col])

    def build_period(row):
        m = str(row[m_col]).strip()
        y_raw = row[y_col]
        y = _safe_float(str(y_raw))
        if y is None:
            return None
        m_num = MONTH_NAMES.get(m.lower()) or _safe_float(m)
        if m_num is None:
            return None
        return f"{int(y)}-{int(m_num):02d}"

    def period_label(row):
        m = str(row[m_col]).strip()
        y_raw = row[y_col]
        y = _safe_float(str(y_raw))
        if y is None:
            return str(m)
        # Abbreviate month
        m_num = MONTH_NAMES.get(m.lower())
        if m_num:
            month_abbr = MONTH_ORDER[m_num - 1] if m_num <= 12 else m
            return f"{month_abbr[:3]} {int(y)}"
        return f"{m} {int(y)}"

    df2['_period_sort'] = df2.apply(build_period, axis=1)
    df2['_period_label'] = df2.apply(period_label, axis=1)
    df2 = df2.dropna(subset=['_period_sort'])

    agg_fn = {'mean': 'mean','sum': 'sum','count': 'count','min': 'min','max': 'max'}.get(agg, 'mean')
    grouped = df2.groupby(['_period_sort','_period_label'])[value_col].agg(agg_fn).reset_index()
    grouped = grouped.sort_values('_period_sort')
    grouped.columns = ['period_sort', 'period_label', 'value']
    return grouped


def sort_categorical_series(labels: list) -> list:
    """Return indices that sort a categorical series in natural order."""
    label_lower = [str(l).strip().lower() for l in labels]

    # Month order
    month_idx = {m.lower(): i for i, m in enumerate(MONTH_ORDER)}
    if all(l in month_idx for l in label_lower):
        return sorted(range(len(labels)), key=lambda i: month_idx[label_lower[i]])

    # Quarter order
    q_idx = {q.lower(): i for i, q in enumerate(QUARTER_ORDER)}
    if all(l in q_idx for l in label_lower):
        return sorted(range(len(labels)), key=lambda i: q_idx[label_lower[i]])

    # Year-month pattern (YYYY-MM or MMM YYYY)
    ym_re = re.compile(r'^(\d{4})-(\d{2})$')
    if all(ym_re.match(l) for l in label_lower):
        return sorted(range(len(labels)), key=lambda i: labels[i])

    # MonthName-YYYY or MonthName YYYY (e.g. "April-2025", "Apr 2025", "Apr-2025")
    mname_re = re.compile(r'^([a-z]+)[\s\-](\d{4})$')
    if all(mname_re.match(l) for l in label_lower):
        def _mname_key(i):
            m = mname_re.match(label_lower[i])
            mon_str, yr = m.group(1), m.group(2)
            mon_num = MONTH_NAMES.get(mon_str) or MONTH_NAMES.get(mon_str[:3]) or 0
            return (int(yr), mon_num)
        return sorted(range(len(labels)), key=_mname_key)

    # YYYY-MonthName or YYYY-Mon (e.g. "2025-April", "2025-Apr")
    ym_name_re = re.compile(r'^(\d{4})[\s\-]([a-z]+)$')
    if all(ym_name_re.match(l) for l in label_lower):
        def _ym_name_key(i):
            m = ym_name_re.match(label_lower[i])
            yr, mon_str = m.group(1), m.group(2)
            mon_num = MONTH_NAMES.get(mon_str) or MONTH_NAMES.get(mon_str[:3]) or 0
            return (int(yr), mon_num)
        return sorted(range(len(labels)), key=_ym_name_key)

    return list(range(len(labels)))  # keep original order




# --- Enhanced semantic detection overrides (Phase 6 quality patch) ---
_DATE_NAME_HINTS = ('date','day','time','period','week','month','year','quarter','fy','financial year','fiscal year')
_METRIC_NAME_HINTS = ('amount','total','sum','revenue','sales','profit','loss','income','expense','cost','price','value','balance','payment','salary','wage','fee','charge','rate','score','mark','target','budget','actual','forecast','plan','variance')
_COUNT_HINTS = ('count','qty','quantity','units','number of','num','headcount','staff count','employees','transactions','orders','visits')
_CATEGORY_HINTS = ('name','branch','region','province','district','city','town','country','state','location','area','zone','territory','department','team','manager','staff','employee','category','type','class','segment','product','item','sku')


def _name_contains(name_lower: str, hints) -> bool:
    return any(h in name_lower for h in hints)


def _detect_dateish_string_series(clean: pd.Series) -> str | None:
    if clean.empty:
        return None
    sample = clean.astype(str).str.strip().head(60)
    lowered = sample.str.lower()
    if (lowered.isin(MONTH_NAMES.keys()).mean() >= 0.5) or (lowered.str.match(r'^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*$').mean() >= 0.5):
        return 'time_cat'
    if lowered.str.match(r'^q[1-4]$').mean() >= 0.4:
        return 'time_cat'
    if lowered.str.match(r'^\d{4}[-/]\d{1,2}$').mean() >= 0.5:
        return 'date'
    if lowered.str.match(r'^(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*[-/ ]?\d{2,4}$').mean() >= 0.4:
        return 'date'
    parsed = pd.to_datetime(sample, errors='coerce', dayfirst=False)
    if parsed.notna().mean() >= 0.75:
        return 'date'
    return None


def detect_semantic_type(series: pd.Series, col_name: str) -> str:
    name_lower = str(col_name).lower().strip()
    clean = series.dropna()
    n = len(clean)
    if n == 0:
        return 'text'

    string_dateish = _detect_dateish_string_series(clean)
    if string_dateish and _name_contains(name_lower, _DATE_NAME_HINTS):
        return string_dateish
    if string_dateish == 'date':
        return 'date'

    numeric_series = force_numeric(clean)
    numeric_frac = numeric_series.notna().sum() / max(n, 1)
    sample_unique = int(clean.nunique())

    if numeric_frac >= 0.85:
        vals = numeric_series.dropna()
        if vals.empty:
            return 'text'
        v_min = float(vals.min())
        v_max = float(vals.max())
        unique_n = int(vals.nunique())
        all_int = bool((vals == vals.round()).all())

        if _name_contains(name_lower, ('year','yr','fy','financial year','fiscal year')) or (all_int and 1900 <= v_min <= 2100 and 1900 <= v_max <= 2100 and unique_n <= 50):
            return 'year'
        if _name_contains(name_lower, ('month','mon','mth')):
            return 'month'
        if _name_contains(name_lower, ('quarter','qtr')) or (all_int and 1 <= v_min <= 4 and v_max <= 4 and unique_n <= 4 and 'quarter' in name_lower):
            return 'time_cat'
        if all_int and 1 <= v_min and v_max <= 12 and unique_n <= 12 and not _name_contains(name_lower, ('staff','employee','count','qty','quantity','number','score','grade','rank','age')):
            return 'month'
        if 0 <= v_min and v_max <= 1.05 and (_name_contains(name_lower, ('pct','percent','ratio','rate','achievement','utilisation','utilization','margin','completion','share')) or unique_n > 5):
            return 'ratio'
        if 0 <= v_min and v_max <= 100 and _name_contains(name_lower, ('pct','percent','%','rate','margin','achievement','share')):
            return 'percentage'
        if all_int and v_min >= 0 and _name_contains(name_lower, _COUNT_HINTS):
            return 'count'
        if _name_contains(name_lower, _METRIC_NAME_HINTS):
            return 'currency' if abs(float(vals.mean())) >= 1000 else 'metric'
        return 'metric'

    if _name_contains(name_lower, ('id','code','ref','serial')) and sample_unique / max(len(series),1) > 0.8:
        return 'id'
    if sample_unique <= 2:
        vals_lower = set(str(v).lower().strip() for v in clean.head(20))
        if vals_lower <= {'yes','no','true','false','1','0','y','n'}:
            return 'boolean'
    if sample_unique > 30 and sample_unique / max(len(series),1) > 0.3:
        return 'high_card'
    if _name_contains(name_lower, _CATEGORY_HINTS) or sample_unique <= 30:
        return 'category'
    return 'high_card' if sample_unique / max(len(series),1) > 0.5 else 'category'
