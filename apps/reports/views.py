from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
from django.utils import timezone
from datetime import timedelta
from apps.analyser.models import FileUpload
from .models import ScheduledReport
from .tasks import send_report, _set_next_send


@login_required
def report_list(request):
    reports = ScheduledReport.objects.filter(user=request.user)
    uploads = FileUpload.objects.filter(user=request.user, status='done')
    return render(request, 'reports/list.html', {'reports': reports, 'uploads': uploads})


@login_required
@require_POST
def create_report(request):
    name  = request.POST.get('name', 'My Report')
    freq  = request.POST.get('frequency', 'weekly')
    day   = int(request.POST.get('send_day', 0))
    hour  = int(request.POST.get('send_hour', 8))
    email = request.POST.get('recipient_email', request.user.email)
    ai    = request.POST.get('include_ai_summary') == 'on'
    upload_ids = request.POST.getlist('uploads')

    report = ScheduledReport.objects.create(
        user=request.user, name=name, frequency=freq,
        send_day=day, send_hour=hour, recipient_email=email,
        include_ai_summary=ai,
    )
    if upload_ids:
        report.uploads.set(FileUpload.objects.filter(id__in=upload_ids, user=request.user))
    _set_next_send(report)
    report.save(update_fields=['next_send'])

    messages.success(request, f'Report "{name}" scheduled ({freq}).')
    return redirect('reports:list')


@login_required
@require_POST
def send_now(request, pk):
    report = get_object_or_404(ScheduledReport, pk=pk, user=request.user)
    try:
        send_report(report.id)
        messages.success(request, f'Report "{report.name}" sent to {report.recipient_email}.')
    except Exception as e:
        messages.error(request, f'Send failed: {e}')
    return redirect('reports:list')


@login_required
@require_POST
def toggle_report(request, pk):
    report = get_object_or_404(ScheduledReport, pk=pk, user=request.user)
    report.is_active = not report.is_active
    report.save(update_fields=['is_active'])
    return redirect('reports:list')


@login_required
@require_POST
def delete_report(request, pk):
    get_object_or_404(ScheduledReport, pk=pk, user=request.user).delete()
    messages.success(request, 'Report deleted.')
    return redirect('reports:list')
