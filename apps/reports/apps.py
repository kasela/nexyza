from django.apps import AppConfig


class ReportsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.reports'

    def ready(self):
        from django.db.models.signals import post_migrate
        post_migrate.connect(_create_q_schedule, sender=self)


def _create_q_schedule(sender, **kwargs):
    try:
        from django_q.models import Schedule
        Schedule.objects.get_or_create(
            func='apps.reports.tasks.schedule_pending_reports',
            defaults={
                'name': 'Check Scheduled Reports',
                'schedule_type': Schedule.HOURLY,
                'repeats': -1,
            }
        )
    except Exception:
        pass
