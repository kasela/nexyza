from __future__ import annotations

from typing import Any, Dict, List

from .analysis_type_classifier import classify_analysis_type
from .dataset_chart_pack_engine import chart_pack_settings


def build_decision_chart_plan(profile: Dict[str, Any], target_count: int = 8) -> List[Dict[str, Any]]:
    classification = classify_analysis_type(profile)
    settings = chart_pack_settings(profile)
    semantics = profile.get('business_semantics') or {}
    semantic_roles = semantics.get('roles') or {}
    semantic_recommendations = semantics.get('recommendations') or {}
    archetype = semantics.get('primary_archetype') or ''

    measures = profile.get('measures') or []
    targets = profile.get('target_columns') or []
    times = profile.get('time_columns') or []
    dims = profile.get('dimensions') or []
    derived = profile.get('derived_metrics') or {}
    derived_available = list(derived.get('available') or [])
    derived_labels = derived.get('labels') or {}

    actual = semantic_roles.get('primary_measure') or classification.get('primary_measure') or (measures[0] if measures else '')
    secondary = classification.get('secondary_measure') or (measures[1] if len(measures) > 1 else '')
    target = semantic_roles.get('target_measure') or classification.get('primary_target_column') or (targets[0] if targets else '')
    time_col = semantic_roles.get('period_column') or settings.get('primary_time') or classification.get('primary_time_column') or (times[0] if times else '')
    dim = semantic_roles.get('primary_dimension') or settings.get('primary_grouping') or classification.get('primary_dimension') or (dims[0] if dims else '')
    dim2 = semantic_roles.get('comparison_dimension') or settings.get('secondary_grouping') or (dims[1] if len(dims) > 1 else '')
    dim3 = settings.get('tertiary_grouping') or (dims[2] if len(dims) > 2 else '')
    target_count = min(max(target_count, 6), int(settings.get('target_count_cap') or target_count))

    plan: List[Dict[str, Any]] = []
    used = set()

    def add(**kwargs):
        key = (
            kwargs.get('chart_type'),
            kwargs.get('x_axis') or '',
            kwargs.get('y_axis') or '',
            kwargs.get('target_column') or '',
            kwargs.get('group_by') or '',
            tuple(kwargs.get('extra_measures') or []),
        )
        if key in used or len(plan) >= target_count:
            return
        kwargs.setdefault('semantic_archetype', archetype)
        kwargs.setdefault('semantic_priority', 'recommended' if kwargs.get('chart_type') != 'kpi' else 'high')
        used.add(key)
        plan.append(kwargs)

    def title_for(metric: str) -> str:
        return derived_labels.get(metric, metric.replace('_', ' ').title())

    def kpi(title, metric, aggregation='sum', color='violet', insight='Headline KPI.', target_col=''):
        add(
            title=title,
            chart_type='kpi',
            x_axis='',
            y_axis=metric,
            aggregation=aggregation,
            group_by='',
            color=color,
            size='sm',
            x_label='',
            y_label=title,
            insight=insight,
            is_time_series=False,
            combined_date_key='',
            target_column=target_col,
        )

    if actual:
        kpi(f"{title_for(actual)} KPI", actual, 'sum', 'violet', f'Headline KPI for {title_for(actual)}.', target)
    if target:
        kpi(f"{title_for(target)} KPI", target, 'sum', 'blue', f'Headline KPI for {title_for(target)}.')
    for metric in derived_available[:3]:
        aggregation = 'mean' if derived.get('semantic_types', {}).get(metric) == 'ratio' else 'sum'
        color = 'emerald' if 'pct' in metric or 'ratio' in metric else 'rose' if 'variance' in metric or 'minus' in metric or 'gap' in metric else 'cyan'
        kpi(f"{title_for(metric)} KPI", metric, aggregation, color, f"Headline KPI for {title_for(metric)}.", target)

    recommended_charts = semantic_recommendations.get('charts') or []

    if 'target_vs_actual_trend' in recommended_charts and time_col and actual:
        add(
            title=f"{title_for(actual)} vs {title_for(target) if target else 'Benchmark'} Trend",
            chart_type='line',
            x_axis=time_col,
            y_axis=actual,
            aggregation='sum',
            group_by='',
            color='violet',
            size='full',
            x_label=time_col,
            y_label=title_for(actual),
            insight='Semantics-selected primary trend view for actual versus target.',
            is_time_series=True,
            combined_date_key=time_col,
            target_column=target,
            extra_measures=[target] if target else [],
            semantic_priority='high',
        )
    if 'variance_by_dimension' in recommended_charts and dim and actual and target:
        add(
            title=f"Variance to Target by {dim}",
            chart_type='variance_bar',
            x_axis=dim,
            y_axis=actual,
            aggregation='sum',
            group_by='',
            color='rose',
            size='lg',
            x_label=dim,
            y_label=title_for(actual),
            insight='Semantics-selected variance view for target attainment.',
            is_time_series=False,
            combined_date_key='',
            target_column=target,
            semantic_priority='high',
        )
    if 'attainment_ranked_bar' in recommended_charts and dim and actual:
        metric = next((m for m in derived_available if 'attainment' in m or 'pct' in m or 'ratio' in m), actual)
        add(
            title=f"Attainment by {dim}",
            chart_type='horizontal_bar',
            x_axis=dim,
            y_axis=metric,
            aggregation='mean' if metric != actual else 'sum',
            group_by='',
            color='emerald',
            size='lg',
            x_label=dim,
            y_label=title_for(metric),
            insight='Semantics-selected ranking of attainment across the primary dimension.',
            is_time_series=False,
            combined_date_key='',
            target_column=target,
            semantic_priority='high',
        )
    if 'period_variance' in recommended_charts and time_col and actual:
        variance_metric = next((m for m in derived_available if 'variance' in m or 'gap' in m), actual)
        add(
            title=f"Period Variance in {title_for(variance_metric)}",
            chart_type='area',
            x_axis=time_col,
            y_axis=variance_metric,
            aggregation='sum',
            group_by='',
            color='amber',
            size='lg',
            x_label=time_col,
            y_label=title_for(variance_metric),
            insight='Semantics-selected period variance story.',
            is_time_series=True,
            combined_date_key=time_col,
            target_column=target,
        )
    if 'top_bottom_segments' in recommended_charts and dim and actual:
        add(
            title=f"Top and Bottom {dim} by {title_for(actual)}",
            chart_type='horizontal_bar',
            x_axis=dim,
            y_axis=actual,
            aggregation='sum',
            group_by='',
            color='emerald',
            size='lg',
            x_label=dim,
            y_label=title_for(actual),
            insight='Semantics-selected top and bottom segment comparison.',
            is_time_series=False,
            combined_date_key='',
            target_column=target,
        )

    if time_col and actual:
        add(
            title=f"{title_for(actual)} Trend",
            chart_type='line',
            x_axis=time_col,
            y_axis=actual,
            aggregation='sum',
            group_by='',
            color='violet',
            size='full',
            x_label=time_col,
            y_label=title_for(actual),
            insight='Primary time trend for the main measure.',
            is_time_series=True,
            combined_date_key=time_col,
            target_column=target,
            extra_measures=[target] if target else [],
        )
        for metric in derived_available[:2]:
            if derived.get('semantic_types', {}).get(metric) == 'ratio' or 'variance' in metric:
                add(
                    title=f"{title_for(metric)} Trend",
                    chart_type='line' if derived.get('semantic_types', {}).get(metric) == 'ratio' else 'area',
                    x_axis=time_col,
                    y_axis=metric,
                    aggregation='mean' if derived.get('semantic_types', {}).get(metric) == 'ratio' else 'sum',
                    group_by='',
                    color='emerald' if derived.get('semantic_types', {}).get(metric) == 'ratio' else 'rose',
                    size='lg',
                    x_label=time_col,
                    y_label=title_for(metric),
                    insight=f"Trend of {title_for(metric).lower()} over time.",
                    is_time_series=True,
                    combined_date_key=time_col,
                    target_column=target,
                )

    ranking_metric = actual or (derived_available[0] if derived_available else (measures[0] if measures else ''))
    if dim and ranking_metric:
        add(
            title=f"{title_for(ranking_metric) if ranking_metric in derived_labels else ranking_metric} by {dim}",
            chart_type='horizontal_bar',
            x_axis=dim,
            y_axis=ranking_metric,
            aggregation='mean' if ranking_metric in derived_labels and derived.get('semantic_types', {}).get(ranking_metric) == 'ratio' else 'sum',
            group_by='',
            color='emerald',
            size='lg',
            x_label=dim,
            y_label=title_for(ranking_metric) if ranking_metric in derived_labels else ranking_metric,
            insight='Primary ranking comparison across the main grouping.',
            is_time_series=False,
            combined_date_key='',
            target_column=target,
            extra_measures=[target] if target and ranking_metric == actual else [],
        )
        if target and actual:
            add(
                title=f"{title_for(actual)} vs {title_for(target)} by {dim}",
                chart_type='variance_bar',
                x_axis=dim,
                y_axis=actual,
                aggregation='sum',
                group_by='',
                color='rose',
                size='lg',
                x_label=dim,
                y_label=title_for(actual),
                insight='Shows which entities are ahead or behind target.',
                is_time_series=False,
                combined_date_key='',
                target_column=target,
            )
        for metric in derived_available[:2]:
            if metric != ranking_metric:
                add(
                    title=f"{title_for(metric)} by {dim}",
                    chart_type='horizontal_bar',
                    x_axis=dim,
                    y_axis=metric,
                    aggregation='mean' if derived.get('semantic_types', {}).get(metric) == 'ratio' else 'sum',
                    group_by='',
                    color='cyan' if derived.get('semantic_types', {}).get(metric) == 'ratio' else 'amber',
                    size='md',
                    x_label=dim,
                    y_label=title_for(metric),
                    insight=f"Comparison of {title_for(metric).lower()} across {dim}.",
                    is_time_series=False,
                    combined_date_key='',
                    target_column=target,
                )
        if settings.get('prefer_pareto') or archetype in {'financial_statement', 'inventory_or_balance'}:
            if actual:
                add(
                    title=f"Contribution of {title_for(actual)} by {dim}",
                    chart_type='pareto',
                    x_axis=dim,
                    y_axis=actual,
                    aggregation='sum',
                    group_by='',
                    color='amber',
                    size='full',
                    x_label=dim,
                    y_label=title_for(actual),
                    insight='Contribution chart for prioritisation.',
                    is_time_series=False,
                    combined_date_key='',
                )

    for alt_dim in [dim2, dim3]:
        if alt_dim and len(plan) < target_count:
            metric = derived_available[0] if derived_available else actual
            if metric:
                # Use the actual column name in the title to avoid misleading role-based labels
                agg_fn = 'mean' if metric in derived_labels and derived.get('semantic_types', {}).get(metric) == 'ratio' else 'sum'
                # Low-cardinality dimension (e.g. tier codes: Gold/Silver/Bronze) → doughnut
                alt_dim_col = next((c for c in profile.get('column_profiles') or [] if c.get('name') == alt_dim), {})
                alt_dim_uniq = int(alt_dim_col.get('unique_count') or 99)
                if 2 <= alt_dim_uniq <= 6:
                    add(
                        title=f"{title_for(metric)} by {alt_dim}",
                        chart_type='doughnut',
                        x_axis=alt_dim,
                        y_axis=metric,
                        aggregation=agg_fn,
                        group_by='',
                        color='multi',
                        size='md',
                        x_label=alt_dim,
                        y_label=title_for(metric),
                        insight=f'Proportional {title_for(metric).lower()} breakdown by {alt_dim}.',
                        is_time_series=False,
                        combined_date_key='',
                        target_column=target,
                    )
                else:
                    add(
                        title=f"{title_for(metric)} by {alt_dim}",
                        chart_type='horizontal_bar',
                        x_axis=alt_dim,
                        y_axis=metric,
                        aggregation=agg_fn,
                        group_by='',
                        color='blue',
                        size='md',
                        x_label=alt_dim,
                        y_label=title_for(metric),
                        insight=f'Comparison of {title_for(metric).lower()} across {alt_dim}.',
                        is_time_series=False,
                        combined_date_key='',
                        target_column=target,
                    )

    ratio_metric = next((m for m in derived_available if derived.get('semantic_types', {}).get(m) == 'ratio'), '')
    metric_gap = next((m for m in derived_available if 'gap' in m or 'minus' in m or 'variance' in m), '')
    if settings.get('allow_scatter') and len(measures) >= 2 and actual and secondary and actual != secondary and len(plan) < target_count and archetype not in {'target_vs_actual'}:
        add(
            title=f"{title_for(actual)} vs {title_for(secondary)}",
            chart_type='scatter',
            x_axis=actual,
            y_axis=secondary,
            aggregation='mean',
            group_by='',
            color='violet',
            size='md',
            x_label=title_for(actual),
            y_label=title_for(secondary),
            insight='Relationship view between the two main measures.',
            is_time_series=False,
            combined_date_key='',
        )
    if settings.get('prefer_heatmap') and dim and dim2 and (actual or ratio_metric) and len(plan) < target_count:
        y_metric = actual or ratio_metric
        add(
            title=f"{title_for(y_metric)} Heatmap",
            chart_type='heatmap',
            x_axis=dim,
            y_axis=y_metric,
            aggregation='sum',
            group_by=dim2,
            color='multi',
            size='full',
            x_label=dim,
            y_label=title_for(y_metric),
            insight='Cross-segment comparison between two strong groupings.',
            is_time_series=False,
            combined_date_key='',
        )
    if not time_col and len(plan) < target_count:
        hist_metric = ratio_metric or metric_gap or actual or secondary
        if hist_metric:
            add(
                title=f"Distribution of {title_for(hist_metric)}",
                chart_type='histogram',
                x_axis='',
                y_axis=hist_metric,
                aggregation='count',
                group_by='',
                color='amber',
                size='md',
                x_label=title_for(hist_metric),
                y_label='Frequency',
                insight='Distribution view for spread and outliers.',
                is_time_series=False,
                combined_date_key='',
            )

    return plan[:target_count]
