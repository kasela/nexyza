"""
Billing views: pricing, checkout, portal, webhooks, token usage API.
"""
import hashlib, hmac, json, requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.utils.dateparse import parse_datetime
from .models import Subscription, Plan, WebhookEvent, TokenUsage, PLAN_LIMITS


FREE_FEATURES = [
    '5 file uploads / month',
    '2 MB max file size',
    'CSV, Excel & JSON',
    'Interactive charts (rule-based)',
    'Basic statistics & previews',
    '1 dashboard',
    'CSV / JSON export',
]

PLUS_FEATURES = [
    '50 uploads / month',
    '25 MB max file size',
    'Everything in Free',
    '🤖 AI chart generation',
    '200,000 AI tokens / month',
    'Google Sheets live connector',
    'Excel Online live connector',
    'Auto-refresh dashboards (hourly)',
    '10 dashboards · 3 collaborators',
    'XLSX & PDF export',
    'Email support',
]

PRO_FEATURES = [
    'Unlimited uploads',
    '100 MB max file size',
    'Everything in Plus',
    '2,000,000 AI tokens / month',
    'All connectors',
    'Auto-refresh every 5 minutes',
    'Unlimited dashboards',
    'Unlimited collaborators',
    'PPTX export',
    'Priority support',
    'Whitelabel reports',
    'API access',
]

COMPARISON_ROWS = [
    {'feature': 'Uploads / month',         'free': '5',          'plus': '50',          'pro': 'Unlimited'},
    {'feature': 'Max file size',            'free': '2 MB',       'plus': '25 MB',       'pro': '100 MB'},
    {'feature': 'Max rows per file',        'free': '10,000',     'plus': '500,000',     'pro': 'Unlimited'},
    {'feature': 'AI chart generation',      'free': '✗',          'plus': '✓',           'pro': '✓'},
    {'feature': 'AI tokens / month',        'free': '—',          'plus': '200,000',     'pro': '2,000,000'},
    {'feature': 'Google Sheets connector',  'free': '✗',          'plus': '✓',           'pro': '✓'},
    {'feature': 'Excel Online connector',   'free': '✗',          'plus': '✓',           'pro': '✓'},
    {'feature': 'Auto-refresh dashboards',  'free': '✗',          'plus': 'Hourly',      'pro': 'Every 5 min'},
    {'feature': 'Dashboards',               'free': '1',          'plus': '10',          'pro': 'Unlimited'},
    {'feature': 'Collaborators',            'free': '—',          'plus': '3',           'pro': 'Unlimited'},
    {'feature': 'Export formats',           'free': 'CSV / JSON', 'plus': '+ XLSX / PDF','pro': '+ PPTX'},
    {'feature': 'Support',                  'free': 'Community',  'plus': 'Email',       'pro': 'Priority'},
    {'feature': 'API access',               'free': '✗',          'plus': '✗',           'pro': '✓'},
    {'feature': 'Whitelabel reports',       'free': '✗',          'plus': '✗',           'pro': '✓'},
]

FAQS = [
    {'q': 'Can I cancel anytime?',
     'a': 'Yes — cancel anytime from your billing portal. You keep access until the end of your billing period.'},
    {'q': 'What counts as an AI token?',
     'a': 'Each AI chart generation uses ~1,500–3,000 tokens. Your monthly budget resets on the 1st. Pro users get ~2,000 generations/month.'},
    {'q': 'What are live connectors?',
     'a': 'Connect Google Sheets or Excel Online and Nexyza automatically pulls fresh data on your chosen schedule — no manual re-uploading.'},
    {'q': 'How does auto-refresh work?',
     'a': 'On Plus, dashboards refresh every hour. On Pro, every 5 minutes. Charts update automatically when new data arrives.'},
    {'q': 'Can I switch plans?',
     'a': 'Yes — upgrade or downgrade any time. Upgrades take effect immediately; downgrades at the next billing cycle.'},
    {'q': 'What payment methods are accepted?',
     'a': 'All major credit/debit cards via LemonSqueezy, a trusted payment processor. No PayPal required.'},
    {'q': 'Is there a trial period?',
     'a': 'The Free plan is free forever. Paid plans start immediately — if you\'re not satisfied in the first 7 days, contact us for a refund.'},
    {'q': 'Is my data secure?',
     'a': 'Files are processed in isolation and never shared. You can delete your data any time from your dashboard.'},
]


