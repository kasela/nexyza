import json
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.contrib import messages
from django.utils import timezone
from .models import APIKey
from .auth import api_key_required
from apps.analyser.models import FileUpload
from apps.analyser.engine import analyse
import tempfile, os


# ── Key management (web UI) ───────────────────────────────────────────────────

@login_required
def key_list(request):
    keys = APIKey.objects.filter(user=request.user)
    endpoints = [
        ('GET',    '/api/v1/uploads/',         'List all analysed files'),
        ('POST',   '/api/v1/upload/',           'Upload and analyse a new file'),
        ('GET',    '/api/v1/uploads/{id}/',     'Get full analysis result'),
        ('GET',    '/api/v1/uploads/{id}/charts/', 'Get chart configs'),
        ('DELETE', '/api/v1/uploads/{id}/delete/', 'Delete an upload'),
    ]
    return render(request, 'api/keys.html', {'keys': keys, 'api_endpoints': endpoints})


@login_required
def create_key(request):
    if request.method == 'POST':
        name = request.POST.get('name', 'Default')
        key = APIKey.generate(request.user, name=name)
        messages.success(request, f'API key created. Copy it now — it won\'t be shown again.')
        return render(request, 'api/key_created.html', {'key': key, 'raw': key.display_key()})
    return redirect('api:keys')


@login_required
def revoke_key(request, pk):
    if request.method == 'POST':
        APIKey.objects.filter(pk=pk, user=request.user).update(is_active=False)
        messages.success(request, 'API key revoked.')
    return redirect('api:keys')


# ── REST Endpoints ────────────────────────────────────────────────────────────

@csrf_exempt
@api_key_required
@require_http_methods(['GET'])
def api_uploads_list(request):
    uploads = FileUpload.objects.filter(user=request.api_user, status='done').values(
        'id', 'original_name', 'file_type', 'file_size', 'row_count', 'column_count', 'created_at'
    )
    return JsonResponse({'uploads': list(uploads)})


@csrf_exempt
@api_key_required
@require_http_methods(['GET'])
def api_upload_detail(request, pk):
    from django.core.exceptions import ObjectDoesNotExist
    try:
        upload = FileUpload.objects.get(pk=pk, user=request.api_user)
    except ObjectDoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    return JsonResponse({
        'id': upload.id,
        'original_name': upload.original_name,
        'file_type': upload.file_type,
        'file_size': upload.file_size,
        'row_count': upload.row_count,
        'column_count': upload.column_count,
        'status': upload.status,
        'created_at': upload.created_at.isoformat(),
        'analysis': upload.analysis_result,
        'ai_insights': upload.ai_insights,
    })


@csrf_exempt
@api_key_required
@require_http_methods(['POST'])
def api_upload_file(request):
    file = request.FILES.get('file')
    if not file:
        return JsonResponse({'error': 'No file provided'}, status=400)

    ext = os.path.splitext(file.name)[1].lower()
    type_map = {'.csv': 'csv', '.xlsx': 'excel', '.xls': 'excel', '.json': 'json'}
    file_type = type_map.get(ext)
    if not file_type:
        return JsonResponse({'error': 'Unsupported file type'}, status=400)

    upload = FileUpload.objects.create(
        user=request.api_user, file=file, original_name=file.name,
        file_type=file_type, file_size=file.size, status='processing',
    )
    try:
        result = analyse(upload.file.path, file_type)
        upload.analysis_result = result
        upload.row_count = result['rows']
        upload.column_count = result['cols']
        upload.status = 'done'
        upload.save()
        from apps.analyser.charts import auto_generate_charts
        auto_generate_charts(upload)
    except Exception as e:
        upload.status = 'error'
        upload.error_message = str(e)
        upload.save()
        return JsonResponse({'error': str(e)}, status=500)

    return JsonResponse({'id': upload.id, 'status': 'done',
                         'rows': upload.row_count, 'cols': upload.column_count}, status=201)


@csrf_exempt
@api_key_required
@require_http_methods(['GET'])
def api_upload_charts(request, pk):
    from django.core.exceptions import ObjectDoesNotExist
    try:
        upload = FileUpload.objects.get(pk=pk, user=request.api_user)
    except ObjectDoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
    charts = upload.chart_configs.values('id', 'title', 'chart_type', 'x_axis', 'y_axis',
                                          'aggregation', 'color', 'size', 'cached_data')
    return JsonResponse({'charts': list(charts)})


@csrf_exempt
@api_key_required
@require_http_methods(['DELETE'])
def api_upload_delete(request, pk):
    from django.core.exceptions import ObjectDoesNotExist
    try:
        upload = FileUpload.objects.get(pk=pk, user=request.api_user)
        upload.file.delete(save=False)
        upload.delete()
        return JsonResponse({'deleted': True})
    except ObjectDoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)
