from django.urls import path
from . import views

app_name = 'reportbuilder'
urlpatterns = [
    path('',                              views.report_list,       name='list'),
    path('create/',                       views.create_report,     name='create'),
    path('<uuid:pk>/',                     views.builder,           name='builder'),
    path('<uuid:pk>/meta/',                views.update_report_meta,name='meta'),
    path('<uuid:pk>/section/add/',         views.add_section,       name='add_section'),
    path('<uuid:pk>/section/<uuid:section_id>/update/', views.update_section, name='update_section'),
    path('<uuid:pk>/section/<uuid:section_id>/delete/', views.delete_section, name='delete_section'),
    path('<uuid:pk>/reorder/',             views.reorder_sections,  name='reorder'),
    path('<uuid:pk>/export/pdf/',          views.export_report_pdf, name='export_pdf'),
    path('<uuid:pk>/export/<str:fmt>/queue/',  views.queue_report_export, name='export_queue'),
    path('<uuid:pk>/export/history/',          views.report_export_history, name='export_history'),
    path('export/download/<uuid:job_id>/',     views.report_export_download, name='export_download'),
    path('export/retry/<uuid:job_id>/',        views.retry_report_export, name='export_retry'),
    path('<uuid:pk>/public/',              views.toggle_public,     name='toggle_public'),
    path('<uuid:pk>/delete/',              views.delete_report,     name='delete'),
    path('<uuid:pk>/schedule/',            views.schedule_report,   name='schedule'),
    path('<uuid:pk>/unschedule/',          views.unschedule_report, name='unschedule'),
    path('view/<str:token>/',             views.public_report,     name='public'),
]
