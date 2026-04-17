from __future__ import annotations

import re
import pandas as pd


def _canonical(name: str) -> str:
    return re.sub(r'[^a-z0-9]+', '_', str(name).strip().lower()).strip('_')


def _numeric_columns(df: pd.DataFrame):
    out = []
    for col in df.columns:
        series = pd.to_numeric(df[col], errors="coerce")
        if series.notna().sum() >= max(3, int(len(df) * 0.5)):
            out.append(col)
    return out


def _find_best_match(columns, include_terms, exclude_terms=None):
    exclude_terms = exclude_terms or []
    best = None
    best_score = -1
    for col in columns:
        canon = _canonical(col)
        score = 0
        for term in include_terms:
            if term in canon:
                score += 3 if canon == term else 1
        for term in exclude_terms:
            if term in canon:
                score -= 2
        if score > best_score:
            best = col
            best_score = score
    return best if best_score > 0 else None


def add_derived_metrics(
    df: pd.DataFrame,
    business_roles: dict | None = None,
) -> tuple[pd.DataFrame, list[dict]]:
    """
    Return a dataframe with all profile-defined derived metrics added as columns,
    plus metadata for each.

    When `business_roles` is supplied (from profile_json['business_roles']),
    column resolution is exact and authoritative.  Falls back to heuristic
    keyword matching when roles are not available.
    """
    df = df.copy()
    derived: list[dict] = []
    num_cols = _numeric_columns(df)
    if not num_cols:
        return df, derived

    roles = business_roles or {}

    # ── Resolve role columns ────────────────────────────────────────────────
    def _exact_or_heuristic(role_key, include_terms, exclude_terms=None):
        role_val = roles.get(role_key, '')
        if role_val and role_val in df.columns:
            return role_val
        return _find_best_match(num_cols, include_terms, exclude_terms)

    revenue_col     = _exact_or_heuristic('actual_column',
                          ['revenue', 'sales', 'actual', 'amount', 'value', 'turnover', 'income', 'achivement', 'achievement'],
                          exclude_terms=['target', 'budget', 'plan', 'variance'])
    target_col      = _exact_or_heuristic('target_column',
                          ['target', 'budget', 'plan', 'forecast', 'given_target'])
    purchasing_col  = _exact_or_heuristic('purchasing_column',
                          ['purchasing', 'purchase', 'cost', 'expense', 'spend', 'procurement'])
    open_stock_col  = _exact_or_heuristic('opening_stock_column',
                          ['opening', 'open_stock', 'opening_stock'])
    close_stock_col = _exact_or_heuristic('closing_stock_column',
                          ['closing', 'close_stock', 'closing_stock'])
    profit_col      = _exact_or_heuristic('profit_column',
                          ['profit', 'gross_profit', 'net_profit'])
    count_col       = _find_best_match(num_cols,
                          ['quantity', 'qty', 'count', 'orders', 'transactions', 'units', 'staff'])

    def _add(name: str, label: str, semantic_type: str, series: pd.Series,
             source_columns: list):
        """Add a derived column to the df and record its metadata."""
        if name in df.columns:
            # Already exists — don't overwrite
            derived.append({'name': name, 'label': label,
                            'semantic_type': semantic_type,
                            'source_columns': source_columns})
            return
        df[name] = series
        derived.append({'name': name, 'label': label,
                        'semantic_type': semantic_type,
                        'source_columns': source_columns})

    # ── Target vs Actual metrics ────────────────────────────────────────────
    if revenue_col and target_col:
        actual  = pd.to_numeric(df[revenue_col], errors='coerce')
        target  = pd.to_numeric(df[target_col],  errors='coerce')
        safe_t  = target.replace(0, pd.NA)

        # achievement_pct — stored as 0–100 scale (e.g. 112.34, not 1.1234)
        _add('achievement_pct', 'Achievement %', 'ratio',
             (actual / safe_t * 100).round(2),
             [revenue_col, target_col])

        # variance_to_target — actual minus target (signed)
        _add('variance_to_target', 'Variance to Target', 'metric',
             (actual - target).round(2),
             [revenue_col, target_col])

        # given_target_minus_achivement
        _add('given_target_minus_achivement', 'Given Target minus Achivement', 'metric',
             (target - actual).round(2),
             [target_col, revenue_col])

        # given_target_to_achivement_ratio
        safe_a = actual.replace(0, pd.NA)
        _add('given_target_to_achivement_ratio', 'Given Target to Achivement Ratio', 'ratio',
             (target / safe_a).round(4),
             [target_col, revenue_col])

        # Legacy names kept for backwards compat
        _add('variance', 'Variance', 'metric',
             (actual - target).round(2),
             [revenue_col, target_col])
        _add('variance_pct', 'Variance %', 'ratio',
             (actual / safe_t - 1).round(4),
             [revenue_col, target_col])

    # ── Purchasing / Cost efficiency metrics ────────────────────────────────
    if revenue_col and purchasing_col:
        actual_s = pd.to_numeric(df[revenue_col],    errors='coerce')
        cost_s   = pd.to_numeric(df[purchasing_col], errors='coerce')
        safe_c   = cost_s.replace(0, pd.NA)
        safe_a   = actual_s.replace(0, pd.NA)

        # actual_to_cost_ratio
        _add('actual_to_cost_ratio', 'Achivement to Purchasing Ratio', 'ratio',
             (actual_s / safe_c).round(4),
             [revenue_col, purchasing_col])
        _add('achivement_to_purchasing_ratio', 'Achivement to Purchasing Ratio', 'ratio',
             (actual_s / safe_c).round(4),
             [revenue_col, purchasing_col])

        # cost_gap = actual minus purchasing
        _add('cost_gap', 'Achivement minus Purchasing', 'metric',
             (actual_s - cost_s).round(2),
             [revenue_col, purchasing_col])
        _add('achivement_minus_purchasing', 'Achivement minus Purchasing', 'metric',
             (actual_s - cost_s).round(2),
             [revenue_col, purchasing_col])

    if target_col and purchasing_col:
        target_s = pd.to_numeric(df[target_col],     errors='coerce')
        cost_s   = pd.to_numeric(df[purchasing_col], errors='coerce')
        safe_c   = cost_s.replace(0, pd.NA)
        _add('given_target_minus_purchasing', 'Given Target minus Purchasing', 'metric',
             (target_s - cost_s).round(2),
             [target_col, purchasing_col])
        _add('given_target_to_purchasing_ratio', 'Given Target to Purchasing Ratio', 'ratio',
             (target_s / safe_c).round(4),
             [target_col, purchasing_col])

    # ── Stock / Inventory metrics ───────────────────────────────────────────
    if open_stock_col and close_stock_col:
        opening = pd.to_numeric(df[open_stock_col],  errors='coerce')
        closing = pd.to_numeric(df[close_stock_col], errors='coerce')

        # stock_movement = closing - opening
        _add('stock_movement', 'Stock Movement', 'metric',
             (closing - opening).round(2),
             [open_stock_col, close_stock_col])

        # average_stock
        _add('average_stock', 'Average Stock', 'metric',
             ((opening + closing) / 2).round(2),
             [open_stock_col, close_stock_col])

        # stock_turnover = actual / average_stock
        if revenue_col:
            actual_s = pd.to_numeric(df[revenue_col], errors='coerce')
            avg_stk  = ((opening + closing) / 2).replace(0, pd.NA)
            _add('stock_turnover', 'Stock Turnover', 'ratio',
                 (actual_s / avg_stk).round(4),
                 [revenue_col, open_stock_col, close_stock_col])

    # ── Profitability metrics ───────────────────────────────────────────────
    if profit_col and revenue_col:
        safe_rev = pd.to_numeric(df[revenue_col], errors='coerce').replace(0, pd.NA)
        _add('margin_pct', 'Margin %', 'ratio',
             (pd.to_numeric(df[profit_col], errors='coerce') / safe_rev * 100).round(2),
             [profit_col, revenue_col])

    if purchasing_col and revenue_col:
        safe_rev = pd.to_numeric(df[revenue_col], errors='coerce').replace(0, pd.NA)
        _add('cost_pct', 'Cost %', 'ratio',
             (pd.to_numeric(df[purchasing_col], errors='coerce') / safe_rev * 100).round(2),
             [purchasing_col, revenue_col])

    # ── Contribution ────────────────────────────────────────────────────────
    if revenue_col:
        total = pd.to_numeric(df[revenue_col], errors='coerce').sum()
        if total:
            _add('contribution_pct', 'Contribution %', 'ratio',
                 (pd.to_numeric(df[revenue_col], errors='coerce') / total * 100).round(2),
                 [revenue_col])

    if count_col and revenue_col:
        safe_count = pd.to_numeric(df[count_col], errors='coerce').replace(0, pd.NA)
        _add('value_per_unit', 'Value per Unit', 'metric',
             (pd.to_numeric(df[revenue_col], errors='coerce') / safe_count).round(2),
             [revenue_col, count_col])

    if profit_col and count_col:
        safe_count = pd.to_numeric(df[count_col], errors='coerce').replace(0, pd.NA)
        _add('profit_per_unit', 'Profit per Unit', 'metric',
             (pd.to_numeric(df[profit_col], errors='coerce') / safe_count).round(2),
             [profit_col, count_col])

    # ── Lead time (Ship Date − Order Date) ───────────────────────────────────
    _order_col = _find_best_match(list(df.columns), ['order_date', 'order date', 'date_ordered', 'date_order'])
    _ship_col  = _find_best_match(list(df.columns), ['ship_date', 'ship date', 'shipped_date', 'delivery_date', 'dispatch_date'])
    if _order_col and _ship_col and _order_col != _ship_col:
        try:
            _order_dt = pd.to_datetime(df[_order_col], errors='coerce', infer_datetime_format=True)
            _ship_dt  = pd.to_datetime(df[_ship_col],  errors='coerce', infer_datetime_format=True)
            _lt = (_ship_dt - _order_dt).dt.days
            if _lt.notna().sum() >= max(3, int(len(df) * 0.4)):
                _add('lead_time_days', 'Lead Time (Days)', 'metric',
                     _lt.round(0),
                     [_order_col, _ship_col])
        except Exception:
            pass

    return df, derived
