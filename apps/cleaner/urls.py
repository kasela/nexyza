from django.urls import path
from . import views

app_name = 'cleaner'

urlpatterns = [
    path('<uuid:pk>/',        views.cleaner,        name='cleaner'),
    path('<uuid:pk>/apply/',  views.apply_op,       name='apply_op'),
    path('<uuid:pk>/export/', views.export_cleaned, name='export'),
    path('<uuid:pk>/reset/',  views.reset_ops,      name='reset'),
]
