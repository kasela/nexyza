"""
Natural Language Query engine.
Claude converts user questions into pandas operations, executes them safely,
and returns structured answer + optional chart/table data.
"""
import json
import re
import pandas as pd
import numpy as np
from django.conf import settings
from apps.analyser.engine import load_dataframe


NLQ_SYSTEM = """You are a data analyst. Given dataset info and a user question, respond with ONLY valid JSON:
{
  "answer": "Clear natural-language answer (1-2 sentences)",
  "pandas_code": "pandas code storing final result in `result` variable. Use df. No imports/exec/eval.",
  "chart": {"type":"bar|line|pie|scatter|number|table","title":"chart title","x":"col","y":"col"} or null
}

Rules:
- pandas_code: use only pandas/numpy on df variable
- For single number: result = df['col'].mean()
- For grouped: result = df.groupby('col')['val'].agg('sum').reset_index()
- For table: result = df[...].head(20)
- chart.type = "number" for scalar answers, "table" for DataFrames with >5 rows
- chart = null if no visual value
"""


# Safe builtins whitelist
_SAFE_BUILTINS = {
    '__builtins__': {},
    'abs': abs, 'round': round, 'min': min, 'max': max,
    'sum': sum, 'len': len, 'str': str, 'int': int, 'float': float,
    'bool': bool, 'list': list, 'dict': dict, 'sorted': sorted,
    'pd': pd, 'np': np,
}


def _safe_exec(code: str, df: pd.DataFrame):
    """Execute pandas code safely in a sandboxed namespace."""
    blocked = re.compile(r'\b(import|exec|eval|open|os|sys|__import__|globals|locals|getattr|setattr)\b')
    if blocked.search(code):
        raise ValueError("Expression contains disallowed keywords")
    if len(code) > 2000:
        raise ValueError("Code too long")

    ns = dict(_SAFE_BUILTINS)
    ns['df'] = df.copy()
    ns['result'] = None

    exec(code, ns)
    return ns.get('result')


def _build_chart_data(result, chart_spec: dict) -> dict:
    """Convert pandas result + chart spec into Chart.js compatible data."""
    if chart_spec is None:
        return None

    chart_type = chart_spec.get('type', 'bar')
    title      = chart_spec.get('title', '')

    if chart_type == 'number':
        val = result
        if isinstance(val, (pd.Series, list)):
            val = val.iloc[0] if hasattr(val, 'iloc') else val[0]
        return {
            'chart_type': 'number',
            'title':      title,
            'value':      str(round(float(val), 4)) if val is not None else '—',
        }

    if isinstance(result, pd.DataFrame):
        if chart_type == 'table' or len(result) > 15:
            cols = result.columns.tolist()
            rows = [[str(v) for v in row] for row in result.values.tolist()[:30]]
            return {'chart_type': 'table', 'title': title, 'table': True,
                    'columns': cols, 'rows': rows}

        x_col = chart_spec.get('x') or result.columns[0]
        y_col = chart_spec.get('y') or (result.columns[1] if len(result.columns) > 1 else result.columns[0])

        if x_col not in result.columns:
            x_col = result.columns[0]
        if y_col not in result.columns:
            y_col = result.columns[-1]

        labels = [str(v) for v in result[x_col].tolist()]
        vals   = [round(float(v), 4) if pd.notna(v) else None for v in result[y_col].tolist()]

        palette = {'bar': 'rgba(139,92,246,0.7)', 'line': 'rgba(59,130,246,1)',
                   'pie': None, 'scatter': 'rgba(16,185,129,0.7)'}
        bg = palette.get(chart_type, 'rgba(139,92,246,0.7)')

        return {
            'chart_type': chart_type,
            'title':      title,
            'labels':     labels,
            'datasets': [{
                'label': y_col,
                'data':  vals,
                'backgroundColor': bg or [f'hsl({i*40},60%,55%)' for i in range(len(vals))],
                'borderColor': bg or '#7c3aed',
                'borderWidth': 2,
                'tension': 0.3,
                'fill': chart_type == 'area',
            }],
            'x_label': str(x_col),
            'y_label': str(y_col),
        }

    if isinstance(result, pd.Series):
        labels = [str(v) for v in result.index.tolist()]
        vals   = [round(float(v), 4) if pd.notna(v) else None for v in result.values.tolist()]
        return {
            'chart_type': chart_type,
            'title':      title,
            'labels':     labels,
            'datasets': [{
                'label': result.name or y_col if (y_col := chart_spec.get('y')) else 'Value',
                'data':  vals,
                'backgroundColor': 'rgba(139,92,246,0.7)',
                'borderColor': 'rgba(139,92,246,1)',
                'borderWidth': 2,
            }],
        }

    return None


