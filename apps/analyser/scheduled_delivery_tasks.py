from django.utils import timezone
import logging
logger = logging.getLogger(__name__)


def run_scheduled_deliveries():
    from .connector_models import ScheduledAnalyticsRun
    from .scheduled_delivery_engine import deliver_schedule
    due = ScheduledAnalyticsRun.objects.filter(next_run_at__lte=timezone.now()).select_related('upload', 'user')
    sent = 0
    failed = 0
    for schedule in due:
        try:
            schedule.status = 'running'
            schedule.save(update_fields=['status', 'updated_at'])
            deliver_schedule(schedule)
            sent += 1
        except Exception as e:
            failed += 1
            logger.exception('Scheduled delivery failed for %s', schedule.id)
            schedule.status = 'error'
            schedule.last_error = str(e)[:1000]
            schedule.last_run_at = timezone.now()
            schedule.save(update_fields=['status', 'last_error', 'last_run_at', 'updated_at'])
    return {'sent': sent, 'failed': failed}
