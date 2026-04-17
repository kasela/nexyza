"""
Django-Q tasks for sending scheduled email reports.
Queue with: from django_q.tasks import async_task; async_task('apps.reports.tasks.send_report', report_id)
"""
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string


def send_report(report_id: int):
    from .models import ScheduledReport
    try:
        report = ScheduledReport.objects.select_related('user').prefetch_related('uploads').get(id=report_id)
    except ScheduledReport.DoesNotExist:
        return

    if not report.is_active:
        return

    uploads = list(report.uploads.filter(status='done'))
    if not uploads:
        return

    summaries = []
    for u in uploads:
        analysis = u.analysis_result or {}
        entry = {
            'name': u.original_name,
            'rows': u.row_count,
            'cols': u.column_count,
            'url': f"{settings.SITE_URL}/workspace/{u.id}/",
            'columns': analysis.get('columns', [])[:5],
        }
        if report.include_ai_summary and u.ai_insights:
            entry['ai_summary'] = u.ai_insights[:600] + '…' if len(u.ai_insights) > 600 else u.ai_insights
        summaries.append(entry)

    subject = f"Nexyza Report: {report.name} — {timezone.now().strftime('%b %d, %Y')}"
    html_body = render_to_string('reports/email_report.html', {
        'report': report,
        'summaries': summaries,
        'generated_at': timezone.now(),
    })
    text_body = f"Nexyza Report: {report.name}\n\n" + \
                '\n'.join(f"- {s['name']}: {s['rows']} rows, {s['cols']} cols" for s in summaries)

    send_mail(
        subject=subject,
        message=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[report.recipient_email],
        html_message=html_body,
        fail_silently=False,
    )

    report.last_sent = timezone.now()
    report.save(update_fields=['last_sent'])


def schedule_pending_reports():
    """Called by Django-Q schedule. Finds reports due and dispatches them."""
    from .models import ScheduledReport
    from django_q.tasks import async_task

    now = timezone.now()
    due = ScheduledReport.objects.filter(is_active=True, next_send__lte=now)
    for report in due:
        async_task('apps.reports.tasks.send_report', report.id)
        _set_next_send(report)
        report.save(update_fields=['next_send'])


def _set_next_send(report):
    from datetime import timedelta
    now = timezone.now()
    if report.frequency == 'weekly':
        days_ahead = report.send_day - now.weekday()
        if days_ahead <= 0:
            days_ahead += 7
        report.next_send = now.replace(hour=report.send_hour, minute=0, second=0, microsecond=0) + timedelta(days=days_ahead)
    else:  # monthly
        from calendar import monthrange
        day = min(report.send_day, monthrange(now.year, now.month)[1])
        next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
        report.next_send = next_month.replace(day=day, hour=report.send_hour, minute=0, second=0, microsecond=0)
