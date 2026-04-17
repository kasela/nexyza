import json
import io
import os
import tempfile
import pandas as pd
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from apps.analyser.models import FileUpload, CleaningOperation
from apps.analyser.engine import analyse, load_dataframe


def _apply_operations(df: pd.DataFrame, ops: list) -> pd.DataFrame:
    for op in ops:
        t = op['type']
        p = op.get('params', {})
        try:
            if t == 'drop_nulls':
                col = p.get('column')
                df = df.dropna(subset=[col]) if col else df.dropna()
            elif t == 'fill_nulls':
                col, val = p['column'], p.get('value', '')
                df[col] = df[col].fillna(val)
            elif t == 'rename_column':
                df = df.rename(columns={p['old_name']: p['new_name']})
            elif t == 'drop_column':
                df = df.drop(columns=[p['column']], errors='ignore')
            elif t == 'find_replace':
                col = p.get('column')
                find, replace = p.get('find', ''), p.get('replace', '')
                if col:
                    df[col] = df[col].astype(str).str.replace(find, replace, regex=False)
                else:
                    df = df.replace(find, replace)
            elif t == 'filter_rows':
                col, op_sym, val = p['column'], p['operator'], p['value']
                if op_sym == 'eq':       df = df[df[col].astype(str) == str(val)]
                elif op_sym == 'ne':     df = df[df[col].astype(str) != str(val)]
                elif op_sym == 'gt':     df = df[pd.to_numeric(df[col], errors='coerce') > float(val)]
                elif op_sym == 'lt':     df = df[pd.to_numeric(df[col], errors='coerce') < float(val)]
                elif op_sym == 'gte':    df = df[pd.to_numeric(df[col], errors='coerce') >= float(val)]
                elif op_sym == 'lte':    df = df[pd.to_numeric(df[col], errors='coerce') <= float(val)]
                elif op_sym == 'contains': df = df[df[col].astype(str).str.contains(str(val), na=False)]
                elif op_sym == 'not_null': df = df[df[col].notna()]
            elif t == 'deduplicate':
                raw = p.get('columns', '') or p.get('column', '')
                subset = [c.strip() for c in raw.split(',') if c.strip()] if raw else None
                df = df.drop_duplicates(subset=subset)
            elif t == 'split_column':
                col   = p['column']
                delim = p.get('delimiter', ',')
                names = [n.strip() for n in p.get('new_names', '').split(',') if n.strip()]
                if col in df.columns:
                    parts = df[col].astype(str).str.split(delim, expand=True)
                    for i, new_name in enumerate(names):
                        if i < parts.shape[1]:
                            df[new_name] = parts[i]
            elif t == 'merge_columns':
                cols2merge = [c.strip() for c in p.get('columns', '').split(',') if c.strip()]
                delim      = p.get('delimiter', ' ')
                new_name   = p.get('new_name', 'merged')
                if cols2merge:
                    df[new_name] = df[cols2merge].astype(str).agg(delim.join, axis=1)
            elif t == 'strip_whitespace':
                col = p.get('column')
                if col and col in df.columns:
                    df[col] = df[col].astype(str).str.strip()
                elif not col:
                    for c in df.select_dtypes(include='object').columns:
                        df[c] = df[c].astype(str).str.strip()
            elif t == 'to_uppercase':
                col = p.get('column')
                if col and col in df.columns:
                    df[col] = df[col].astype(str).str.upper()
            elif t == 'to_lowercase':
                col = p.get('column')
                if col and col in df.columns:
                    df[col] = df[col].astype(str).str.lower()
            elif t == 'convert_numeric':
                col = p.get('column')
                if col and col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')
        except Exception:
            pass
    return df


def _col_options(cols):
    return "".join(f'<option value="{c}">{c}</option>' for c in cols)


