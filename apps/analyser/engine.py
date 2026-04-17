"""
Core analysis engine — parses CSV, Excel (multi-sheet), JSON and computes statistics.
v2: multi-sheet Excel support, sheet selector metadata.
"""
import json
import math
import pandas as pd
from pathlib import Path

from .schema_normalization_engine import build_schema_metadata, normalize_dataframe


def _safe_preview(v):
    """Make a preview cell JSON-safe — convert any non-primitive to str."""
    if v is None or v == '':
        return ''
    if isinstance(v, float):
        if math.isnan(v) or math.isinf(v):
            return ''
        return v
    if isinstance(v, (int, bool, str)):
        return v
    # Catch Timestamp, Period, date, numpy scalar, etc.
    safe = _safe(v)
    if safe is None:
        return ''
    if isinstance(safe, (int, float, bool, str)):
        return safe
    return str(safe)

def _safe(val):
    """Convert a value to a JSON-serialisable Python primitive.
    Handles: numpy scalars, pandas Timestamp/Period/NA, NaN/Inf floats.
    """
    if val is None:
        return None
    if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
        return None
    # pandas Timestamp → ISO string
    try:
        import pandas as _pd
        if isinstance(val, _pd.Timestamp):
            return val.isoformat()
        if isinstance(val, _pd.Period):
            return str(val)
        if val is _pd.NA or val is _pd.NaT:
            return None
    except Exception:
        pass
    # numpy scalars
    try:
        import numpy as _np
        if isinstance(val, _np.integer):
            return int(val)
        if isinstance(val, _np.floating):
            return None if (_np.isnan(val) or _np.isinf(val)) else float(val)
        if isinstance(val, _np.bool_):
            return bool(val)
        if isinstance(val, _np.ndarray):
            return val.tolist()
    except Exception:
        pass
    # datetime / date
    try:
        import datetime
        if isinstance(val, (datetime.datetime, datetime.date)):
            return val.isoformat()
    except Exception:
        pass
    return val


def get_excel_sheets(filepath: str) -> list[str]:
    """Return list of sheet names in an Excel file."""
    xl = pd.ExcelFile(filepath, engine='openpyxl')
    return xl.sheet_names


def load_dataframe(filepath: str, file_type: str, sheet_name=None) -> pd.DataFrame:
    path = Path(filepath)
    if file_type == 'csv':
        df = pd.read_csv(path, low_memory=False)
    elif file_type == 'excel':
        kw = {'engine': 'openpyxl'}
        if sheet_name is not None:
            kw['sheet_name'] = sheet_name
        df = pd.read_excel(path, **kw)
    elif file_type == 'json':
        with open(path, 'r', encoding='utf-8') as f:
            raw = json.load(f)
        if isinstance(raw, list):
            df = pd.DataFrame(raw)
        elif isinstance(raw, dict):
            for v in raw.values():
                if isinstance(v, list):
                    df = pd.DataFrame(v)
                    break
            else:
                df = pd.DataFrame([raw])
        else:
            raise ValueError("Unsupported JSON structure")
    else:
        raise ValueError(f"Unknown file type: {file_type}")
    return normalize_dataframe(df)


