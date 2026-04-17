from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404
from django.views.decorators.http import require_POST
from django.http import HttpResponse
from apps.analyser.models import FileUpload
from .models import AnomalyReport
from .engine import detect_anomalies, ai_anomaly_narrative


@login_required
def anomaly_report(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    report = AnomalyReport.objects.filter(upload=upload).first()
    return render(request, 'anomaly/report.html', {
        'upload': upload, 'report': report,
        'is_pro': getattr(getattr(request, 'subscription', None), 'is_active', False),
    })


@login_required
@require_POST
def run_detection(request, pk):
    upload = get_object_or_404(FileUpload, pk=pk, user=request.user)
    findings = detect_anomalies(upload)
    sub = getattr(request, 'subscription', None)

    summary = ''
    if sub and sub.is_active:
        try:
            summary = ai_anomaly_narrative(upload, findings)
        except Exception as e:
            summary = f"AI narrative unavailable: {e}"
    else:
        high = sum(1 for f in findings if f['severity'] == 'high')
        med  = sum(1 for f in findings if f['severity'] == 'medium')
        summary = f"Found {len(findings)} issue(s): {high} high, {med} medium severity."

    report, _ = AnomalyReport.objects.update_or_create(
        upload=upload,
        defaults={'findings': findings, 'summary': summary},
    )
    # Fire webhook if anomalies found
    if findings:
        try:
            from apps.webhooks.dispatcher import fire_event
            high = sum(1 for f in findings if f['severity'] == 'high')
            fire_event('anomaly.detected', request.user, {
                'upload_id': upload.id,
                'filename':  upload.original_name,
                'total':     len(findings),
                'high':      high,
                'summary':   summary[:200],
            })
        except Exception:
            pass

    if request.htmx:
        from django.template.loader import render_to_string
        return HttpResponse(render_to_string('anomaly/partials/findings.html',
                                              {'report': report, 'upload': upload}, request=request))
    return render(request, 'anomaly/report.html', {
        'upload': upload, 'report': report,
        'is_pro': sub.is_active if sub else False,
    })
