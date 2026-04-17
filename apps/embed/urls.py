from django.urls import path
from . import views

app_name = 'embed'

urlpatterns = [
    path('chart/<uuid:chart_id>/<str:token>/', views.embed_chart,      name='chart'),
    path('dashboard/<str:token>/',            views.embed_dashboard,   name='dashboard'),
    path('snippet/<str:token>/',              views.embed_snippet,     name='snippet'),
]
