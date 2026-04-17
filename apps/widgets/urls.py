from django.urls import path
from . import views
app_name = 'widgets'
urlpatterns = [
    path('',              views.widget_board,   name='board'),
    path('add/',          views.add_widget,     name='add'),
    path('<uuid:pk>/delete/', views.delete_widget, name='delete'),
    path('<uuid:pk>/data/', views.widget_data,   name='data'),
    path('reorder/',      views.reorder_widgets, name='reorder'),
]
