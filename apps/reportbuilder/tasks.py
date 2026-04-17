"""
Scheduled report delivery tasks — runs via Django-Q2.
"""
import logging
logger = logging.getLogger(__name__)


def send_scheduled_reports():
    """Check all scheduled reports and send those due. Runs every 15 minutes."""
    from django.utils import timezone
    from .models import Report, ScheduledReport

    due  = ScheduledReport.objects.filter(
        is_active=True, next_send_at__lte=timezone.now()
    ).select_related('report', 'user')

    sent = 0
    for schedule in due:
        try:
            _deliver_report(schedule)
            schedule.last_sent_at = timezone.now()
            schedule.run_count   += 1
            schedule.schedule_next()
            schedule.save(update_fields=['last_sent_at', 'run_count', 'next_send_at'])
            sent += 1
        except Exception as e:
            logger.error(f"Report delivery failed (schedule {schedule.id}): {e}")

    logger.info(f"Scheduled reports: {sent} delivered")
    return {'sent': sent}


def _deliver_report(schedule):
    from django.core.mail import EmailMultiAlternatives
    from django.conf import settings as s

    report = schedule.report
    email  = schedule.email or schedule.user.email
    if not email:
        return

    subject   = f"[Nexyza] {report.title}"
    text_body = f"Your scheduled report '{report.title}' is attached."

    if report.is_public and report.share_token:
        site = getattr(s, 'SITE_URL', 'http://localhost:8000')
        text_body += f"\n\nView online: {site}/reports/view/{report.share_token}/"

    msg = EmailMultiAlternatives(
        subject=subject, body=text_body,
        from_email=getattr(s, 'DEFAULT_FROM_EMAIL', 'hello@nexyza.com'),
        to=[email],
    )
    try:
        from .views import _build_report_pdf
        pdf  = _build_report_pdf(report)
        fname = report.title.replace(' ', '_')[:40] + '.pdf'
        msg.attach(fname, pdf, 'application/pdf')
    except Exception as e:
        logger.warning(f"PDF attachment failed: {e}")

    msg.send()
