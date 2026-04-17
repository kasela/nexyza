from django.urls import path
from . import views

app_name = 'api'

urlpatterns = [
    # Web UI
    path('keys/',           views.key_list,   name='keys'),
    path('keys/create/',    views.create_key, name='create_key'),
    path('keys/<uuid:pk>/revoke/', views.revoke_key, name='revoke_key'),
    # REST endpoints
    path('uploads/',              views.api_uploads_list,   name='uploads'),
    path('uploads/<uuid:pk>/',     views.api_upload_detail,  name='upload_detail'),
    path('uploads/<uuid:pk>/charts/', views.api_upload_charts, name='upload_charts'),
    path('uploads/<uuid:pk>/delete/', views.api_upload_delete, name='upload_delete'),
    path('upload/',               views.api_upload_file,    name='upload_file'),
]
