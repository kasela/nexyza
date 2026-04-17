"""Check notification rules against current upload analysis_result."""
from django.utils import timezone


def check_rules(upload) -> list:
    """
    Evaluate all active NotificationRule objects for this upload.
    Creates Notification records for triggered rules.
    Returns list of new Notification objects.
    """
    from .models import NotificationRule, Notification

    rules = NotificationRule.objects.filter(upload=upload, is_active=True)
    analysis = upload.analysis_result or {}
    cols = {c['name']: c for c in analysis.get('columns', [])}
    triggered = []

    for rule in rules:
        current_val = _get_metric(rule, cols, upload)
        if current_val is None:
            continue

        fired = _evaluate(current_val, rule.operator, rule.threshold)
        if not fired:
            continue

        title = f"Alert: {rule.name}"
        body  = (f"Column '{rule.column}' {rule.metric} = {current_val:.4g} "
                 f"({rule.get_operator_display()} {rule.threshold})")
        level = 'alert' if abs(current_val - rule.threshold) / max(abs(rule.threshold), 1) > 0.5 else 'warning'

        notif = Notification.objects.create(
            user=rule.user, rule=rule, upload=upload,
            level=level, title=title, body=body,
        )
        rule.last_triggered = timezone.now()
        rule.save(update_fields=['last_triggered'])
        triggered.append(notif)

        # Send email if Pro
        try:
            sub = getattr(rule.user, 'subscription', None)
            if sub and sub.is_active:
                _send_notification_email(rule.user, notif)
        except Exception:
            pass

    return triggered


def _get_metric(rule, cols: dict, upload) -> float | None:
    if rule.metric == 'row_count':
        return float(upload.row_count)
    col = cols.get(rule.column)
    if not col:
        return None
    mapping = {'mean': 'mean', 'max': 'max', 'min': 'min', 'null_pct': 'null_pct'}
    key = mapping.get(rule.metric)
    val = col.get(key)
    return float(val) if val is not None else None


def _evaluate(current: float, operator: str, threshold: float) -> bool:
    if operator == 'gt':  return current > threshold
    if operator == 'lt':  return current < threshold
    if operator == 'eq':  return abs(current - threshold) < 1e-9
    if operator == 'pct_change':
        if threshold == 0: return False
        return abs((current - threshold) / abs(threshold) * 100) >= threshold
    return False


def _send_notification_email(user, notif):
    from django.core.mail import send_mail
    from django.conf import settings
    send_mail(
        subject=f"Nexyza Alert: {notif.title}",
        message=notif.body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )
