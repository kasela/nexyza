from django.urls import path
from . import views, views_charts, views_analysis

app_name = 'analyser'

urlpatterns = [
    # Upload & result
    path('',                              views.upload,                 name='upload'),
    path('<uuid:pk>/',                     views.result,                 name='result'),
    path('<uuid:pk>/sheet/',               views.switch_sheet,           name='switch_sheet'),
    path('<uuid:pk>/review/',              views.profile_review,         name='profile_review'),
    path('<uuid:pk>/review/submit/',       views.submit_profile_review,  name='submit_profile_review'),
    path('<uuid:pk>/refinement/',          views.adaptive_refinement,      name='adaptive_refinement'),
    path('<uuid:pk>/refinement/submit/',   views.adaptive_refinement_submit, name='adaptive_refinement_submit'),
    path('<uuid:pk>/refinement/download/', views.adaptive_refinement_download, name='adaptive_refinement_download'),
    path('<uuid:pk>/build/',               views.build_dashboard,        name='build_dashboard'),
    path('<uuid:pk>/build/start/',         views.build_dashboard_start,  name='build_dashboard_start'),
    path('<uuid:pk>/power-dashboard/',     views.power_dashboard,        name='power_dashboard'),
    path('<uuid:pk>/insights/',            views.generate_ai_insights,   name='ai_insights'),
    path('<uuid:pk>/export/<str:fmt>/',    views.export,                 name='export'),
    path('<uuid:pk>/delete/',              views.delete_upload,          name='delete'),
    path('<uuid:pk>/pin/',                  views.pin_upload,             name='pin'),
    path('bulk-delete/',                   views.bulk_delete,            name='bulk_delete'),
    path('<uuid:pk>/share/',               views.toggle_share,           name='share'),
    path('<uuid:pk>/studio/',              views_analysis.analysis_studio, name='analysis_studio'),
    path('<uuid:pk>/forecast/',            views_analysis.forecast_workspace, name='forecast_workspace'),
    path('<uuid:pk>/scenario-preview/',    views_analysis.scenario_preview, name='scenario_preview'),
    path('<uuid:pk>/board/',               views_analysis.board_report, name='board_report'),

    path('<uuid:pk>/studio/save-view/',         views_analysis.save_analysis_view, name='save_analysis_view'),
    path('<uuid:pk>/studio/views/<uuid:view_id>/', views_analysis.load_analysis_view, name='load_analysis_view'),
    path('<uuid:pk>/studio/views/<uuid:view_id>/delete/', views_analysis.delete_analysis_view, name='delete_analysis_view'),
    path('<uuid:pk>/studio/cross-filter/',      views_analysis.cross_filter, name='cross_filter'),
    path('<uuid:pk>/studio/drilldown/',         views_analysis.drilldown_data, name='drilldown_data'),
    path('<uuid:pk>/studio/charts/<uuid:chart_id>/update/', views_analysis.update_chart_inspector, name='update_chart_inspector'),
    # Compare
    path('compare/',                      views.compare,                name='compare'),
    # Shared (public)
    path('shared/<str:token>/',           views.shared_result,          name='shared'),

    # ── Chart gallery & CRUD ──────────────────────────────────────────────────
    path('<uuid:pk>/charts/',              views_charts.chart_gallery,        name='chart_gallery'),
    path('<uuid:pk>/charts/regenerate/',   views_charts.regenerate_charts,    name='regenerate_charts'),
    path('<uuid:pk>/charts/ai-generate/',  views_charts.ai_regenerate_charts,  name='ai_regenerate_charts'),
    path('<uuid:pk>/charts/create/',       views_charts.create_chart,         name='create_chart'),
    path('<uuid:pk>/charts/reorder/',      views_charts.reorder_charts,       name='reorder_charts'),
    path('<uuid:pk>/charts/schedule/save/', views_charts.save_scheduled_delivery, name='save_scheduled_delivery'),
    path('<uuid:pk>/charts/schedule/run/', views_charts.run_scheduled_delivery_now, name='run_scheduled_delivery_now'),
    path('<uuid:pk>/charts/schedule/disable/', views_charts.disable_scheduled_delivery, name='disable_scheduled_delivery'),
    path('<uuid:pk>/charts/preview/',      views_charts.preview_chart_data,   name='preview_chart_data'),
    path('<uuid:pk>/charts/<uuid:chart_id>/data/',      views_charts.chart_data_api,  name='chart_data_api'),
    path('<uuid:pk>/charts/<uuid:chart_id>/update/',    views_charts.update_chart,    name='update_chart'),
    path('<uuid:pk>/charts/<uuid:chart_id>/delete/',    views_charts.delete_chart,    name='delete_chart'),
    path('<uuid:pk>/charts/<uuid:chart_id>/duplicate/', views_charts.duplicate_chart, name='duplicate_chart'),
]
