"""
Live data connector views.
Handles Google Sheets and Excel Online connections + sync.
"""
import json
import requests
import logging
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.views.decorators.http import require_POST
from django.utils import timezone

from apps.analyser.connector_models import DataConnector, ConnectorSyncLog, ConnectorAlertRule
from apps.analyser.models import FileUpload
from apps.billing.models import TokenUsage
from apps.connectors.service_helpers import (
    connector_status_payload,
    connector_summary_payload,
    connector_history_payload,
    connector_history_item_payload,
    connector_detail_payload,
    connector_history_payload_filtered,
    validate_sync_note,
    validate_google_sheet_form,
    validate_excel_online_form,
    connector_form_context,
    start_connector_sync_log,
    finish_connector_sync_log,
    build_schema_snapshot,
    connector_health_payload,
    connector_alert_rules_payload,
    validate_alert_rule_form,
    alert_rule_payload,
)

logger = logging.getLogger(__name__)


def _require_connector_access(user):
    """Check if user's plan allows connectors."""
    try:
        return user.subscription.can_use_connectors
    except Exception:
        return False


# ── Connector list ────────────────────────────────────────────────────────────

@login_required
def connector_list(request):
    if not _require_connector_access(request.user):
        return render(request, 'connectors/upgrade_required.html')
    connectors = DataConnector.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'connectors/list.html', {
        'connectors': connectors,
        'connector_summary': connector_summary_payload(connectors),
    })


# ── Google Sheets OAuth ───────────────────────────────────────────────────────

@login_required
def google_auth_start(request):
    """Redirect to Google OAuth consent screen requesting Sheets read access."""
    if not _require_connector_access(request.user):
        return redirect('billing:pricing')

    client_id = settings.GOOGLE_OAUTH_CLIENT_ID
    if not client_id:
        return render(request, 'connectors/oauth_not_configured.html',
                      {'provider': 'Google'})

    redirect_uri = request.build_absolute_uri('/connectors/google/callback/')
    scope = 'https://www.googleapis.com/auth/spreadsheets.readonly profile email'

    auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth"
        f"?client_id={client_id}"
        f"&redirect_uri={redirect_uri}"
        f"&response_type=code"
        f"&scope={scope}"
        f"&access_type=offline"
        f"&prompt=consent"
        f"&state={request.user.id}"
    )
    return redirect(auth_url)


@login_required
def google_auth_callback(request):
    """Handle Google OAuth callback, exchange code for tokens."""
    code  = request.GET.get('code', '')
    error = request.GET.get('error', '')

    if error or not code:
        return render(request, 'connectors/oauth_error.html',
                      {'provider': 'Google', 'error': error or 'No code returned'})

    redirect_uri = request.build_absolute_uri('/connectors/google/callback/')
    token_resp   = requests.post('https://oauth2.googleapis.com/token', data={
        'code':          code,
        'client_id':     settings.GOOGLE_OAUTH_CLIENT_ID,
        'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
        'redirect_uri':  redirect_uri,
        'grant_type':    'authorization_code',
    }, timeout=15)

    if not token_resp.ok:
        return render(request, 'connectors/oauth_error.html',
                      {'provider': 'Google', 'error': token_resp.text[:200]})

    tokens = token_resp.json()
    request.session['google_access_token']  = tokens.get('access_token', '')
    request.session['google_refresh_token'] = tokens.get('refresh_token', '')
    request.session['google_token_expiry']  = str(
        timezone.now().timestamp() + tokens.get('expires_in', 3600)
    )
    return redirect('connectors:add_sheet')


