from .models import Subscription, Plan


class SubscriptionMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            sub, _ = Subscription.objects.get_or_create(
                user=request.user,
                defaults={'plan': Plan.FREE, 'status': 'inactive'}
            )
            request.subscription = sub
        else:
            request.subscription = None
        return self.get_response(request)
