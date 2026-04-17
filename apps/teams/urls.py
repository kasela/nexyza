from django.urls import path
from . import views

app_name = 'teams'
urlpatterns = [
    path('',                        views.team_list,     name='list'),
    path('create/',                 views.create_team,   name='create'),
    path('<slug:slug>/',            views.team_detail,   name='detail'),
    path('<slug:slug>/invite/',     views.invite_member, name='invite'),
    path('<slug:slug>/remove/<int:user_id>/', views.remove_member, name='remove_member'),
    path('invite/<str:token>/accept/', views.accept_invite, name='accept_invite'),
]
