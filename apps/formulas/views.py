from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from apps.analyser.models import FileUpload
from apps.analyser.engine import load_dataframe
from .models import ComputedColumn
from .engine import preview_expression, apply_computed_columns


@login_required
def formula_editor(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    cols = [c['name'] for c in (upload.analysis_result or {}).get('columns', [])]
    computed = upload.computed_cols.filter(is_active=True)
    return render(request, 'formulas/editor.html', {
        'upload': upload, 'columns': cols, 'computed': computed,
    })


@login_required
@require_POST
def preview(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    expr = request.POST.get('expression', '')
    try:
        df = load_dataframe(upload.file.path, upload.file_type,
                            sheet_name=upload.active_sheet or None)
        result = preview_expression(df, expr)
    except Exception as e:
        result = {'ok': False, 'error': str(e)}
    if request.htmx:
        if result['ok']:
            sample = ', '.join(result['sample'][:5])
            return HttpResponse(
                f'<div class="p-3 bg-green-900/20 border border-green-700/30 rounded-xl text-sm">'
                f'<p class="text-green-300 font-medium">✓ Valid — dtype: {result["dtype"]}</p>'
                f'<p class="text-slate-400 text-xs mt-1">Sample: {sample}</p></div>'
            )
        return HttpResponse(
            f'<div class="p-3 bg-red-900/20 border border-red-700/30 rounded-xl text-red-300 text-sm">'
            f'✗ {result["error"]}</div>'
        )
    return JsonResponse(result)


@login_required
@require_POST
def save_formula(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    name   = request.POST.get('col_name', '').strip()
    expr   = request.POST.get('expression', '').strip()
    desc   = request.POST.get('description', '')

    if not name or not expr:
        messages.error(request, 'Column name and expression required.')
        return redirect('formulas:editor', pk=pk)

    ComputedColumn.objects.update_or_create(
        upload=upload, name=name,
        defaults={'expression': expr, 'description': desc, 'is_active': True},
    )
    messages.success(request, f'Column "{name}" added.')
    # Rebuild analysis with new column
    try:
        df = load_dataframe(upload.file.path, upload.file_type,
                            sheet_name=upload.active_sheet or None)
        df = apply_computed_columns(df, upload.computed_cols.filter(is_active=True))
        import tempfile, os
        from apps.analyser.engine import analyse
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False, mode='w') as f:
            df.to_csv(f, index=False); tmp = f.name
        result = analyse(tmp, 'csv')
        os.unlink(tmp)
        upload.analysis_result = result
        upload.row_count = result['rows']
        upload.column_count = result['cols']
        upload.save(update_fields=['analysis_result', 'row_count', 'column_count'])
    except Exception:
        pass
    return redirect('formulas:editor', pk=pk)


@login_required
@require_POST
def delete_formula(request, pk, col_id):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    ComputedColumn.objects.filter(pk=col_id, upload=upload).delete()
    messages.success(request, 'Column removed.')
    return redirect('formulas:editor', pk=pk)