@login_required
def add_sheet(request):
    """Form to add a Google Sheet connector after successful OAuth."""
    access_token = request.session.get('google_access_token', '')
    if not access_token:
        return redirect('connectors:google_auth_start')

    if request.method == 'POST':
        validation = validate_google_sheet_form(request.POST)
        if validation['errors']:
            return render(request, 'connectors/add_sheet.html', connector_form_context(
                form_data=validation['form_data'],
                errors=validation['errors'],
            ))

        cleaned = validation['cleaned_data']
        sheet_url = cleaned['sheet_url']
        name = cleaned['name']
        tab = cleaned['tab']
        interval = cleaned['refresh_interval']

        # Extract sheet ID from URL
        sheet_id = _extract_sheet_id(sheet_url)
        if not sheet_id:
            return render(request, 'connectors/add_sheet.html', connector_form_context(
                form_data=validation['form_data'],
                errors={'sheet_url': 'Could not extract Sheet ID from URL. Please paste the full Google Sheets URL.'},
            ))

        # Test the connection
        test_ok, test_err = _test_google_sheet(access_token, sheet_id, tab)
        if not test_ok:
            return render(request, 'connectors/add_sheet.html', connector_form_context(
                form_data=validation['form_data'],
                non_field_error=f'Could not access sheet: {test_err}',
            ))

        connector = DataConnector.objects.create(
            user=request.user,
            source=DataConnector.SOURCE_GOOGLE_SHEETS,
            name=name,
            sheet_url=sheet_url,
            sheet_id=sheet_id,
            sheet_tab=tab,
            access_token=access_token,
            refresh_token=request.session.get('google_refresh_token', ''),
            refresh_interval_min=interval,
        )
        # Trigger first sync
        _sync_google_sheet(connector)
        return redirect('connectors:list')

    return render(request, 'connectors/add_sheet.html', connector_form_context(form_data={'refresh_interval': '60'}))


def _extract_sheet_id(url: str) -> str:
    """Extract Google Sheet ID from URL."""
    import re
    match = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', url)
    return match.group(1) if match else ''


def _test_google_sheet(access_token: str, sheet_id: str, tab: str) -> tuple:
    """Test read access to a Google Sheet."""
    range_spec = f"'{tab}'!A1:A2" if tab else 'A1:A2'
    resp = requests.get(
        f"https://sheets.googleapis.com/v4/spreadsheets/{sheet_id}/values/{range_spec}",
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=10,
    )
    if resp.ok:
        return True, ''
    return False, resp.json().get('error', {}).get('message', resp.text[:100])


# ── Sheet sync ────────────────────────────────────────────────────────────────

def _refresh_google_token(connector: DataConnector) -> str:
    """Refresh expired Google access token. Returns new access token."""
    if not connector.refresh_token:
        return connector.access_token

    resp = requests.post('https://oauth2.googleapis.com/token', data={
        'client_id':     settings.GOOGLE_OAUTH_CLIENT_ID,
        'client_secret': settings.GOOGLE_OAUTH_CLIENT_SECRET,
        'refresh_token': connector.refresh_token,
        'grant_type':    'refresh_token',
    }, timeout=15)

    if resp.ok:
        new_token = resp.json().get('access_token', '')
        connector.access_token = new_token
        connector.token_expiry = timezone.now() + __import__('datetime').timedelta(
            seconds=resp.json().get('expires_in', 3600)
        )
        connector.save(update_fields=['access_token', 'token_expiry'])
        return new_token
    return connector.access_token


