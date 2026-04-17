from django.urls import path
from . import views

app_name = 'roles'
urlpatterns = [
    path('<slug:team_slug>/',           views.role_manager, name='manager'),
    path('<slug:team_slug>/create/',    views.create_role,  name='create'),
    path('<slug:team_slug>/<uuid:role_id>/delete/', views.delete_role, name='delete'),
]
