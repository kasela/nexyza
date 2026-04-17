from django.urls import path
from . import views

app_name = 'reports'

urlpatterns = [
    path('',              views.report_list,    name='list'),
    path('create/',       views.create_report,  name='create'),
    path('<uuid:pk>/send/', views.send_now,       name='send_now'),
    path('<uuid:pk>/toggle/', views.toggle_report, name='toggle'),
    path('<uuid:pk>/delete/', views.delete_report, name='delete'),
]