def _sync_google_sheet(connector: DataConnector, *, trigger: str = 'manual'):
    log = start_connector_sync_log(connector, trigger=trigger)
    """Pull latest data from Google Sheet and create/update a FileUpload."""
    import io, csv as csvmod, tempfile, os, shutil

    connector.sync_status = 'syncing'
    connector.save(update_fields=['sync_status'])

    try:
        # Refresh token if needed
        if connector.token_expiry and timezone.now() >= connector.token_expiry:
            _refresh_google_token(connector)

        # Build range
        tab       = connector.sheet_tab
        range_ref = connector.range_spec or 'A1'
        full_range = f"'{tab}'!{range_ref}" if tab else range_ref

        resp = requests.get(
            f"https://sheets.googleapis.com/v4/spreadsheets/{connector.sheet_id}/values/{full_range}",
            headers={'Authorization': f'Bearer {connector.access_token}'},
            timeout=30,
        )

        if not resp.ok:
            raise RuntimeError(resp.json().get('error', {}).get('message', 'API error'))

        data  = resp.json()
        rows  = data.get('values', [])
        if not rows:
            raise RuntimeError('Sheet returned no data')

        # Convert to CSV
        buf = io.StringIO()
        csvmod.writer(buf).writerows(rows)
        csv_bytes = buf.getvalue().encode()

        # Save as a temp file and run analyse
        safe_name = f"gs_{connector.sheet_id[:8]}.csv"
        user_dir  = f"uploads/{connector.user_id}"
        full_dir  = f"{settings.MEDIA_ROOT}/{user_dir}"
        os.makedirs(full_dir, exist_ok=True)
        csv_path  = f"{full_dir}/{safe_name}"

        with open(csv_path, 'wb') as f:
            f.write(csv_bytes)

        from apps.analyser.engine import analyse
        from apps.analyser.views import _sanitise_result

        result = _sanitise_result(analyse(csv_path, 'csv'))

        # Update or create a FileUpload linked to this connector
        upload, created = FileUpload.objects.update_or_create(
            user=connector.user,
            original_name=f"[Live] {connector.name}",
            defaults={
                'file':            f"{user_dir}/{safe_name}",
                'file_type':       'csv',
                'file_size':       len(csv_bytes),
                'status':          FileUpload.STATUS_DONE,
                'row_count':       result['rows'],
                'column_count':    result['cols'],
                'analysis_result': result,
                'label':           '🔴 Live',
            }
        )

        connector.last_synced_at = timezone.now()
        connector.row_count      = result['rows']
        connector.sync_status    = 'ok'
        connector.sync_error     = ''
        connector.schedule_next_sync()
        connector.save(update_fields=[
            'last_synced_at', 'row_count', 'sync_status', 'sync_error', 'next_sync_at'
        ])
        schema_columns, schema_signature = build_schema_snapshot(result)
        finish_connector_sync_log(log, connector, ok=True, row_count=result['rows'], message='Sync complete', schema_columns=schema_columns, schema_signature=schema_signature)

        return upload

    except Exception as e:
        connector.sync_status = 'error'
        connector.sync_error  = str(e)[:500]
        connector.save(update_fields=['sync_status', 'sync_error'])
        finish_connector_sync_log(log, connector, ok=False, error_message=str(e), message='Sync failed')
        logger.error(f"Sync failed for connector {connector.id}: {e}")
        return None


@login_required
def connector_status(request, pk):
    """Return structured sync status for a single connector."""
    connector = get_object_or_404(DataConnector, pk=pk, user=request.user)
    return JsonResponse({'ok': True, 'connector': connector_status_payload(connector)})




@login_required
def connector_history(request, pk):
    connector = get_object_or_404(DataConnector, pk=pk, user=request.user)
    return JsonResponse({'ok': True, 'history': connector_history_payload(connector)})


@login_required
def connector_detail(request, pk):
    connector = get_object_or_404(DataConnector, pk=pk, user=request.user)
    status = (request.GET.get('status') or '').strip()
    trigger = (request.GET.get('trigger') or '').strip()
    query = (request.GET.get('q') or '').strip()
    history = connector_history_payload_filtered(connector, status=status, trigger=trigger, query=query)
    return render(request, 'connectors/detail.html', {
        'connector': connector,
        'connector_payload': connector_detail_payload(connector),
        'connector_health': connector_health_payload(connector),
        'history_payload': history,
        'active_status': status,
        'active_trigger': trigger,
        'active_query': query,
        'alert_rules': connector_alert_rules_payload(connector),
    })






@login_required
def connector_alert_rules(request, pk):
    connector = get_object_or_404(DataConnector, pk=pk, user=request.user)
    return JsonResponse({'ok': True, 'rules': connector_alert_rules_payload(connector)})


@login_required
@require_POST
def add_alert_rule(request, pk):
    connector = get_object_or_404(DataConnector, pk=pk, user=request.user)
    validation = validate_alert_rule_form(request.POST)
    if validation['errors']:
        return JsonResponse({'ok': False, 'errors': validation['errors']}, status=400)
    cleaned = validation['cleaned_data']
    rule = ConnectorAlertRule.objects.create(
        connector=connector,
        rule_type=cleaned['rule_type'],
        threshold=cleaned['threshold'],
        action=cleaned['action'],
        is_active=True,
    )
    return JsonResponse({'ok': True, 'rule': alert_rule_payload(rule), 'rules': connector_alert_rules_payload(connector)})


@login_required
@require_POST
def delete_alert_rule(request, rule_id):
    rule = get_object_or_404(ConnectorAlertRule.objects.select_related('connector'), pk=rule_id, connector__user=request.user)
    connector = rule.connector
    rule.delete()
    return JsonResponse({'ok': True, 'rules': connector_alert_rules_payload(connector)})

