from django.urls import path
from . import views

app_name = 'nlq'

urlpatterns = [
    path('<uuid:pk>/ask/',     views.ask,     name='ask'),
    path('<uuid:pk>/history/', views.history, name='history'),
]
