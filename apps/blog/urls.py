from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
    path('',           views.blog_index, name='index'),
    path('<slug:slug>/', views.blog_post,  name='post'),
]