def _op_forms(all_columns):
    col_opts = "".join(f'<option value="{c}">{c}</option>' for c in all_columns)
    sel_req  = f'''<select name="column" class="input-field text-sm mb-2" required>
      <option value="">Select column…</option>{col_opts}</select>'''
    sel_opt  = f'''<select name="column" class="input-field text-sm mb-2">
      <option value="">All columns</option>{col_opts}</select>'''

    return [
        ("drop_nulls",  "Drop Null Rows",      sel_opt + '<p class="text-slate-500 text-xs">Leave blank to drop rows with ANY null.</p>'),
        ("fill_nulls",  "Fill Null Values",     sel_req + '<input type="text" name="fill_value" placeholder="Fill value (e.g. 0 or N/A)" class="input-field text-sm">'),
        ("find_replace","Find & Replace",       sel_opt + '<input type="text" name="find"    placeholder="Find…"         class="input-field text-sm mb-2">' + '<input type="text" name="replace" placeholder="Replace with…" class="input-field text-sm">'),
        ("rename_column","Rename Column",
            f'<select name="old_name" class="input-field text-sm mb-2" required><option value="">Select column…</option>{col_opts}</select>' +
            '<input type="text" name="new_name" placeholder="New name…" class="input-field text-sm" required>'),
        ("drop_column", "Drop Column",
            f'<select name="column" class="input-field text-sm mb-2" required><option value="">Select column…</option>{col_opts}</select>' +
            '<p class="text-slate-500 text-xs">Permanently removes this column from the output.</p>'),
        ("filter_rows", "Filter Rows",          sel_req +
            '<select name="operator" class="input-field text-sm mb-2">' +
            '<option value="eq">equals</option><option value="ne">not equals</option>' +
            '<option value="gt">greater than</option><option value="lt">less than</option>' +
            '<option value="gte">≥ greater or equal</option><option value="lte">≤ less or equal</option>' +
            '<option value="contains">contains</option><option value="not_null">is not null</option></select>' +
            '<input type="text" name="filter_value" placeholder="Value…" class="input-field text-sm">'),
        ("deduplicate",    "Remove Duplicates",   sel_opt + '<p class="text-slate-500 text-xs mt-1">Leave blank to check all columns. Or enter comma-separated column names.</p>'),
        ("split_column",   "Split Column",         sel_req + '<input type="text" name="delimiter" placeholder="Delimiter (e.g. , or -)" class="input-field text-sm mb-2">' + '<input type="text" name="new_names" placeholder="New column names (comma-separated)" class="input-field text-sm">'),
        ("merge_columns",  "Merge Columns",        '<input type="text" name="columns" placeholder="col1, col2, col3" class="input-field text-sm mb-2">' + '<input type="text" name="delimiter" placeholder="Delimiter (space, - , etc)" class="input-field text-sm mb-2">' + '<input type="text" name="new_name" placeholder="New column name" class="input-field text-sm">'),
        ("strip_whitespace","Strip Whitespace",    sel_opt),
        ("to_uppercase",   "To UPPERCASE",         sel_req),
        ("to_lowercase",   "to lowercase",          sel_req),
        ("convert_numeric","Convert to Numeric",   sel_req),
    ]


@login_required
def cleaner(request, pk):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    ops = list(upload_obj.cleaning_ops.values('op_type', 'params', 'rows_before', 'rows_after', 'applied_at'))
    analysis = upload_obj.analysis_result or {}
    all_columns = [c['name'] for c in analysis.get('columns', [])]
    return render(request, 'cleaner/cleaner.html', {
        'upload': upload_obj,
        'columns': analysis.get('columns', []),
        'all_columns': all_columns,
        'op_forms': _op_forms(all_columns),
        'ops': ops,
        'row_count': upload_obj.row_count,
    })


