"""Fire webhooks for Nexyza events."""
import json
import hmac
import hashlib
import requests
from django.utils import timezone
from django.conf import settings


def fire_event(event: str, user, payload: dict):
    """Fire all active webhooks for this user + event."""
    from .models import Webhook, WebhookDelivery

    webhooks = Webhook.objects.filter(user=user, is_active=True)
    for wh in webhooks:
        if event not in wh.events:
            continue
        body = json.dumps({'event': event, 'data': payload, 'timestamp': timezone.now().isoformat()})
        headers = {
            'Content-Type': 'application/json',
            'X-Nexyza-Event': event,
            'X-Nexyza-Delivery': f"{wh.id}-{timezone.now().timestamp()}",
        }
        if wh.secret:
            sig = hmac.new(wh.secret.encode(), body.encode(), hashlib.sha256).hexdigest()
            headers['X-Nexyza-Signature'] = sig

        timeout = getattr(settings, 'WEBHOOK_TIMEOUT_SECONDS', 10)
        delivery = WebhookDelivery(webhook=wh, event=event, payload=payload)
        try:
            resp = requests.post(wh.url, data=body, headers=headers, timeout=timeout)
            delivery.status      = WebhookDelivery.STATUS_OK if resp.ok else WebhookDelivery.STATUS_FAIL
            delivery.status_code = resp.status_code
            delivery.response    = resp.text[:500]
            if resp.ok:
                wh.success_count += 1
            else:
                wh.failure_count += 1
        except Exception as e:
            delivery.status   = WebhookDelivery.STATUS_FAIL
            delivery.response = str(e)[:500]
            wh.failure_count += 1
        finally:
            wh.last_fired = timezone.now()
            wh.save(update_fields=['last_fired','success_count','failure_count'])
            delivery.save()
