from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.contrib import messages
from apps.analyser.models import FileUpload
from .models import Forecast
from .engine import run_forecast, ai_forecast_narrative


@login_required
def forecast_view(request, pk):
    upload  = get_object_or_404(FileUpload, pk=pk, user=request.user)
    analysis = upload.analysis_result or {}
    cols     = analysis.get('columns', [])
    numeric  = [c for c in cols if c.get('is_numeric')]
    all_cols = [c['name'] for c in cols]
    existing = Forecast.objects.filter(upload=upload).order_by('-created_at')[:5]
    return render(request, 'forecasting/forecast.html', {
        'upload': upload, 'numeric_columns': numeric,
        'all_columns': all_cols, 'existing': existing,
        'methods': Forecast.METHOD_CHOICES,
    })


@login_required
@require_POST
def run(request, pk):
    upload    = get_object_or_404(FileUpload, pk=pk, user=request.user)
    date_col  = request.POST.get('date_column', '')
    value_col = request.POST.get('value_column', '')
    periods   = min(int(request.POST.get('periods', 6)), 24)
    method    = request.POST.get('method', 'linear')

    if not date_col or not value_col:
        return JsonResponse({'error': 'Select both date and value columns'}, status=400)

    try:
        data = run_forecast(upload, date_col, value_col, periods, method)
        narrative = ''
        try:
            narrative = ai_forecast_narrative(upload, data)
        except Exception:
            pass

        fc = Forecast.objects.create(
            upload=upload, date_column=date_col, value_column=value_col,
            periods=periods, method=method,
            forecast_data=data, ai_narrative=narrative,
        )

        if request.htmx:
            from django.template.loader import render_to_string
            return JsonResponse({
                'html': render_to_string('forecasting/partials/result.html',
                                         {'fc': fc, 'upload': upload}, request=request)
            })
        return JsonResponse({'id': fc.id, 'data': data})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