@login_required
@require_POST
def apply_op(request, pk):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    op_type = request.POST.get('op_type')
    params = {}

    if op_type == 'drop_nulls':
        params = {'column': request.POST.get('column', '')}
    elif op_type == 'fill_nulls':
        params = {'column': request.POST.get('column'), 'value': request.POST.get('fill_value', '')}
    elif op_type == 'rename_column':
        params = {'old_name': request.POST.get('old_name'), 'new_name': request.POST.get('new_name')}
    elif op_type == 'drop_column':
        params = {'column': request.POST.get('column')}
    elif op_type == 'find_replace':
        params = {'column': request.POST.get('column', ''),
                  'find': request.POST.get('find', ''),
                  'replace': request.POST.get('replace', '')}
    elif op_type == 'filter_rows':
        params = {'column': request.POST.get('column'),
                  'operator': request.POST.get('operator', 'eq'),
                  'value': request.POST.get('filter_value', '')}
    elif op_type == 'deduplicate':
        params = {'columns': request.POST.get('column', '')}
    elif op_type == 'split_column':
        params = {'column':    request.POST.get('column'),
                  'delimiter': request.POST.get('delimiter', ','),
                  'new_names': request.POST.get('new_names', '')}
    elif op_type == 'merge_columns':
        params = {'columns':   request.POST.get('columns', ''),
                  'delimiter': request.POST.get('delimiter', ' '),
                  'new_name':  request.POST.get('new_name', 'merged')}
    elif op_type in ('strip_whitespace', 'to_uppercase', 'to_lowercase', 'convert_numeric'):
        params = {'column': request.POST.get('column', '')}
    elif op_type == 'deduplicate':
        params = {'columns': request.POST.get('column', '')}
    elif op_type == 'split_column':
        params = {'column': request.POST.get('column'),
                  'delimiter': request.POST.get('delimiter', ','),
                  'new_names': request.POST.get('new_names', '')}
    elif op_type == 'merge_columns':
        params = {'columns':   request.POST.get('columns', ''),
                  'delimiter': request.POST.get('delimiter', ' '),
                  'new_name':  request.POST.get('new_name', 'merged')}
    elif op_type in ('strip_whitespace', 'to_uppercase', 'to_lowercase', 'convert_numeric'):
        params = {'column': request.POST.get('column', '')}

    try:
        df = load_dataframe(upload_obj.file.path, upload_obj.file_type,
                            sheet_name=upload_obj.active_sheet or None)
        rows_before = len(df)

        # Apply all previous ops first
        prev_ops = [{'type': o.op_type, 'params': o.params} for o in upload_obj.cleaning_ops.all()]
        df = _apply_operations(df, prev_ops)
        df = _apply_operations(df, [{'type': op_type, 'params': params}])
        rows_after = len(df)

        CleaningOperation.objects.create(
            upload=upload_obj, op_type=op_type, params=params,
            rows_before=rows_before, rows_after=rows_after,
        )

        # Re-analyse and update
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='w') as f:
            df.to_csv(f, index=False)
            tmp_path = f.name
        result = analyse(tmp_path, 'csv')
        os.unlink(tmp_path)

        upload_obj.row_count = result['rows']
        upload_obj.column_count = result['cols']
        upload_obj.analysis_result = result
        upload_obj.save(update_fields=['row_count', 'column_count', 'analysis_result'])

        if request.htmx:
            from django.template.loader import render_to_string
            return HttpResponse(render_to_string('cleaner/partials/op_result.html', {
                'op_type': op_type, 'params': params,
                'rows_before': rows_before, 'rows_after': rows_after,
                'columns': result.get('columns', []),
                'all_columns': [c['name'] for c in result.get('columns', [])],
                'row_count': rows_after,
            }, request=request))
    except Exception as e:
        if request.htmx:
            return HttpResponse(f'<p class="text-red-400 text-sm">Error: {e}</p>')
        messages.error(request, str(e))

    return redirect('cleaner:cleaner', pk=pk)


@login_required
def export_cleaned(request, pk):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    try:
        df = load_dataframe(upload_obj.file.path, upload_obj.file_type,
                            sheet_name=upload_obj.active_sheet or None)
        ops = [{'type': o.op_type, 'params': o.params} for o in upload_obj.cleaning_ops.all()]
        df = _apply_operations(df, ops)

        fmt = request.GET.get('fmt', 'csv')
        if fmt == 'json':
            resp = HttpResponse(df.to_json(orient='records', indent=2), content_type='application/json')
            resp['Content-Disposition'] = f'attachment; filename="{upload_obj.original_name}_cleaned.json"'
        else:
            out = io.StringIO()
            df.to_csv(out, index=False)
            resp = HttpResponse(out.getvalue(), content_type='text/csv')
            resp['Content-Disposition'] = f'attachment; filename="{upload_obj.original_name}_cleaned.csv"'
        return resp
    except Exception as e:
        messages.error(request, str(e))
        return redirect('cleaner:cleaner', pk=pk)


@login_required
@require_POST
def reset_ops(request, pk):
    upload_obj = get_object_or_404(FileUpload, pk=pk, user=request.user)
    upload_obj.cleaning_ops.all().delete()
    # Re-analyse original
    try:
        result = analyse(upload_obj.file.path, upload_obj.file_type,
                         sheet_name=upload_obj.active_sheet or None)
        upload_obj.row_count = result['rows']
        upload_obj.column_count = result['cols']
        upload_obj.analysis_result = result
        upload_obj.save(update_fields=['row_count', 'column_count', 'analysis_result'])
    except Exception:
        pass
    messages.success(request, 'All cleaning operations reset.')
    return redirect('cleaner:cleaner', pk=pk)
