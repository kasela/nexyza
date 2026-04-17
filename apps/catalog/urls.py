from django.urls import path
from . import views
app_name = 'catalog'
urlpatterns = [
    path('',             views.catalog_home,  name='home'),
    path('<uuid:pk>/',    views.asset_detail,  name='asset'),
    path('<uuid:pk>/update/', views.update_asset, name='update'),
]