# ── Pricing ───────────────────────────────────────────────────────────────────

def pricing(request):
    return render(request, 'billing/pricing.html', {
        'free_features':    FREE_FEATURES,
        'plus_features':    PLUS_FEATURES,
        'pro_features':     PRO_FEATURES,
        'comparison_rows':  COMPARISON_ROWS,
        'faqs':             FAQS,
        'billing_enabled':  getattr(settings, 'BILLING_ENABLED', False),
    })


# ── Checkout ──────────────────────────────────────────────────────────────────

VARIANT_MAP = {
    'plus_monthly': 'LEMONSQUEEZY_PLUS_MONTHLY_VARIANT_ID',
    'plus_yearly':  'LEMONSQUEEZY_PLUS_YEARLY_VARIANT_ID',
    'pro_monthly':  'LEMONSQUEEZY_PRO_MONTHLY_VARIANT_ID',
    'pro_yearly':   'LEMONSQUEEZY_PRO_YEARLY_VARIANT_ID',
    # Legacy
    'monthly':      'LEMONSQUEEZY_PRO_MONTHLY_VARIANT_ID',
    'yearly':       'LEMONSQUEEZY_PRO_YEARLY_VARIANT_ID',
}


@login_required
def checkout(request, plan_key='pro_monthly'):
    if not getattr(settings, 'BILLING_ENABLED', False):
        return render(request, 'billing/checkout_unavailable.html',
                      {'plan_key': plan_key, 'reason': 'coming_soon'})
    variant_setting = VARIANT_MAP.get(plan_key)
    if not variant_setting:
        return redirect('billing:pricing')
    variant_id = getattr(settings, variant_setting, '')
    if not variant_id:
        return render(request, 'billing/checkout_unavailable.html',
                      {'plan_key': plan_key, 'reason': 'not_configured'})
    store_id = settings.LEMONSQUEEZY_STORE_ID
    checkout_url = (
        f"https://store.lemonsqueezy.com/checkout/buy/{variant_id}"
        f"?checkout[email]={request.user.email}"
        f"&checkout[custom][user_id]={request.user.id}"
    )
    return redirect(checkout_url)


# ── Billing portal ────────────────────────────────────────────────────────────

@login_required
def portal(request):
    sub = getattr(request.user, 'subscription', None)
    if sub and sub.ls_customer_id:
        resp = requests.post(
            f'https://api.lemonsqueezy.com/v1/customers/{sub.ls_customer_id}/portal',
            headers={'Authorization': f'Bearer {settings.LEMONSQUEEZY_API_KEY}',
                     'Accept': 'application/vnd.api+json'},
            timeout=10,
        )
        if resp.ok:
            portal_url = resp.json().get('data', {}).get('attributes', {}).get('urls', {}).get('customer_portal')
            if portal_url:
                return redirect(portal_url)
    return redirect('billing:pricing')


# ── Token usage API ───────────────────────────────────────────────────────────

