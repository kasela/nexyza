from django.urls import path
from . import views

app_name = 'billing'

urlpatterns = [
    path('pricing/',                views.pricing,       name='pricing'),
    path('checkout/<str:plan_key>/',views.checkout,      name='checkout'),
    path('checkout/',               views.checkout,      name='checkout_default',
         kwargs={'plan_key': 'pro_monthly'}),
    path('portal/',                 views.portal,        name='portal'),
    path('webhook/',                views.webhook,       name='webhook'),
    path('token-usage/',            views.token_usage,   name='token_usage'),
]
