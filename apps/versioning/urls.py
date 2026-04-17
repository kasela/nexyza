from django.urls import path
from . import views
app_name = 'versioning'
urlpatterns = [
    path('<uuid:pk>/',                      views.version_history,  name='history'),
    path('<uuid:pk>/save/',                 views.save_snapshot,    name='save'),
    path('<uuid:pk>/diff/<int:v1>/<int:v2>/', views.view_diff,      name='diff'),
    path('<uuid:pk>/restore/<int:version>/', views.restore_snapshot, name='restore'),
]
