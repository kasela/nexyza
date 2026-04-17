from django.urls import path
from . import views

app_name = 'connectors'

urlpatterns = [
    path('refresh-history/',    views.refresh_history,     name='refresh_history'),
    path('schedules/',          views.scheduled_analytics, name='scheduled_analytics'),
    path('snapshots/',          views.snapshot_timeline,   name='snapshot_timeline'),
    path('microsoft/auth/',     views.microsoft_auth_start,    name='microsoft_auth_start'),
    path('microsoft/callback/', views.microsoft_auth_callback, name='microsoft_auth_callback'),
    path('microsoft/add-file/', views.add_excel_file,          name='add_excel_file'),
    path('',                    views.connector_list,       name='list'),
    path('google/auth/',        views.google_auth_start,    name='google_auth_start'),
    path('google/callback/',    views.google_auth_callback, name='google_auth_callback'),
    path('google/add-sheet/',   views.add_sheet,            name='add_sheet'),
    path('summary/',            views.connector_summary,    name='summary'),
    path('<uuid:pk>/status/',    views.connector_status,     name='status'),
    path('<uuid:pk>/sync/',      views.trigger_sync,         name='trigger_sync'),
    path('<uuid:pk>/history/',   views.connector_history,     name='history'),
    path('<uuid:pk>/alerts/',    views.connector_alert_rules, name='alerts'),
    path('<uuid:pk>/alerts/add/', views.add_alert_rule, name='add_alert_rule'),
    path('<uuid:pk>/health/',    views.connector_health,      name='health'),
    path('<uuid:pk>/detail-history/', views.connector_history_detail, name='detail_history'),
    path('<uuid:pk>/', views.connector_detail, name='detail'),
    path('sync-log/<int:log_id>/retry/', views.retry_sync_log, name='retry_sync_log'),
    path('alert-rule/<uuid:rule_id>/delete/', views.delete_alert_rule, name='delete_alert_rule'),
    path('sync-log/<int:log_id>/note/', views.save_sync_note, name='save_sync_note'),
    path('<uuid:pk>/delete/',    views.delete_connector,     name='delete_connector'),
]
