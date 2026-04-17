import json

from .charts import build_chart_data
from .models import ChartConfig
from .schema_normalization_engine import resolve_column_name


class ChartPayloadError(Exception):
    def __init__(self, message, *, field_errors=None, code='invalid_chart_payload'):
        super().__init__(message)
        self.message = message
        self.field_errors = field_errors or {}
        self.code = code


def _choice_values(choices):
    return {value for value, _label in choices}


def _split_csv_list(raw: str):
    return [item.strip() for item in (raw or '').split(',') if item.strip()]


def _column_map(upload):
    analysis = upload.analysis_result or {}
    cols = analysis.get('columns') or []
    out = {}
    for col in cols:
        if isinstance(col, dict) and col.get('name'):
            out[col['name']] = col
    return out


def _normalize_text(value):
    return (value or '').strip()


def _combined_date_names(upload):
    analysis = upload.analysis_result or {}
    combos = analysis.get('combined_dates') or []
    names = set()
    for combo in combos:
        if combo.get('display_name'):
            names.add(combo['display_name'])
        if combo.get('name'):
            names.add(combo['name'])
    return names


def _semantic_type(columns, value):
    return (columns.get(value) or {}).get('semantic_type', 'text')


def _build_config_json(post_data):
    return {
        'extra_measures': _split_csv_list(post_data.get('config_json_extra_measures', '')),
        'y2_axis': post_data.get('config_json_y2_axis', ''),
        'x_label': post_data.get('x_label') or post_data.get('config_json_x_label', ''),
        'y_label': post_data.get('y_label') or post_data.get('config_json_y_label', ''),
        'insight': post_data.get('insight') or post_data.get('config_json_insight', ''),
        'top_n': int(post_data.get('top_n') or post_data.get('config_json_top_n') or 10),
        'bottom_n': str(post_data.get('bottom_n') or post_data.get('config_json_bottom_n') or '').lower() in {'1','true','yes','on'},
        'comparison_mode': post_data.get('comparison_mode') or post_data.get('config_json_comparison_mode', ''),
        'target_column': post_data.get('target_column') or post_data.get('config_json_target_column', ''),
        'benchmark_column': post_data.get('benchmark_column') or post_data.get('config_json_benchmark_column', ''),
        'rolling_window': int(post_data.get('rolling_window') or post_data.get('config_json_rolling_window') or 3),
        'show_annotations': str(post_data.get('show_annotations') or post_data.get('config_json_show_annotations') or 'true').lower() in {'1','true','yes','on'},
    }


def _autofix_axes(chart_type, x_axis, y_axis, columns, numeric_columns, combo_names):
    bar_like = {'bar', 'horizontal_bar', 'line', 'area', 'rolling_line', 'cumulative_line', 'variance_bar', 'pareto', 'pie', 'doughnut'}
    if chart_type not in bar_like:
        return x_axis, y_axis
    x_is_combo = x_axis in combo_names
    x_is_numeric = x_axis in numeric_columns and not x_is_combo
    y_is_numeric = y_axis in numeric_columns
    y_type = _semantic_type(columns, y_axis)
    if x_is_numeric and y_axis and not y_is_numeric and y_type in {'category', 'date', 'month', 'year', 'time_cat'}:
        return y_axis, x_axis
    return x_axis, y_axis


