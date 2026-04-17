from django.urls import path
from . import views

app_name = 'pipeline'

urlpatterns = [
    path('',              views.pipeline_list,  name='list'),
    path('create/',       views.create_source,  name='create'),
    path('<uuid:pk>/run/', views.run_now,         name='run_now'),
    path('<uuid:pk>/toggle/', views.toggle_source, name='toggle'),
    path('<uuid:pk>/delete/', views.delete_source, name='delete'),
]