def analyse(filepath: str, file_type: str, sheet_name=None) -> dict:
    df = load_dataframe(filepath, file_type, sheet_name=sheet_name)

    # Excel sheet metadata
    sheets = None
    if file_type == 'excel':
        try:
            sheets = get_excel_sheets(filepath)
        except Exception:
            sheets = []

    rows, cols = df.shape
    columns_info = []

    for col in df.columns:
        series = df[col]
        dtype = str(series.dtype)
        null_count = int(series.isna().sum())
        unique_count = int(series.nunique())

        col_info = {
            'name': col,
            'dtype': dtype,
            'null_count': null_count,
            'null_pct': round(null_count / rows * 100, 1) if rows else 0,
            'unique_count': unique_count,
        }

        if pd.api.types.is_numeric_dtype(series):
            desc = series.describe()
            col_info.update({
                'is_numeric': True,
                'min': _safe(desc.get('min')),
                'max': _safe(desc.get('max')),
                'mean': _safe(desc.get('mean')),
                'median': _safe(series.median()),
                'std': _safe(desc.get('std')),
                'q25': _safe(desc.get('25%')),
                'q75': _safe(desc.get('75%')),
            })
            try:
                clean = series.dropna()
                if len(clean) > 1:
                    counts, edges = pd.cut(clean, bins=min(10, len(clean.unique())), retbins=True)
                    hist = counts.value_counts(sort=False)
                    col_info['histogram'] = {
                        'labels': [f"{_safe(edges[i]):.2g}–{_safe(edges[i+1]):.2g}" for i in range(len(edges)-1)],
                        'values': [int(v) for v in hist.values],
                    }
                else:
                    col_info['histogram'] = None
            except Exception:
                col_info['histogram'] = None
        else:
            col_info['is_numeric'] = False
            try:
                vc = series.value_counts().head(10)
                col_info['top_values'] = [
                    {'value': _safe_preview(k), 'count': int(v)} for k, v in vc.items()
                ]
            except Exception:
                col_info['top_values'] = []

        columns_info.append(col_info)

    numeric_cols = [c['name'] for c in columns_info if c.get('is_numeric')]
    correlation = None
    if len(numeric_cols) >= 2:
        try:
            corr = df[numeric_cols].corr().round(3)
            correlation = {
                'columns': numeric_cols,
                'matrix': [[_safe(corr.iat[i, j]) for j in range(len(numeric_cols))] for i in range(len(numeric_cols))],
            }
        except Exception:
            pass

    preview_df = df.head(100).fillna('')
    preview_rows = preview_df.values.tolist()
    for row in preview_rows:
        for i, v in enumerate(row):
            row[i] = _safe_preview(v)

    result = {
        'rows': rows,
        'cols': cols,
        'columns': columns_info,
        'correlation': correlation,
        'preview': {'columns': list(df.columns), 'rows': preview_rows},
        'numeric_columns': numeric_cols,
        'sheets': sheets,
        'active_sheet': sheet_name,
        'schema_normalization': build_schema_metadata(df),
    }

    # Enrich with semantic types, combined dates, groups
    try:
        from .intelligence import enrich_analysis, force_numeric
        result = enrich_analysis(df, result)
        
        # Re-compute numeric stats for columns that force_numeric can now parse
        # (handles "85%", "LKR 250,000", "$1,200" stored as object dtype)
        for col_info in result.get('columns', []):
            name  = col_info['name']
            stype = col_info.get('semantic_type', 'text')
            if (stype in ('metric','ratio','percentage','count','currency')
                    and not col_info.get('is_numeric')
                    and name in df.columns):
                ns = force_numeric(df[name]).dropna()
                if len(ns) >= 1:
                    col_info['is_numeric']   = True
                    col_info['coerced_numeric'] = True
                    col_info['mean']   = _safe(float(ns.mean()))
                    col_info['median'] = _safe(float(ns.median()))
                    col_info['min']    = _safe(float(ns.min()))
                    col_info['max']    = _safe(float(ns.max()))
                    col_info['std']    = _safe(float(ns.std())) if len(ns) > 1 else 0
                    # Rebuild histogram
                    try:
                        if ns.nunique() > 1:
                            counts, edges = pd.cut(ns, bins=min(10, ns.nunique()), retbins=True)
                            hist = counts.value_counts(sort=False)
                            col_info['histogram'] = {
                                'labels': [f"{_safe(edges[i]):.2g}\u2013{_safe(edges[i+1]):.2g}"
                                           for i in range(len(edges)-1)],
                                'values': [int(v) for v in hist.values],
                            }
                    except Exception:
                        pass
    except Exception:
        pass

    return result


def compare_dataframes(result_a: dict, result_b: dict) -> dict:
    """Produce a diff summary between two analysis results."""
    cols_a = {c['name']: c for c in result_a.get('columns', [])}
    cols_b = {c['name']: c for c in result_b.get('columns', [])}
    names_a = set(cols_a)
    names_b = set(cols_b)

    only_in_a = sorted(names_a - names_b)
    only_in_b = sorted(names_b - names_a)
    in_both = sorted(names_a & names_b)

    col_diffs = []
    for name in in_both:
        ca, cb = cols_a[name], cols_b[name]
        diffs = {}
        for field in ('mean', 'median', 'min', 'max', 'null_pct', 'unique_count'):
            va, vb = ca.get(field), cb.get(field)
            if va is not None and vb is not None:
                try:
                    diff = round(float(vb) - float(va), 4)
                    pct = round((diff / float(va) * 100), 1) if va != 0 else None
                    diffs[field] = {'a': va, 'b': vb, 'diff': diff, 'pct': pct}
                except (TypeError, ValueError):
                    if va != vb:
                        diffs[field] = {'a': va, 'b': vb, 'diff': None, 'pct': None}
        col_diffs.append({'name': name, 'diffs': diffs})

    return {
        'rows_a': result_a.get('rows', 0),
        'rows_b': result_b.get('rows', 0),
        'cols_a': result_a.get('cols', 0),
        'cols_b': result_b.get('cols', 0),
        'only_in_a': only_in_a,
        'only_in_b': only_in_b,
        'in_both': in_both,
        'col_diffs': col_diffs,
    }