def validate_chart_payload(upload, post_data, *, partial=False):
    columns = _column_map(upload)
    numeric_columns = {name for name, meta in columns.items() if meta.get('is_numeric') or meta.get('semantic_type') in {'metric','currency','count','ratio','percentage'}}
    combo_names = _combined_date_names(upload)
    chart_type = _normalize_text(post_data.get('chart_type', 'bar')) or 'bar'
    x_axis = _normalize_text(post_data.get('x_axis', ''))
    y_axis = _normalize_text(post_data.get('y_axis', ''))
    group_by = _normalize_text(post_data.get('group_by', ''))
    aggregation = _normalize_text(post_data.get('aggregation', 'sum')) or 'sum'
    color = _normalize_text(post_data.get('color', 'violet')) or 'violet'
    size = _normalize_text(post_data.get('size', 'md')) or 'md'
    title = _normalize_text(post_data.get('title', ''))
    config_json = _build_config_json(post_data)
    field_errors = {}

    x_axis, y_axis = _autofix_axes(chart_type, x_axis, y_axis, columns, numeric_columns, combo_names)

    if chart_type not in _choice_values(ChartConfig.CHART_TYPES):
        field_errors['chart_type'] = 'Unsupported chart type.'
    if aggregation not in _choice_values(ChartConfig.AGG_CHOICES):
        field_errors['aggregation'] = 'Unsupported aggregation.'
    if color not in _choice_values(ChartConfig.COLOR_PALETTES):
        field_errors['color'] = 'Unsupported color palette.'
    if not partial and size not in _choice_values(ChartConfig.SIZE_CHOICES):
        field_errors['size'] = 'Unsupported chart size.'

    if chart_type == 'kpi':
        if not y_axis:
            field_errors['y_axis'] = 'Select a measure column for KPI cards.'
    elif chart_type == 'histogram':
        if not y_axis:
            field_errors['y_axis'] = 'Select a numeric column for histograms.'
    elif chart_type == 'heatmap':
        pass
    else:
        if not x_axis:
            field_errors['x_axis'] = 'Select a dimension or time column.'
        if not y_axis:
            field_errors['y_axis'] = 'Select a measure column.'

    resolved_axes = {}
    for field_name, value in {'x_axis': x_axis, 'y_axis': y_axis, 'group_by': group_by}.items():
        if not value:
            continue
        res = resolve_column_name(value, columns.keys())
        if res.resolved:
            resolved_axes[field_name] = res.resolved
        elif value not in combo_names:
            field_errors[field_name] = 'Selected column was not found in this dataset.'

    x_axis = resolved_axes.get('x_axis', x_axis)
    y_axis = resolved_axes.get('y_axis', y_axis)
    group_by = resolved_axes.get('group_by', group_by)

    numeric_required = {'bar', 'horizontal_bar', 'line', 'area', 'rolling_line', 'cumulative_line', 'variance_bar', 'pareto', 'scatter', 'pie', 'doughnut', 'histogram', 'kpi', 'waterfall', 'bullet', 'progress_ring'}
    if y_axis and y_axis in columns and y_axis not in numeric_columns and chart_type in numeric_required:
        field_errors['y_axis'] = 'Y-axis must be a numeric measure for this chart type.'

    if chart_type in {'line','area','rolling_line','cumulative_line'} and x_axis in columns:
        x_type = _semantic_type(columns, x_axis)
        if x_type not in {'date', 'year', 'month', 'time_cat', 'category'}:
            field_errors.setdefault('x_axis', 'Use a date, month, year, period, or category column on the X-axis.')

    extra_measures = config_json.get('extra_measures') or []
    resolved_extra_measures = []
    bad_extras = []
    for m in extra_measures:
        res = resolve_column_name(m, columns.keys())
        if res.resolved in numeric_columns:
            resolved_extra_measures.append(res.resolved)
        else:
            bad_extras.append(m)
    config_json['extra_measures'] = resolved_extra_measures
    if bad_extras:
        field_errors['config_json_extra_measures'] = 'Extra measures must be numeric columns from this dataset.'

    y2_axis = _normalize_text(config_json.get('y2_axis', ''))
    if y2_axis:
        res = resolve_column_name(y2_axis, columns.keys())
        if not res.resolved or res.resolved not in numeric_columns:
            field_errors['config_json_y2_axis'] = 'Secondary axis must be a numeric column.'
        else:
            config_json['y2_axis'] = res.resolved

    if not title:
        if chart_type == 'kpi' and y_axis:
            title = y_axis
        elif x_axis and y_axis:
            title = f'{y_axis} by {x_axis}'
        else:
            title = 'New Chart'

    if field_errors:
        raise ChartPayloadError('Please correct the highlighted chart fields and try again.', field_errors=field_errors)

    return {
        'title': title,
        'chart_type': chart_type,
        'x_axis': x_axis,
        'y_axis': y_axis,
        'group_by': group_by,
        'aggregation': aggregation,
        'color': color,
        'size': size,
        'config_json': config_json,
    }


def error_payload(exc: ChartPayloadError):
    return {
        'ok': False,
        'error': exc.message,
        'message': exc.message,
        'code': exc.code,
        'field_errors': exc.field_errors,
    }


def get_next_sort_order(upload):
    last = upload.chart_configs.order_by('-sort_order').first()
    return (last.sort_order + 1) if last else 0


def create_chart_from_post(upload, post_data):
    payload = validate_chart_payload(upload, post_data)
    chart = ChartConfig.objects.create(
        upload=upload,
        title=payload['title'],
        chart_type=payload['chart_type'],
        x_axis=payload['x_axis'],
        y_axis=payload['y_axis'],
        group_by=payload['group_by'],
        aggregation=payload['aggregation'],
        color=payload['color'],
        size=payload['size'],
        sort_order=get_next_sort_order(upload),
        is_auto=False,
        config_json=payload['config_json'],
    )
    refresh_chart_cache(upload, chart)
    return chart


def update_chart_from_post(upload, chart, post_data):
    payload = validate_chart_payload(upload, post_data, partial=True)
    chart.title = payload['title']
    chart.chart_type = payload['chart_type']
    chart.x_axis = payload['x_axis']
    chart.y_axis = payload['y_axis']
    chart.group_by = payload['group_by']
    chart.aggregation = payload['aggregation']
    chart.color = payload['color']
    if post_data.get('size'):
        chart.size = payload['size']
    chart.is_auto = False
    chart.config_json = {**(chart.config_json or {}), **payload['config_json']}
    refresh_chart_cache(upload, chart)
    chart.save()
    return chart


def build_preview_data(upload, post_data):
    payload = validate_chart_payload(upload, post_data, partial=True)
    temp_chart = ChartConfig(
        upload=upload,
        chart_type=payload['chart_type'],
        x_axis=payload['x_axis'],
        y_axis=payload['y_axis'],
        group_by=payload['group_by'],
        aggregation=payload['aggregation'],
        color=payload['color'],
        title=payload['title'],
        config_json=payload['config_json'],
    )
    return build_chart_data(upload, temp_chart)


def refresh_chart_cache(upload, chart):
    chart.cached_data = build_chart_data(upload, chart)
    chart.save(update_fields=['cached_data', 'updated_at'] if chart.pk else ['cached_data'])
    return chart.cached_data
