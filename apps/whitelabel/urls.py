from django.urls import path
from . import views

app_name = 'whitelabel'

urlpatterns = [
    path('',       views.branding_settings, name='settings'),
    path('save/',  views.save_branding,     name='save'),
    path('reset/', views.reset_branding,    name='reset'),
]
