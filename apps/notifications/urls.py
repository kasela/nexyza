from django.urls import path
from . import views
app_name = 'notifications'
urlpatterns = [
    path('',                     views.notification_center, name='center'),
    path('rules/create/',        views.create_rule,         name='create_rule'),
    path('rules/<uuid:pk>/delete/', views.delete_rule,       name='delete_rule'),
    path('<uuid:pk>/read/',       views.mark_read,           name='mark_read'),
    path('read-all/',            views.mark_all_read,       name='mark_all_read'),
    path('check/<uuid:pk>/',      views.check_now,           name='check_now'),
]
