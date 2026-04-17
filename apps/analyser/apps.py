from django.apps import AppConfig

class AnalyserConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.analyser'

    def ready(self):
        try:
            from django.db.models.signals import post_migrate
            post_migrate.connect(_create_delivery_schedule, sender=self)
        except Exception:
            return


def _create_delivery_schedule(sender, **kwargs):
    try:
        from django_q.models import Schedule
        Schedule.objects.get_or_create(
            func='apps.analyser.scheduled_delivery_tasks.run_scheduled_deliveries',
            defaults={'name': 'Scheduled Analytics Delivery', 'schedule_type': Schedule.HOURLY},
        )
    except Exception:
        pass