@login_required
def token_usage(request):
    """Return current month's token usage — HTML for HTMX, JSON for API."""
    user = request.user
    used = TokenUsage.this_month(user)
    try:
        budget = user.subscription.ai_token_budget
        plan   = user.subscription.plan_key
    except Exception:
        budget, plan = 0, 'free'

    remaining = max(0, budget - used) if budget else 0
    pct       = round(used / budget * 100, 1) if budget else 0

    if request.headers.get('HX-Request') or request.GET.get('format') != 'json':
        if budget == 0:
            html = '''<div style="color:#64748b;font-size:13px;">
              AI features are not available on the Free plan.
              <a href="/billing/pricing/" style="color:#a78bfa;">Upgrade to Plus →</a>
            </div>'''
        else:
            bar_color = '#34d399' if pct < 70 else ('#fbbf24' if pct < 90 else '#f87171')
            html = f'''
            <div>
              <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:6px;">
                <span style="color:#94a3b8;">{used:,} / {budget:,} tokens used</span>
                <span style="color:{bar_color};font-weight:600;">{pct}%</span>
              </div>
              <div style="height:6px;background:rgba(51,65,85,.6);border-radius:999px;overflow:hidden;">
                <div style="height:100%;width:{min(pct,100)}%;background:{bar_color};border-radius:999px;transition:.3s;"></div>
              </div>
              <div style="display:flex;justify-content:space-between;font-size:11px;margin-top:5px;">
                <span style="color:#475569;">{remaining:,} tokens remaining · resets 1st of month</span>
                <span style="color:#475569;text-transform:capitalize;">{plan} plan</span>
              </div>
            </div>'''
        from django.http import HttpResponse as _HR
        return _HR(html)

    return JsonResponse({
        'plan': plan, 'used': used, 'budget': budget,
        'remaining': remaining, 'pct': pct,
        'can_use_ai': budget > 0 and remaining > 0,
    })


# ── LemonSqueezy Webhook ──────────────────────────────────────────────────────

@csrf_exempt
@require_POST
def webhook(request):
    sig = request.headers.get('X-Signature', '')
    expected = hmac.new(
        settings.LEMONSQUEEZY_WEBHOOK_SECRET.encode(),
        request.body, hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(sig, expected):
        return HttpResponse(status=403)

    try:
        payload   = json.loads(request.body)
        event_id  = payload.get('meta', {}).get('event_id', '')
        event_name= payload.get('meta', {}).get('event_name', '')

        if WebhookEvent.objects.filter(event_id=event_id).exists():
            return HttpResponse(status=200)

        WebhookEvent.objects.create(event_id=event_id, event_name=event_name, payload=payload)
        _handle_webhook(event_name, payload)
    except Exception:
        pass
    return HttpResponse(status=200)


def _handle_webhook(event_name: str, payload: dict):
    from django.contrib.auth import get_user_model
    User = get_user_model()

    data  = payload.get('data', {})
    attrs = data.get('attributes', {})
    meta  = payload.get('meta', {}).get('custom_data', {})

    user_id = meta.get('user_id')
    if not user_id:
        return

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    sub, _ = Subscription.objects.get_or_create(user=user)
    variant_id = str(attrs.get('variant_id', ''))

    # Map variant_id to plan
    plan = Plan.FREE
    for plan_key, setting_name in VARIANT_MAP.items():
        if '_' in plan_key:  # skip legacy aliases
            vid = getattr(settings, setting_name, '')
            if vid and str(vid) == variant_id:
                plan = plan_key
                break

    if event_name in ('subscription_created', 'subscription_updated', 'subscription_resumed'):
        sub.plan                 = plan
        sub.ls_subscription_id   = str(data.get('id', ''))
        sub.ls_customer_id       = str(attrs.get('customer_id', ''))
        sub.ls_variant_id        = variant_id
        sub.status               = attrs.get('status', 'active')
        sub.cancel_at_period_end = attrs.get('cancelled', False)
        end_at = attrs.get('renews_at') or attrs.get('ends_at')
        if end_at:
            sub.current_period_end = parse_datetime(end_at)
        sub.save()

    elif event_name in ('subscription_cancelled', 'subscription_expired'):
        sub.status               = 'inactive' if event_name == 'subscription_expired' else 'cancelled'
        sub.cancel_at_period_end = True
        sub.save()