@login_required
def connector_health(request, pk):
    connector = get_object_or_404(DataConnector, pk=pk, user=request.user)
    return JsonResponse({'ok': True, 'health': connector_health_payload(connector)})

@login_required
def connector_history_detail(request, pk):
    connector = get_object_or_404(DataConnector, pk=pk, user=request.user)
    status = (request.GET.get('status') or '').strip()
    trigger = (request.GET.get('trigger') or '').strip()
    query = (request.GET.get('q') or '').strip()
    return JsonResponse({'ok': True, 'history': connector_history_payload_filtered(connector, status=status, trigger=trigger, query=query)})


@login_required
@require_POST
def save_sync_note(request, log_id):
    log = get_object_or_404(ConnectorSyncLog.objects.select_related('connector'), pk=log_id, connector__user=request.user)
    note, errors = validate_sync_note(request.POST.get('notes'))
    if errors:
        return JsonResponse({'ok': False, 'errors': errors}, status=400)
    log.notes = note
    log.save(update_fields=['notes'])
    return JsonResponse({'ok': True, 'item': connector_history_item_payload(log)})


@login_required
@require_POST
def retry_sync_log(request, log_id):
    log = get_object_or_404(ConnectorSyncLog.objects.select_related('connector'), pk=log_id, connector__user=request.user)
    connector = log.connector
    upload = _sync_google_sheet(connector, trigger='retry') if connector.source == DataConnector.SOURCE_GOOGLE_SHEETS else _sync_excel_online(connector, trigger='retry')
    return JsonResponse({
        'ok': connector.sync_status == 'ok',
        'connector': connector_status_payload(connector),
        'history': connector_history_payload(connector),
        'upload_id': str(upload.id) if upload else None,
    }, status=200 if connector.sync_status == 'ok' else 400)

@login_required
def connector_summary(request):
    """Return summary counts for the connector dashboard."""
    connectors = DataConnector.objects.filter(user=request.user).order_by('-created_at')
    return JsonResponse({
        'ok': True,
        'summary': connector_summary_payload(connectors),
        'connectors': [connector_status_payload(conn) for conn in connectors],
    })


@login_required
@require_POST
def trigger_sync(request, pk):
    """Manually trigger a sync for a connector."""
    connector = get_object_or_404(DataConnector, pk=pk, user=request.user)
    upload = _sync_google_sheet(connector) if connector.source == DataConnector.SOURCE_GOOGLE_SHEETS else _sync_excel_online(connector)
    payload = connector_status_payload(connector)
    if request.headers.get('HX-Request'):
        msg = payload['last_synced_human'] if connector.sync_status == 'ok' else (payload['sync_error'][:80] or 'Sync failed')
        return HttpResponse(
            f"<span style=\"color:{payload['status_color']};font-size:12px;\">{payload['status_dot']} {msg}</span>"
        )
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({'ok': connector.sync_status == 'ok', 'connector': payload})
    return redirect('connectors:list')


@login_required
def delete_connector(request, pk):
    """Delete a connector."""
    connector = get_object_or_404(DataConnector, pk=pk, user=request.user)
    if request.method == 'POST':
        connector.delete()
        return redirect('connectors:list')
    return render(request, 'connectors/confirm_delete.html', {'connector': connector})


# ── Microsoft Excel Online (Graph API) ───────────────────────────────────────

@login_required
def microsoft_auth_start(request):
    """Redirect to Microsoft OAuth consent screen."""
    if not _require_connector_access(request.user):
        return redirect('billing:pricing')

    client_id = getattr(settings, 'MICROSOFT_OAUTH_CLIENT_ID', '')
    if not client_id:
        return render(request, 'connectors/oauth_not_configured.html',
                      {'provider': 'Microsoft'})

    redirect_uri = request.build_absolute_uri('/connectors/microsoft/callback/')
    scope = 'Files.Read User.Read offline_access'

    auth_url = (
        'https://login.microsoftonline.com/common/oauth2/v2.0/authorize'
        f'?client_id={client_id}'
        f'&redirect_uri={redirect_uri}'
        '&response_type=code'
        f'&scope={scope}'
        '&response_mode=query'
        f'&state={request.user.id}'
    )
    return redirect(auth_url)


