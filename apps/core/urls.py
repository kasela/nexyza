from django.urls import path
from . import views
from . import admin_views

app_name = 'core'

urlpatterns = [
    path('',             views.home,            name='home'),
    path('manifest.json', views.pwa_manifest,   name='pwa_manifest'),
    path('sw.js',        views.service_worker,  name='service_worker'),
    path('privacy/',     views.privacy,          name='privacy'),
    path('terms/',       views.terms,            name='terms'),
    path('contact/',     views.contact,          name='contact'),
    path('social-posts/', views.social_posts,     name='social_posts'),
    path('robots.txt',   views.robots_txt,       name='robots_txt'),
    path('sitemap.xml',  views.sitemap_xml,       name='sitemap_xml'),
    # Custom admin panel
    path('admin-panel/',                           admin_views.admin_dashboard,    name='admin_dashboard'),
    path('admin-panel/users/',                     admin_views.admin_users,        name='admin_users'),
    path('admin-panel/users/<int:user_id>/',       admin_views.admin_user_detail,  name='admin_user_detail'),
    path('admin-panel/users/<int:user_id>/staff/', admin_views.admin_toggle_staff, name='admin_toggle_staff'),
    path('admin-panel/users/<int:user_id>/pro/',   admin_views.admin_grant_pro,    name='admin_grant_pro'),
    path('admin-panel/users/<int:user_id>/delete/', admin_views.admin_delete_user, name='admin_delete_user'),
]
