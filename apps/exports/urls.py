from django.urls import path
from . import views

app_name = 'exports'
urlpatterns = [
    path('<uuid:pk>/excel/',           views.export_excel,   name='excel'),
    path('<uuid:pk>/pdf/',             views.export_pdf,     name='pdf'),
    path('<uuid:pk>/pptx/',            views.export_pptx,    name='pptx'),
    # Background export
    path('<uuid:pk>/<str:fmt>/queue/', views.export_queue,   name='queue'),
    path('status/<uuid:job_id>/',     views.export_status,   name='status'),
    path('download/<uuid:job_id>/',   views.export_download, name='download'),
    path('<uuid:pk>/history/',         views.export_history,  name='history'),
    path('retry/<uuid:job_id>/',       views.export_retry,    name='retry'),
]
