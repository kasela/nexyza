from django.urls import path
from . import views
app_name = 'webhooks'
urlpatterns = [
    path('',                views.webhook_list,  name='list'),
    path('create/',         views.create_webhook, name='create'),
    path('<uuid:pk>/toggle/', views.toggle_webhook, name='toggle'),
    path('<uuid:pk>/delete/', views.delete_webhook, name='delete'),
    path('<uuid:pk>/log/',    views.delivery_log,   name='log'),
    path('<uuid:pk>/test/',   views.test_webhook,   name='test'),
]
