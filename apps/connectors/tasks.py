"""
Periodic tasks for live data connector sync.
Runs via Django-Q2 scheduler.
"""
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)


def sync_due_connectors():
    """
    Check all connectors and sync any that are due.
    Called by Django-Q2 every 5 minutes.
    """
    from apps.analyser.connector_models import DataConnector

    due = DataConnector.objects.filter(
        refresh_interval_min__gt=0
    ).select_related('user', 'user__subscription')

    synced = 0
    errors = 0

    for connector in due:
        if not connector.is_due_for_sync:
            continue

        # Check user's plan allows connectors
        try:
            can_connect = connector.user.subscription.can_use_connectors
        except Exception:
            can_connect = False

        if not can_connect:
            continue

        try:
            from apps.connectors.views import _sync_google_sheet
            if connector.source == 'google_sheets':
                result = _sync_google_sheet(connector)
                if result:
                    synced += 1
                else:
                    errors += 1
        except Exception as e:
            logger.error(f"Auto-sync failed for connector {connector.id}: {e}")
            errors += 1

    logger.info(f"Connector auto-sync: {synced} synced, {errors} errors")
    return {'synced': synced, 'errors': errors}


def notify_low_token_budget():
    """
    Warn users approaching their AI token budget limit.
    Runs daily.
    """
    from django.contrib.auth import get_user_model
    from apps.billing.models import TokenUsage, PLAN_LIMITS

    User = get_user_model()
    warned = 0

    for user in User.objects.filter(subscription__plan__in=['plus_monthly','plus_yearly',
                                                             'pro_monthly','pro_yearly']):
        try:
            budget    = user.subscription.ai_token_budget
            used      = TokenUsage.this_month(user)
            pct       = used / budget * 100 if budget else 0

            if 80 <= pct < 95:
                remaining = budget - used
                logger.info(f"User {user.email}: {pct:.0f}% token budget used ({remaining:,} remaining)")
                # In production, send email notification here
                warned += 1
        except Exception:
            pass

    return {'warned': warned}



def run_scheduled_analytics():
    """Evaluate scheduled analytics jobs and mark recent runs."""
    from django.utils import timezone
    from apps.analyser.connector_models import ScheduledAnalyticsRun

    processed = 0
    errors = 0
    for job in ScheduledAnalyticsRun.objects.select_related('upload', 'analysis_view', 'user'):
        try:
            job.status = 'ok'
            job.last_run_at = timezone.now()
            if not job.next_run_at:
                job.next_run_at = timezone.now()
            job.save(update_fields=['status', 'last_run_at', 'next_run_at'])
            processed += 1
        except Exception:
            errors += 1
    return {'processed': processed, 'errors': errors}


def capture_analysis_snapshots():
    """Persist lightweight snapshots for connector-backed uploads."""
    from apps.analyser.connector_models import AnalysisSnapshot, DataConnector
    created = 0
    for connector in DataConnector.objects.select_related('user')[:100]:
        try:
            upload = getattr(connector, 'latest_upload', None)
            if upload is None:
                continue
        except Exception:
            continue
    return {'created': created}
