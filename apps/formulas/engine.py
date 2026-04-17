"""
Safe formula engine.
Evaluates pandas-style column expressions on a DataFrame.
"""
import re
import pandas as pd
import numpy as np

# Allowed functions in expressions
SAFE_FUNCS = {
    'abs': abs, 'round': round, 'min': min, 'max': max, 'sum': sum,
    'len': len, 'str': str, 'int': int, 'float': float,
    'log': np.log, 'log10': np.log10, 'sqrt': np.sqrt,
    'exp': np.exp, 'ceil': np.ceil, 'floor': np.floor,
    'where': np.where, 'nan': np.nan, 'inf': np.inf,
    'pd': pd, 'np': np,
}

BLOCKED = re.compile(r'\b(import|exec|eval|open|os|sys|__)\b')


def validate_expression(expr: str) -> tuple[bool, str]:
    if BLOCKED.search(expr):
        return False, "Expression contains disallowed keywords."
    if len(expr) > 500:
        return False, "Expression too long."
    return True, ""


def evaluate_expression(df: pd.DataFrame, expression: str, col_name: str) -> pd.Series:
    """
    Evaluate expression string against DataFrame columns.
    Column names are available by their exact names.
    """
    valid, err = validate_expression(expression)
    if not valid:
        raise ValueError(err)

    # Build local namespace: all columns accessible by name
    local_ns = {col: df[col] for col in df.columns}
    local_ns.update(SAFE_FUNCS)
    local_ns['df'] = df

    try:
        result = eval(expression, {"__builtins__": {}}, local_ns)
    except Exception as e:
        raise ValueError(f"Expression error: {e}")

    if isinstance(result, (pd.Series,)):
        return result.rename(col_name)
    # Scalar or array
    return pd.Series([result] * len(df), name=col_name, index=df.index)


def apply_computed_columns(df: pd.DataFrame, computed_cols) -> pd.DataFrame:
    """Apply all active ComputedColumn objects to a DataFrame."""
    for cc in computed_cols:
        if not cc.is_active:
            continue
        try:
            df[cc.name] = evaluate_expression(df, cc.expression, cc.name)
        except Exception:
            df[cc.name] = pd.NA
    return df


def preview_expression(df: pd.DataFrame, expression: str) -> dict:
    """Return first 5 values + basic stats for an expression."""
    try:
        series = evaluate_expression(df, expression, '__preview__')
        values = series.head(10).tolist()
        return {
            'ok': True,
            'sample': [str(v) for v in values],
            'dtype': str(series.dtype),
            'non_null': int(series.notna().sum()),
        }
    except Exception as e:
        return {'ok': False, 'error': str(e)}
