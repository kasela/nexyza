from typing import Any, Dict


def build_schedule_summary(schedules) -> Dict[str, Any]:
    schedules = list(schedules)
    return {
        'scheduled_reports': len(schedules),
        'email_deliveries': sum(1 for s in schedules if getattr(s, 'delivery_mode', '') == 'email'),
        'active': sum(1 for s in schedules if getattr(s, 'status', '') in {'queued', 'ok', 'running'}),
    }