def answer_question(upload, question: str) -> dict:
    import anthropic
    client   = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
    analysis = upload.analysis_result or {}
    cols     = analysis.get('columns', [])
    preview  = analysis.get('preview', {})

    # Build compact column context
    col_lines = []
    for c in cols[:25]:
        if c.get('is_numeric'):
            col_lines.append(f"- {c['name']} [num]: min={c.get('min')}, max={c.get('max')}, mean={round(c.get('mean') or 0, 2)}")
        else:
            tops = [tv['value'] for tv in c.get('top_values', [])[:3]]
            col_lines.append(f"- {c['name']} [cat]: {c.get('unique_count')} unique, e.g. {', '.join(str(t) for t in tops)}")

    # Sample rows
    sample_rows = preview.get('rows', [])[:3]
    sample_cols = preview.get('columns', [])
    sample_txt  = ''
    if sample_rows and sample_cols:
        sample_txt  = 'Sample rows:\n' + '\t'.join(sample_cols[:10]) + '\n'
        sample_txt += '\n'.join('\t'.join(str(v) for v in r[:10]) for r in sample_rows[:3])

    context = (
        f'Dataset: "{upload.original_name}" | {analysis.get("rows",0):,} rows | {len(cols)} cols\n'
        f'Columns:\n' + '\n'.join(col_lines) + '\n\n' + sample_txt
    )

    msg = client.messages.create(
        model='claude-sonnet-4-20250514',
        max_tokens=800,
        system=NLQ_SYSTEM,
        messages=[{
            'role': 'user',
            'content': f'{context}\n\nQuestion: {question}',
        }],
    )
    tokens_in  = msg.usage.input_tokens
    tokens_out = msg.usage.output_tokens
    raw_text   = msg.content[0].text.strip()

    # Parse JSON response
    try:
        clean = re.sub(r'^```(?:json)?\s*|\s*```$', '', raw_text, flags=re.MULTILINE).strip()
        spec  = json.loads(clean)
    except json.JSONDecodeError:
        return {
            'answer': raw_text[:500],
            'code': '', 'chart_data': None,
            'result_value': None,
            'tokens_used': tokens_in + tokens_out,
            'error': '',
        }

    answer     = spec.get('answer', '')
    code       = spec.get('pandas_code', '')
    chart_spec = spec.get('chart')

    # Execute the pandas code
    result_value = None
    chart_data   = None
    error        = ''

    if code:
        try:
            df = load_dataframe(upload.file.path, upload.file_type,
                                sheet_name=getattr(upload, 'active_sheet', None))
            result_obj = _safe_exec(code, df)
            chart_data  = _build_chart_data(result_obj, chart_spec)

            if result_obj is None:
                pass
            elif isinstance(result_obj, (int, float, np.integer, np.floating)):
                result_value = round(float(result_obj), 4)
            elif isinstance(result_obj, pd.DataFrame):
                result_value = f'{len(result_obj)} rows'
            elif isinstance(result_obj, pd.Series):
                result_value = result_obj.to_dict()
            else:
                result_value = str(result_obj)[:200]

        except Exception as e:
            error = f"Computation error: {e}"

    return {
        'answer':       answer,
        'code':         code,
        'chart_data':   chart_data,
        'result_value': result_value,
        'tokens_used':  tokens_in + tokens_out,
        'error':        error,
    }
