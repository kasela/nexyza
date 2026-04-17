from django.urls import path
from . import views

app_name = 'forecasting'
urlpatterns = [
    path('<uuid:pk>/',     views.forecast_view, name='view'),
    path('<uuid:pk>/run/', views.run,           name='run'),
]