@login_required
def microsoft_auth_callback(request):
    """Handle Microsoft OAuth callback."""
    code  = request.GET.get('code', '')
    error = request.GET.get('error', '')

    if error or not code:
        return render(request, 'connectors/oauth_error.html',
                      {'provider': 'Microsoft',
                       'error': request.GET.get('error_description', error or 'No code returned')})

    redirect_uri = request.build_absolute_uri('/connectors/microsoft/callback/')
    token_resp = requests.post(
        'https://login.microsoftonline.com/common/oauth2/v2.0/token',
        data={
            'code':          code,
            'client_id':     settings.MICROSOFT_OAUTH_CLIENT_ID,
            'client_secret': settings.MICROSOFT_OAUTH_CLIENT_SECRET,
            'redirect_uri':  redirect_uri,
            'grant_type':    'authorization_code',
        }, timeout=15,
    )

    if not token_resp.ok:
        return render(request, 'connectors/oauth_error.html',
                      {'provider': 'Microsoft', 'error': token_resp.text[:200]})

    tokens = token_resp.json()
    request.session['ms_access_token']  = tokens.get('access_token', '')
    request.session['ms_refresh_token'] = tokens.get('refresh_token', '')
    return redirect('connectors:add_excel_file')


@login_required
def add_excel_file(request):
    """Form to add a Microsoft Excel Online connector after OAuth."""
    access_token = request.session.get('ms_access_token', '')
    if not access_token:
        return redirect('connectors:microsoft_auth_start')

    if request.method == 'POST':
        validation = validate_excel_online_form(request.POST)
        if validation['errors']:
            return render(request, 'connectors/add_excel.html', connector_form_context(
                form_data=validation['form_data'],
                errors=validation['errors'],
            ))

        cleaned = validation['cleaned_data']
        file_url = cleaned['file_url']
        name = cleaned['name']
        sheet_tab = cleaned['tab']
        interval = cleaned['refresh_interval']

        # Extract drive item ID from OneDrive/SharePoint URL
        item_id, drive_id = _extract_excel_item_id(access_token, file_url)
        if not item_id:
            return render(request, 'connectors/add_excel.html', connector_form_context(
                form_data=validation['form_data'],
                errors={'file_url': 'Could not locate this file in your OneDrive. Please paste the sharing URL from Excel Online.'},
            ))

        connector = DataConnector.objects.create(
            user=request.user,
            source=DataConnector.SOURCE_EXCEL_ONLINE,
            name=name,
            sheet_url=file_url,
            sheet_id=item_id,       # reuse sheet_id field for item ID
            sheet_tab=sheet_tab,
            access_token=access_token,
            refresh_token=request.session.get('ms_refresh_token', ''),
            refresh_interval_min=interval,
        )
        _sync_excel_online(connector)
        return redirect('connectors:list')

    return render(request, 'connectors/add_excel.html', connector_form_context(form_data={'refresh_interval': '60'}))


def _extract_excel_item_id(access_token: str, share_url: str):
    """Resolve a share URL to a Graph API drive item ID."""
    import base64
    # Encode URL as Graph sharing token
    encoded = base64.urlsafe_b64encode(share_url.encode()).rstrip(b'=').decode()
    share_token = f'u!{encoded}'

    resp = requests.get(
        f'https://graph.microsoft.com/v1.0/shares/{share_token}/driveItem',
        headers={'Authorization': f'Bearer {access_token}'},
        timeout=15,
    )
    if resp.ok:
        data = resp.json()
        return data.get('id', ''), data.get('parentReference', {}).get('driveId', '')
    return None, None


