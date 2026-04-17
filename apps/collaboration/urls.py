from django.urls import path
from . import views
app_name = 'collaboration'
urlpatterns = [
    path('<uuid:upload_id>/presence/', views.presence, name='presence'),
    path('<uuid:upload_id>/panel/', views.panel, name='panel'),
    path('<uuid:upload_id>/comments/', views.comments, name='comments'),
    path('<uuid:upload_id>/comments/add/', views.add_comment, name='add_comment'),
    path('<uuid:upload_id>/comments/<uuid:comment_id>/resolve/', views.resolve_comment, name='resolve'),
    path('<uuid:upload_id>/actions/', views.actions, name='actions'),
    path('<uuid:upload_id>/actions/add/', views.add_action, name='add_action'),
    path('<uuid:upload_id>/actions/<uuid:action_id>/status/', views.update_action_status, name='update_action_status'),
]
