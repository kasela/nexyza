from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.contrib import messages
import secrets
from .models import Webhook, WebhookDelivery


@login_required
def webhook_list(request):
    hooks     = Webhook.objects.filter(user=request.user).prefetch_related('deliveries')
    return render(request, 'webhooks/list.html', {
        'hooks': hooks,
        'event_choices': Webhook.EVENT_CHOICES,
    })


@login_required
@require_POST
def create_webhook(request):
    events = request.POST.getlist('events')
    Webhook.objects.create(
        user=request.user,
        name=request.POST.get('name', 'My Webhook'),
        url=request.POST.get('url', ''),
        events=events,
        secret=request.POST.get('secret') or secrets.token_hex(20),
    )
    messages.success(request, 'Webhook created.')
    return redirect('webhooks:list')


@login_required
@require_POST
def toggle_webhook(request, pk):
    wh = get_object_or_404(Webhook, pk=pk, user=request.user)
    wh.is_active = not wh.is_active
    wh.save(update_fields=['is_active'])
    return redirect('webhooks:list')


@login_required
@require_POST
def delete_webhook(request, pk):
    get_object_or_404(Webhook, pk=pk, user=request.user).delete()
    messages.success(request, 'Webhook deleted.')
    return redirect('webhooks:list')


@login_required
def delivery_log(request, pk):
    wh = get_object_or_404(Webhook, pk=pk, user=request.user)
    deliveries = wh.deliveries.all()[:50]
    return render(request, 'webhooks/deliveries.html', {'hook': wh, 'deliveries': deliveries})


@login_required
@require_POST
def test_webhook(request, pk):
    """Send a test payload."""
    from .dispatcher import fire_event
    wh = get_object_or_404(Webhook, pk=pk, user=request.user)
    fire_event('upload.done', request.user, {
        'test': True, 'upload_id': 0,
        'filename': 'test_file.csv', 'rows': 100, 'cols': 5,
    })
    messages.success(request, f'Test payload sent to {wh.url}.')
    return redirect('webhooks:list')
