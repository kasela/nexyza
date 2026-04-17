from .models import Subscription, Plan


def subscription_context(request):
    if request.user.is_authenticated:
        sub = getattr(request, 'subscription', None)
        return {
            'subscription': sub,
            'is_pro': sub.is_active if sub else False,
            'Plan': Plan,
        }
    return {'subscription': None, 'is_pro': False, 'Plan': Plan}
