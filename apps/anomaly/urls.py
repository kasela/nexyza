from django.urls import path
from . import views

app_name = 'anomaly'
urlpatterns = [
    path('<uuid:pk>/',     views.anomaly_report,  name='report'),
    path('<uuid:pk>/run/', views.run_detection,   name='run'),
]