def _sync_excel_online(connector: DataConnector, *, trigger: str = 'manual'):
    log = start_connector_sync_log(connector, trigger=trigger)
    """Pull Excel file from Microsoft Graph and create/update a FileUpload."""
    import io, tempfile, os

    connector.sync_status = 'syncing'
    connector.save(update_fields=['sync_status'])

    try:
        # Refresh token if needed
        if connector.token_expiry and timezone.now() >= connector.token_expiry:
            _refresh_ms_token(connector)

        # Download the file as XLSX via Graph API
        item_id = connector.sheet_id
        resp = requests.get(
            f'https://graph.microsoft.com/v1.0/me/drive/items/{item_id}/content',
            headers={'Authorization': f'Bearer {connector.access_token}'},
            timeout=60, stream=True,
        )

        if not resp.ok:
            raise RuntimeError(f'Graph API error: {resp.status_code} {resp.text[:100]}')

        xlsx_bytes = resp.content
        if not xlsx_bytes:
            raise RuntimeError('Empty file returned from Microsoft')

        safe_name = f'ms_{connector.sheet_id[:8]}.xlsx'
        user_dir  = f'uploads/{connector.user_id}'
        full_dir  = f'{settings.MEDIA_ROOT}/{user_dir}'
        os.makedirs(full_dir, exist_ok=True)
        file_path = f'{full_dir}/{safe_name}'

        with open(file_path, 'wb') as f:
            f.write(xlsx_bytes)

        from apps.analyser.engine import analyse
        from apps.analyser.views import _sanitise_result

        result = _sanitise_result(analyse(
            file_path, 'excel',
            sheet_name=connector.sheet_tab or None,
        ))

        FileUpload.objects.update_or_create(
            user=connector.user,
            original_name=f'[Live] {connector.name}',
            defaults={
                'file':            f'{user_dir}/{safe_name}',
                'file_type':       'excel',
                'file_size':       len(xlsx_bytes),
                'status':          FileUpload.STATUS_DONE,
                'row_count':       result['rows'],
                'column_count':    result['cols'],
                'analysis_result': result,
                'label':           '🟢 Live',
            }
        )

        connector.last_synced_at = timezone.now()
        connector.row_count      = result['rows']
        connector.sync_status    = 'ok'
        connector.sync_error     = ''
        connector.schedule_next_sync()
        connector.save(update_fields=[
            'last_synced_at', 'row_count', 'sync_status', 'sync_error', 'next_sync_at',
        ])
        schema_columns, schema_signature = build_schema_snapshot(result)
        finish_connector_sync_log(log, connector, ok=True, row_count=result['rows'], message='Sync complete', schema_columns=schema_columns, schema_signature=schema_signature)

    except Exception as e:
        connector.sync_status = 'error'
        connector.sync_error  = str(e)[:500]
        connector.save(update_fields=['sync_status', 'sync_error'])
        finish_connector_sync_log(log, connector, ok=False, error_message=str(e), message='Sync failed')
        logger.error(f'Excel Online sync failed for connector {connector.id}: {e}')


def _refresh_ms_token(connector: DataConnector) -> str:
    """Refresh an expired Microsoft access token."""
    if not connector.refresh_token:
        return connector.access_token

    resp = requests.post(
        'https://login.microsoftonline.com/common/oauth2/v2.0/token',
        data={
            'client_id':     settings.MICROSOFT_OAUTH_CLIENT_ID,
            'client_secret': settings.MICROSOFT_OAUTH_CLIENT_SECRET,
            'refresh_token': connector.refresh_token,
            'grant_type':    'refresh_token',
        }, timeout=15,
    )
    if resp.ok:
        new_token = resp.json().get('access_token', '')
        connector.access_token = new_token
        from datetime import timedelta
        connector.token_expiry = timezone.now() + timedelta(
            seconds=resp.json().get('expires_in', 3600)
        )
        connector.save(update_fields=['access_token', 'token_expiry'])
        return new_token
    return connector.access_token



@login_required
def refresh_history(request):
    if not _require_connector_access(request.user):
        return render(request, 'connectors/upgrade_required.html')
    from apps.analyser.connector_models import ConnectorSyncLog
    logs = ConnectorSyncLog.objects.filter(connector__user=request.user).select_related('connector')[:100]
    return render(request, 'connectors/refresh_history.html', {'logs': logs})


@login_required
def scheduled_analytics(request):
    if not _require_connector_access(request.user):
        return render(request, 'connectors/upgrade_required.html')
    from apps.analyser.connector_models import ScheduledAnalyticsRun
    schedules = ScheduledAnalyticsRun.objects.filter(user=request.user).select_related('upload', 'analysis_view')
    return render(request, 'connectors/scheduled_analytics.html', {'schedules': schedules})


@login_required
def snapshot_timeline(request):
    if not _require_connector_access(request.user):
        return render(request, 'connectors/upgrade_required.html')
    from apps.analyser.connector_models import AnalysisSnapshot
    snapshots = AnalysisSnapshot.objects.filter(upload__user=request.user).select_related('upload', 'connector')[:100]
    return render(request, 'connectors/snapshot_timeline.html', {'snapshots': snapshots})
