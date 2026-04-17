from django.urls import path
from . import views
app_name = 'joins'
urlpatterns = [
    path('',                    views.join_builder, name='builder'),
    path('columns/<uuid:pk>/',   views.get_columns,  name='columns'),
    path('execute/',            views.execute,      name='execute'),
]
