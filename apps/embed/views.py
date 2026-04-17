from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.clickjacking import xframe_options_exempt
from django.views.decorators.cache import cache_page
from django.conf import settings
from apps.analyser.models import ChartConfig, FileUpload


@xframe_options_exempt
def embed_chart(request, chart_id, token):
    """Renders a single chart in a minimal iframe-safe page."""
    upload = get_object_or_404(FileUpload, share_token=token, share_enabled=True)
    chart  = get_object_or_404(ChartConfig, pk=chart_id, upload=upload)

    from django.utils import timezone
    if upload.share_expires and upload.share_expires < timezone.now():
        return HttpResponse('<p style="color:#f87171;font-family:sans-serif;padding:1rem">Share link expired.</p>')

    return render(request, 'embed/chart.html', {'chart': chart, 'upload': upload})


@xframe_options_exempt
def embed_dashboard(request, token):
    """Renders all charts for a shared upload in a scrollable iframe."""
    upload = get_object_or_404(FileUpload, share_token=token, share_enabled=True)
    from django.utils import timezone
    if upload.share_expires and upload.share_expires < timezone.now():
        return HttpResponse('<p style="color:#f87171;font-family:sans-serif;padding:1rem">Share link expired.</p>')
    charts = upload.chart_configs.all().order_by('sort_order')
    return render(request, 'embed/dashboard.html', {'upload': upload, 'charts': charts})


def embed_snippet(request, token):
    """Returns the JS/iframe embed code for a shared upload."""
    upload = get_object_or_404(FileUpload, share_token=token, share_enabled=True)
    base   = request.build_absolute_uri('/')[:-1]
    iframe_url  = f"{base}/embed/dashboard/{token}/"
    chart_urls  = [
        {'title': c.title, 'url': f"{base}/embed/chart/{c.id}/{token}/"}
        for c in upload.chart_configs.all()[:20]
    ]
    snippet = f'<iframe src="{iframe_url}" width="100%" height="600" frameborder="0" style="border-radius:12px;"></iframe>'
    return JsonResponse({
        'iframe_url': iframe_url,
        'snippet': snippet,
        'charts': chart_urls,
    })
