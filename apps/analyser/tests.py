import tempfile
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.analyser.models import FileUpload


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class ChartGalleryRouteTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='tester@example.com',
            username='tester',
            password='pass12345'
        )
        self.client.force_login(self.user)
        csv_bytes = b'Branch,Sales,Target\nA,100,90\nB,120,110\nC,80,95\n'
        self.upload = FileUpload.objects.create(
            user=self.user,
            file=SimpleUploadedFile('sample.csv', csv_bytes, content_type='text/csv'),
            original_name='sample.csv',
            file_type=FileUpload.FILE_TYPE_CSV,
            file_size=len(csv_bytes),
            status=FileUpload.STATUS_PENDING,
            row_count=3,
            column_count=3,
            analysis_result={
                'columns': [
                    {'name': 'Branch', 'is_numeric': False, 'semantic_type': 'text'},
                    {'name': 'Sales', 'is_numeric': True, 'semantic_type': 'metric', 'mean': 100, 'sum': 300},
                    {'name': 'Target', 'is_numeric': True, 'semantic_type': 'metric', 'mean': 98.33, 'sum': 295},
                ]
            },
        )

    def test_chart_gallery_renders_with_preview_route(self):
        response = self.client.get(reverse('analyser:chart_gallery', args=[self.upload.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse('analyser:preview_chart_data', args=[self.upload.pk]))
        self.assertNotContains(response, 'analyser:preview_chart')

    def test_preview_endpoint_returns_json(self):
        response = self.client.post(
            reverse('analyser:preview_chart_data', args=[self.upload.pk]),
            {
                'chart_type': 'bar',
                'x_axis': 'Branch',
                'y_axis': 'Sales',
                'aggregation': 'sum',
                'color': 'violet',
                'title': 'Sales by Branch',
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('labels', payload)
        self.assertIn('datasets', payload)
        self.assertEqual(payload.get('chart_type'), 'bar')



    def test_result_page_uses_static_export_tools_bundle(self):
        self.upload.summary_data = {'total_rows': 3, 'numeric_columns': 2, 'text_columns': 1}
        self.upload.analysis_result = self.upload.analysis_result or {}
        self.upload.analysis_result.update({
            'chart_suggestions': [],
            'rows_preview': [{'Branch': 'A', 'Sales': 100, 'Target': 90}],
            'numeric_columns': ['Sales', 'Target'],
            'columns': self.upload.analysis_result.get('columns', []),
        })
        self.upload.save(update_fields=['summary_data', 'analysis_result'])
        response = self.client.get(reverse('analyser:result', args=[self.upload.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'js/analyser/result-export-tools.js')
        self.assertContains(response, 'id="result-export-config"')
        self.assertNotContains(response, 'function _showToast(html)')
        self.assertNotContains(response, 'window.requestExport = function requestExport')

    def test_result_page_uses_static_enhancement_bundle(self):
        self.upload.summary_data = {'total_rows': 3, 'numeric_columns': 2, 'text_columns': 1}
        self.upload.analysis_result = self.upload.analysis_result or {}
        self.upload.analysis_result.update({
            'chart_suggestions': [],
            'rows_preview': [{'Branch': 'A', 'Sales': 100, 'Target': 90}],
            'numeric_columns': ['Sales', 'Target'],
            'columns': self.upload.analysis_result.get('columns', []),
        })
        self.upload.save(update_fields=['summary_data', 'analysis_result'])
        response = self.client.get(reverse('analyser:result', args=[self.upload.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "js/analyser/result-enhancements.js")
        self.assertNotContains(response, "var TAB_KEY = 'nexyza:active-tab:' + uploadId;")

    def test_result_page_uses_static_present_mode_bundle(self):
        self.upload.summary_data = {'total_rows': 3, 'numeric_columns': 2, 'text_columns': 1}
        self.upload.analysis_result = self.upload.analysis_result or {}
        self.upload.analysis_result.update({
            'chart_suggestions': [],
            'rows_preview': [{'Branch': 'A', 'Sales': 100, 'Target': 90}],
            'numeric_columns': ['Sales', 'Target'],
            'columns': self.upload.analysis_result.get('columns', []),
        })
        self.upload.save(update_fields=['summary_data', 'analysis_result'])
        response = self.client.get(reverse('analyser:result', args=[self.upload.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "js/analyser/result-present-mode.js")
        self.assertNotContains(response, "var _fsSlides       = []")
        self.assertNotContains(response, "window.presentAll = function presentAll()")

    def test_result_page_uses_static_collaboration_bundle(self):
        response = self.client.get(reverse('analyser:result', args=[self.upload.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "result-collab-config")
        self.assertContains(response, "js/analyser/result-collaboration.js")
        self.assertNotContains(response, "var wsUrl=(window.location.protocol==='https:'?'wss':'ws')+'://'+window.location.host+'/ws/analysis/'")

    def test_result_page_uses_shared_chart_actions_bundle(self):
        response = self.client.get(reverse('analyser:result', args=[self.upload.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "js/analyser/chart-actions.js")
        self.assertNotContains(response, "window.downloadChart = function downloadChart")
        self.assertNotContains(response, "window.copyChartData = function copyChartData")

    def test_chart_gallery_uses_shared_chart_actions_bundle(self):
        response = self.client.get(reverse('analyser:chart_gallery', args=[self.upload.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "js/analyser/chart-actions.js")

    def test_result_page_uses_shared_chart_mutations_bundle(self):
        response = self.client.get(reverse('analyser:result', args=[self.upload.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "js/analyser/chart-mutations.js")
        self.assertContains(response, 'id="chart-mutation-config"')
        self.assertNotContains(response, "window.changeType = function changeType")
        self.assertNotContains(response, "window.changeColor = function changeColor")
        self.assertNotContains(response, "window.changeSize = function changeSize")

    def test_chart_gallery_uses_shared_chart_mutations_bundle(self):
        response = self.client.get(reverse('analyser:chart_gallery', args=[self.upload.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "js/analyser/chart-mutations.js")
        self.assertContains(response, 'id="chart-mutation-config"')

    def test_chart_gallery_uses_modular_gallery_bundles(self):
        response = self.client.get(reverse('analyser:chart_gallery', args=[self.upload.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "js/analyser/gallery-builder-state.js")
        self.assertContains(response, "js/analyser/gallery-builder-preview.js")
        self.assertContains(response, "js/analyser/gallery-controls.js")
        self.assertContains(response, "js/analyser/gallery-page.js")



    def test_build_dashboard_surfaces_business_semantics_snapshot(self):
        from apps.analyser.business_semantics_engine import infer_business_semantics
        profile = {
            'column_profiles': [
                {'name': 'Branch', 'canonical_name': 'branch', 'role': 'dimension', 'confidence': 0.8, 'hints': []},
                {'name': 'Month', 'canonical_name': 'month', 'role': 'time', 'confidence': 0.8, 'hints': ['time']},
                {'name': 'Sales', 'canonical_name': 'sales', 'role': 'measure', 'confidence': 0.8, 'hints': ['actual']},
                {'name': 'Target', 'canonical_name': 'target', 'role': 'measure', 'confidence': 0.8, 'hints': ['target']},
            ]
        }
        semantics = infer_business_semantics(profile)
        self.upload.analysis_result = self.upload.analysis_result or {}
        self.upload.analysis_result['profile_json'] = {'business_semantics': semantics}
        self.upload.save(update_fields=['analysis_result'])
        response = self.client.get(reverse('analyser:build_dashboard', args=[self.upload.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Business semantics')
        self.assertContains(response, 'Sales')
        self.assertContains(response, 'Target')

    def test_business_semantics_engine_detects_target_vs_actual_dataset(self):
        from apps.analyser.business_semantics_engine import infer_business_semantics
        semantics = infer_business_semantics({
            'column_profiles': [
                {'name': 'Branch', 'canonical_name': 'branch', 'role': 'dimension', 'confidence': 0.8, 'hints': []},
                {'name': 'Regional Manager', 'canonical_name': 'regional_manager', 'role': 'dimension', 'confidence': 0.8, 'hints': []},
                {'name': 'Month', 'canonical_name': 'month', 'role': 'time', 'confidence': 0.8, 'hints': ['time']},
                {'name': 'Achievement', 'canonical_name': 'achievement', 'role': 'measure', 'confidence': 0.8, 'hints': ['actual']},
                {'name': 'Target', 'canonical_name': 'target', 'role': 'measure', 'confidence': 0.8, 'hints': ['target']},
            ]
        })
        self.assertEqual(semantics.get('primary_archetype'), 'target_vs_actual')
        self.assertEqual((semantics.get('roles') or {}).get('primary_dimension'), 'Branch')
        self.assertEqual((semantics.get('roles') or {}).get('target_measure'), 'Target')
        self.assertIn('attainment_pct', ((semantics.get('recommendations') or {}).get('kpis') or []))


    def test_chart_gallery_shows_curation_summary_after_upgrade(self):
        from apps.analyser.models import ChartConfig
        ChartConfig.objects.create(
            upload=self.upload,
            title='Sales by Branch',
            chart_type='bar',
            x_axis='Branch',
            y_axis='Sales',
            aggregation='sum',
            color='violet',
            cached_data={'labels': ['A', 'B', 'C'], 'datasets': [{'label': 'Sales', 'data': [100, 120, 80]}]},
        )
        ChartConfig.objects.create(
            upload=self.upload,
            title='Sales KPI',
            chart_type='kpi',
            y_axis='Sales',
            aggregation='sum',
            color='emerald',
            cached_data={'kpi': True, 'value': '300', 'label': 'Sales'},
        )
        response = self.client.get(reverse('analyser:chart_gallery', args=[self.upload.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Decision-first chart selection')
        self.assertContains(response, 'Visible')

    def test_chart_gallery_shows_chart_selection_priority_badge(self):
        from apps.analyser.models import ChartConfig
        ChartConfig.objects.create(
            upload=self.upload,
            title='Sales by Branch',
            chart_type='bar',
            x_axis='Branch',
            y_axis='Sales',
            aggregation='sum',
            color='violet',
            cached_data={'labels': ['A', 'B', 'C'], 'datasets': [{'label': 'Sales', 'data': [100, 120, 80]}]},
        )
        response = self.client.get(reverse('analyser:chart_gallery', args=[self.upload.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTrue('Recommended' in response.content.decode() or 'High priority' in response.content.decode())



    def test_chart_gallery_uses_precomputed_share_ui_url(self):
        self.upload.share_enabled = True
        self.upload.share_token = 'abc123token'
        self.upload.save(update_fields=['share_enabled', 'share_token'])
        response = self.client.get(reverse('analyser:chart_gallery', args=[self.upload.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Open shared view ↗')
        self.assertContains(response, '/workspace/shared/abc123token/')

    def test_result_page_uses_precomputed_share_ui_embed_url(self):
        self.upload.share_enabled = True
        self.upload.share_token = 'embed123token'
        self.upload.save(update_fields=['share_enabled', 'share_token'])
        response = self.client.get(reverse('analyser:result', args=[self.upload.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, '/embed/dashboard/embed123token/')

    def test_report_builder_uses_modular_schedule_bundle(self):
        from apps.reportbuilder.models import Report
        report = Report.objects.create(user=self.user, title='Board Pack')
        response = self.client.get(reverse('reportbuilder:builder', args=[report.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'js/reportbuilder/builder-state.js')
        self.assertContains(response, 'js/reportbuilder/builder-sections.js')
        self.assertContains(response, 'js/reportbuilder/builder-schedule.js')
        self.assertContains(response, 'js/reportbuilder/builder-page.js')
        self.assertContains(response, 'id="report-schedule-pill"')

    def test_preview_endpoint_still_returns_chart_json_after_service_refactor(self):
        response = self.client.post(
            reverse('analyser:preview_chart_data', args=[self.upload.pk]),
            {
                'chart_type': 'line',
                'x_axis': 'Branch',
                'y_axis': 'Sales',
                'aggregation': 'sum',
                'color': 'blue',
                'title': 'Sales Trend',
                'config_json_extra_measures': 'Target',
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload.get('chart_type'), 'line')
        self.assertIn('datasets', payload)


    def test_result_page_uses_export_history_panel_bundle(self):
        response = self.client.get(reverse('analyser:result', args=[self.upload.id]))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="export-history-panel"')
        self.assertContains(response, 'js/analyser/export-history-panel.js')
        self.assertContains(response, '/export/%s/history/' % self.upload.id)

    def test_export_history_endpoint_returns_jobs(self):
        from apps.exports.models import ExportJob
        ExportJob.objects.create(user=self.user, upload=self.upload, fmt='pdf', theme='dark', status='done', result_url='/media/exports/x.pdf')
        response = self.client.get(reverse('exports:history', args=[self.upload.id]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertIn('jobs', payload)
        self.assertEqual(payload['jobs'][0]['fmt'], 'pdf')

    def test_export_retry_endpoint_creates_new_job(self):
        from unittest.mock import patch
        from apps.exports.models import ExportJob
        job = ExportJob.objects.create(user=self.user, upload=self.upload, fmt='pptx', theme='dark', status='error', error='boom')
        with patch('apps.exports.tasks.run_export') as mocked:
            response = self.client.post(reverse('exports:retry', args=[job.id]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(ExportJob.objects.filter(user=self.user, upload=self.upload, fmt='pptx').count(), 2)
        mocked.assert_called_once()

    def test_preview_endpoint_returns_structured_validation_errors(self):
        response = self.client.post(
            reverse('analyser:preview_chart_data', args=[self.upload.pk]),
            {
                'chart_type': 'bar',
                'x_axis': 'MissingColumn',
                'y_axis': 'Branch',
                'aggregation': 'sum',
                'color': 'violet',
            },
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload.get('ok'))
        self.assertIn('field_errors', payload)
        self.assertIn('x_axis', payload['field_errors'])
        self.assertIn('y_axis', payload['field_errors'])

    def test_create_chart_returns_json_validation_error_for_htmx(self):
        response = self.client.post(
            reverse('analyser:create_chart', args=[self.upload.pk]),
            {
                'title': 'Broken chart',
                'chart_type': 'line',
                'x_axis': '',
                'y_axis': 'Branch',
                'aggregation': 'sum',
                'color': 'violet',
                'size': 'md',
            },
            HTTP_HX_REQUEST='true',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload.get('ok'))
        self.assertIn('field_errors', payload)
        self.assertIn('x_axis', payload['field_errors'])

    def test_update_chart_returns_json_validation_error(self):
        from apps.analyser.models import ChartConfig
        chart = ChartConfig.objects.create(
            upload=self.upload,
            title='Sales by Branch',
            chart_type='bar',
            x_axis='Branch',
            y_axis='Sales',
            aggregation='sum',
            color='violet',
            size='md',
            config_json={},
        )
        response = self.client.post(
            reverse('analyser:update_chart', args=[self.upload.pk, chart.id]),
            {
                'chart_type': 'pie',
                'x_axis': 'Branch',
                'y_axis': 'NotAColumn',
                'aggregation': 'sum',
                'color': 'violet',
            },
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload.get('ok'))
        self.assertIn('y_axis', payload.get('field_errors', {}))


def test_report_builder_uses_export_history_bundle(self):
    from apps.reportbuilder.models import Report
    report = Report.objects.create(user=self.user, title='Ops Pack')
    response = self.client.get(reverse('reportbuilder:builder', args=[report.id]))
    self.assertEqual(response.status_code, 200)
    self.assertContains(response, 'id="report-export-history-panel"')
    self.assertContains(response, 'js/reportbuilder/export-history-panel.js')

def test_report_export_history_endpoint_returns_jobs(self):
    from apps.reportbuilder.models import Report, ReportExportJob
    report = Report.objects.create(user=self.user, title='Ops Pack')
    ReportExportJob.objects.create(report=report, user=self.user, fmt='pdf', status='done', result_url='/reports/builder/export/download/x/')
    response = self.client.get(reverse('reportbuilder:export_history', args=[report.id]))
    self.assertEqual(response.status_code, 200)
    payload = response.json()
    self.assertIn('jobs', payload)
    self.assertEqual(payload['jobs'][0]['fmt'], 'pdf')


    def test_report_schedule_rejects_invalid_frequency(self):
        from apps.reportbuilder.models import Report
        report = Report.objects.create(user=self.user, title='Ops Pack')
        response = self.client.post(reverse('reportbuilder:schedule', args=[report.id]), {
            'frequency': 'hourly',
            'email': 'valid@example.com',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload.get('ok'))
        self.assertIn('field_errors', payload)
        self.assertIn('frequency', payload['field_errors'])

    def test_report_schedule_rejects_invalid_email(self):
        from apps.reportbuilder.models import Report
        report = Report.objects.create(user=self.user, title='Ops Pack')
        response = self.client.post(reverse('reportbuilder:schedule', args=[report.id]), {
            'frequency': 'weekly',
            'email': 'bad-email',
        }, HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload.get('ok'))
        self.assertIn('email', payload.get('field_errors', {}))

    def test_report_export_queue_rejects_unsupported_format(self):
        from apps.reportbuilder.models import Report
        report = Report.objects.create(user=self.user, title='Ops Pack')
        response = self.client.post(reverse('reportbuilder:export_queue', args=[report.id, 'pptx']), HTTP_X_REQUESTED_WITH='XMLHttpRequest')
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload.get('ok'))
        self.assertIn('format', payload.get('field_errors', {}))


    def test_report_add_section_returns_structured_validation_error(self):
        from apps.reportbuilder.models import Report
        report = Report.objects.create(user=self.user, title='Ops Pack')
        response = self.client.post(
            reverse('reportbuilder:add_section', args=[report.id]),
            {'section_type': 'chart'},
            HTTP_HX_REQUEST='true',
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload.get('ok'))
        self.assertIn('chart_id', payload.get('field_errors', {}))

    def test_report_update_section_returns_structured_validation_error(self):
        from apps.reportbuilder.models import Report, ReportSection
        report = Report.objects.create(user=self.user, title='Ops Pack')
        sec = ReportSection.objects.create(report=report, section_type='text', sort_order=0, content={'text': 'Hello'})
        response = self.client.post(
            reverse('reportbuilder:update_section', args=[report.id, sec.id]),
            {'text': ''},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload.get('ok'))
        self.assertIn('text', payload.get('field_errors', {}))

    def test_report_reorder_sections_returns_structured_validation_error(self):
        from apps.reportbuilder.models import Report, ReportSection
        report = Report.objects.create(user=self.user, title='Ops Pack')
        sec = ReportSection.objects.create(report=report, section_type='text', sort_order=0, content={'text': 'Hello'})
        response = self.client.post(
            reverse('reportbuilder:reorder', args=[report.id]),
            {'order': '["not-the-real-id"]'},
            HTTP_X_REQUESTED_WITH='XMLHttpRequest',
        )
        self.assertEqual(response.status_code, 400)
        payload = response.json()
        self.assertFalse(payload.get('ok'))
        self.assertIn('order', payload.get('field_errors', {}))



    def test_connector_list_uses_sync_status_panel_bundle(self):
        response = self.client.get(reverse('connectors:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'id="connector-summary-panel"')
        self.assertContains(response, 'id="connector-sync-config"')
        self.assertContains(response, 'js/connectors/sync-status-panel.js')

    def test_connector_status_endpoint_returns_structured_payload(self):
        from apps.analyser.connector_models import DataConnector
        connector = DataConnector.objects.create(
            user=self.user,
            source=DataConnector.SOURCE_GOOGLE_SHEETS,
            name='Live Sales',
            refresh_interval_min=60,
            sync_status='ok',
            row_count=123,
        )
        response = self.client.get(reverse('connectors:status', args=[connector.id]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(payload['connector']['name'], 'Live Sales')
        self.assertEqual(payload['connector']['row_count'], 123)




    def test_connector_history_endpoint_returns_logs(self):
        from apps.analyser.connector_models import DataConnector, ConnectorSyncLog
        connector = DataConnector.objects.create(
            user=self.user,
            source=DataConnector.SOURCE_GOOGLE_SHEETS,
            name='Ops Feed',
            refresh_interval_min=60,
            sync_status='error',
        )
        ConnectorSyncLog.objects.create(connector=connector, status='error', trigger='manual', message='Sync failed', error_message='Bad tab')
        response = self.client.get(reverse('connectors:history', args=[connector.id]))
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload['ok'])
        self.assertEqual(len(payload['history']['items']), 1)
        self.assertEqual(payload['history']['items'][0]['status'], 'error')

    def test_connector_list_includes_history_urls(self):
        from apps.analyser.connector_models import DataConnector
        connector = DataConnector.objects.create(
            user=self.user,
            source=DataConnector.SOURCE_GOOGLE_SHEETS,
            name='Ops Feed',
            refresh_interval_min=60,
            sync_status='idle',
        )
        response = self.client.get(reverse('connectors:list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, f'connector-history-{connector.id}')
        self.assertContains(response, reverse('connectors:history', args=[connector.id]))


@override_settings(MEDIA_ROOT=tempfile.gettempdir())
class ConnectorValidationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            email='connector@example.com', username='connector', password='pass12345'
        )
        self.client.force_login(self.user)
        self.session = self.client.session
        self.session['google_access_token'] = 'tok'
        self.session['ms_access_token'] = 'tok'
        self.session.save()

    def test_google_sheet_form_preserves_values_and_shows_field_error(self):
        response = self.client.post(reverse('connectors:add_sheet'), {
            'sheet_url': 'https://example.com/not-google',
            'name': 'Revenue Feed',
            'tab': 'Main',
            'refresh_interval': '999',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Revenue Feed')
        self.assertContains(response, 'https://example.com/not-google')
        self.assertContains(response, 'Enter a valid Google Sheets URL.')
        self.assertContains(response, 'Choose one of the available refresh intervals.')

    def test_excel_form_preserves_values_and_shows_field_error(self):
        response = self.client.post(reverse('connectors:add_excel_file'), {
            'file_url': 'https://example.com/not-excel',
            'name': 'Board Pack Feed',
            'tab': 'Summary',
            'refresh_interval': 'abc',
        })
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'Board Pack Feed')
        self.assertContains(response, 'https://example.com/not-excel')
        self.assertContains(response, 'Enter a valid OneDrive, SharePoint, or Excel Online sharing URL.')
        self.assertContains(response, 'Choose a valid refresh interval.')


from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from apps.analyser.connector_models import DataConnector, ConnectorSyncLog
from apps.connectors.services import connector_history_payload_filtered, validate_sync_note


class ConnectorDetailSmokeTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='cdetail', email='cdetail@example.com', password='pw123456')
        self.connector = DataConnector.objects.create(user=self.user, source=DataConnector.SOURCE_GOOGLE_SHEETS, name='Ops Sheet')
        ConnectorSyncLog.objects.create(connector=self.connector, status='ok', trigger='manual', message='Loaded sales')
        ConnectorSyncLog.objects.create(connector=self.connector, status='error', trigger='retry', message='Retry failed', error_message='Bad header')

    def test_filtered_history_by_status(self):
        payload = connector_history_payload_filtered(self.connector, status='error')
        self.assertEqual(len(payload['items']), 1)
        self.assertEqual(payload['items'][0]['status'], 'error')

    def test_validate_sync_note_length(self):
        note, errors = validate_sync_note('x' * 2001)
        self.assertIn('notes', errors)


# Connector health/schema drift regression hooks added in nexyza_next_connector_health_bundle.


    def test_question_pack_uses_business_semantics_defaults(self):
        from apps.analyser.ai_question_designer import build_ai_question_pack
        profile = {
            'measures': ['Achievement', 'Target', 'Variance'],
            'target_columns': ['Target'],
            'time_columns': ['Month', 'Year'],
            'dimensions': ['Branch', 'Regional Manager'],
            'business_semantics': {
                'primary_archetype': 'target_vs_actual',
                'summary': 'primary measure: Achievement; primary dimension: Branch; time axis: Month; target: Target',
                'roles': {
                    'primary_measure': 'Achievement',
                    'target_measure': 'Target',
                    'period_column': 'Month',
                    'primary_dimension': 'Branch',
                    'comparison_dimension': 'Regional Manager',
                },
                'hierarchies': [['Regional Manager', 'Branch']],
                'recommendations': {
                    'charts': ['target_vs_actual_trend', 'variance_by_dimension'],
                },
                'needs_user_clarification': True,
                'ambiguities': ['Year needs confirmation'],
            }
        }
        pack = build_ai_question_pack(profile, ai_enabled=False)
        questions = pack.get('questions') or []
        self.assertEqual(pack.get('source'), 'manual_fallback')
        self.assertIn('primary measure: Achievement', pack.get('dataset_summary', ''))
        qmap = {q.get('key'): q for q in questions}
        self.assertEqual((qmap.get('target_column') or {}).get('default'), 'Target')
        self.assertEqual((qmap.get('time_axis') or {}).get('default'), 'Month')
        self.assertIn('comparison_level', qmap)
        self.assertIn('semantic_confirmation', qmap)

    def test_decision_chart_plan_prefers_semantic_target_views(self):
        from apps.analyser.decision_chart_builder import build_decision_chart_plan
        profile = {
            'measures': ['Achievement', 'Target'],
            'target_columns': ['Target'],
            'time_columns': ['Month'],
            'dimensions': ['Branch'],
            'business_semantics': {
                'primary_archetype': 'target_vs_actual',
                'roles': {
                    'primary_measure': 'Achievement',
                    'target_measure': 'Target',
                    'period_column': 'Month',
                    'primary_dimension': 'Branch',
                },
                'recommendations': {
                    'charts': ['target_vs_actual_trend', 'variance_by_dimension', 'attainment_ranked_bar'],
                },
            },
            'derived_metrics': {'available': ['attainment_pct', 'variance_to_target'], 'labels': {'attainment_pct': 'Attainment %', 'variance_to_target': 'Variance to Target'}, 'semantic_types': {'attainment_pct': 'ratio', 'variance_to_target': 'gap'}},
        }
        plan = build_decision_chart_plan(profile, target_count=8)
        titles = [item.get('title') for item in plan]
        self.assertTrue(any('Trend' in str(t) for t in titles))
        self.assertTrue(any(item.get('chart_type') == 'variance_bar' for item in plan))
        self.assertTrue(any(item.get('semantic_archetype') == 'target_vs_actual' for item in plan))

    def test_chart_curation_uses_business_semantics_when_scoring(self):
        from types import SimpleNamespace
        from apps.analyser.chart_curation_engine import curate_dashboard_charts
        analysis = {
            'profile_json': {
                'dimensions': ['Branch'],
                'measures': ['Achievement', 'Target'],
                'time_columns': ['Month'],
                'target_columns': ['Target'],
                'actual_columns': ['Achievement'],
                'business_semantics': {
                    'primary_archetype': 'target_vs_actual',
                    'roles': {
                        'primary_dimension': 'Branch',
                        'primary_measure': 'Achievement',
                        'target_measure': 'Target',
                        'period_column': 'Month',
                    },
                    'recommendations': {'charts': ['target_vs_actual_trend', 'variance_by_dimension']},
                },
            }
        }
        line_chart = SimpleNamespace(id=1, chart_type='line', x_axis='Month', y_axis='Achievement', group_by='', config_json={'target_column': 'Target'}, confidence_meta={'final_chart_confidence': 0.8}, cached_data={'labels': ['Jan'], 'datasets': [{'label': 'Achievement', 'data': [100]}]})
        pie_chart = SimpleNamespace(id=2, chart_type='pie', x_axis='Branch', y_axis='Achievement', group_by='', config_json={}, confidence_meta={'final_chart_confidence': 0.1}, cached_data={'labels': ['A'], 'datasets': [{'label': 'Achievement', 'data': [100]}]})
        curated = curate_dashboard_charts([pie_chart, line_chart], analysis, mode='executive')
        self.assertEqual(curated.visible[0].id, 1)
        reasons = (getattr(curated.visible[0], 'selection_meta', {}) or {}).get('reasons', [])
        self.assertTrue(any('Target Vs Actual Trend' in r or 'Time-aware trend' in r for r in reasons))
