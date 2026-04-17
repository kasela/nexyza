from __future__ import annotations

import hashlib

from typing import Dict, Any, Tuple
from statistics import mean

from django.utils import timezone
from django.db.models import Q

from apps.analyser.connector_models import DataConnector, ConnectorSyncLog, ConnectorAlertRule


SYNC_TONE = {
    'ok': {'label': 'Live', 'dot': '●', 'color': '#34d399'},
    'error': {'label': 'Error', 'dot': '⚠', 'color': '#f87171'},
    'syncing': {'label': 'Syncing', 'dot': '⟳', 'color': '#fbbf24'},
    'idle': {'label': 'Idle', 'dot': '◯', 'color': '#94a3b8'},
}

ALLOWED_REFRESH_INTERVALS = {0, 15, 30, 60, 360, 1440}


def build_schema_snapshot(result: Dict[str, Any] | None) -> tuple[list[dict[str, Any]], str]:
    columns = []
    for col in (result or {}).get('columns', []) or []:
        columns.append({
            'name': str(col.get('name', '')),
            'dtype': str(col.get('dtype', '')),
            'is_numeric': bool(col.get('is_numeric')),
        })
    signature_src = '|'.join(f"{c['name']}::{c['dtype']}::{int(c['is_numeric'])}" for c in columns)
    signature = hashlib.sha1(signature_src.encode('utf-8')).hexdigest() if signature_src else ''
    return columns, signature


def _schema_drift(current: list[dict[str, Any]] | None, previous: list[dict[str, Any]] | None) -> Dict[str, Any]:
    current = current or []
    previous = previous or []
    prev_map = {str(c.get('name', '')): c for c in previous if c.get('name')}
    curr_map = {str(c.get('name', '')): c for c in current if c.get('name')}
    added = sorted([name for name in curr_map if name not in prev_map])
    removed = sorted([name for name in prev_map if name not in curr_map])
    type_changes = []
    for name in sorted(set(curr_map).intersection(prev_map)):
        old_t = str(prev_map[name].get('dtype', ''))
        new_t = str(curr_map[name].get('dtype', ''))
        if old_t != new_t:
            type_changes.append({'name': name, 'from': old_t, 'to': new_t})
    return {
        'has_changes': bool(added or removed or type_changes),
        'added': added,
        'removed': removed,
        'type_changes': type_changes,
        'summary': f"+{len(added)} / -{len(removed)} / Δ{len(type_changes)}" if (added or removed or type_changes) else 'No schema drift detected',
    }


def connector_health_payload(connector: DataConnector) -> Dict[str, Any]:
    logs = list(connector.sync_logs.all()[:12])
    successful = [log for log in logs if log.status == 'ok']
    latest = logs[0] if logs else None
    previous_success = successful[1] if len(successful) > 1 else None
    latest_success = successful[0] if successful else None
    row_values = [int(log.row_count or 0) for log in successful[:6] if (log.row_count or 0) >= 0]
    avg_rows = round(mean(row_values), 1) if row_values else 0
    last_rows = latest_success.row_count if latest_success else 0
    row_delta = 0
    row_delta_pct = 0
    if latest_success and previous_success:
        row_delta = (latest_success.row_count or 0) - (previous_success.row_count or 0)
        base = previous_success.row_count or 0
        row_delta_pct = round((row_delta / base) * 100, 1) if base else 0
    success_rate = round((len(successful) / len(logs)) * 100, 0) if logs else 100
    stale = bool(connector.refresh_interval_min and connector.next_sync_at and connector.next_sync_at < timezone.now() and connector.sync_status != 'syncing')
    warnings = []
    if connector.sync_status == 'error':
        warnings.append({'tone': 'error', 'label': 'Latest sync failed'})
    if stale:
        warnings.append({'tone': 'warn', 'label': 'Connector is overdue for sync'})
    if latest_success and latest_success.row_count == 0:
        warnings.append({'tone': 'warn', 'label': 'Latest successful sync returned zero rows'})
    if abs(row_delta_pct) >= 30:
        warnings.append({'tone': 'warn', 'label': f'Row count changed {row_delta_pct:+.1f}% vs previous successful sync'})
    drift = _schema_drift(getattr(latest_success, 'schema_columns', []) if latest_success else [], getattr(previous_success, 'schema_columns', []) if previous_success else [])
    if drift['has_changes']:
        warnings.append({'tone': 'info', 'label': f"Schema drift detected: {drift['summary']}"})
    return {
        'success_rate': success_rate,
        'avg_rows': avg_rows,
        'last_rows': last_rows,
        'row_delta': row_delta,
        'row_delta_pct': row_delta_pct,
        'stale': stale,
        'warnings': warnings,
        'schema_drift': drift,
        'latest_schema_columns': len(getattr(latest_success, 'schema_columns', []) or []),
    }


def _human_next_sync(connector: DataConnector) -> str:
    if connector.refresh_interval_min == 0:
        return 'Manual only'
    if not connector.next_sync_at:
        return 'Pending schedule'
    delta = connector.next_sync_at - timezone.now()
    if delta.total_seconds() <= 0:
        return 'Due now'
    minutes = max(1, int(delta.total_seconds() // 60))
    if minutes < 60:
        return f'In {minutes} min'
    hours = minutes // 60
    rem = minutes % 60
    return f'In {hours}h {rem}m' if rem else f'In {hours}h'


def connector_status_payload(connector: DataConnector) -> Dict[str, Any]:
    tone = SYNC_TONE.get(connector.sync_status, SYNC_TONE['idle'])
    upload = connector.upload_set.order_by('-created_at').first()
    return {
        'id': str(connector.id),
        'name': connector.name,
        'status': connector.sync_status,
        'status_label': tone['label'],
        'status_dot': tone['dot'],
        'status_color': tone['color'],
        'last_synced_at': connector.last_synced_at.isoformat() if connector.last_synced_at else None,
        'last_synced_human': timezone.localtime(connector.last_synced_at).strftime('%Y-%m-%d %H:%M') if connector.last_synced_at else 'Never synced',
        'next_sync_human': _human_next_sync(connector),
        'row_count': connector.row_count or 0,
        'refresh_interval_min': connector.refresh_interval_min,
        'sync_error': connector.sync_error or '',
        'upload_id': str(upload.id) if upload else None,
        'has_upload': bool(upload),
        'upload_url': f'/workspace/{upload.id}/' if upload else '',
        'source_label': connector.source_label,
    }


def connector_summary_payload(connectors) -> Dict[str, Any]:
    items = list(connectors)
    return {
        'total': len(items),
        'live': sum(1 for c in items if c.sync_status == 'ok'),
        'syncing': sum(1 for c in items if c.sync_status == 'syncing'),
        'errors': sum(1 for c in items if c.sync_status == 'error'),
        'manual_only': sum(1 for c in items if c.refresh_interval_min == 0),
        'rows_total': sum((c.row_count or 0) for c in items),
    }


def _clean_interval(raw_value: Any) -> Tuple[int, str | None]:
    if raw_value in (None, ''):
        return 60, None
    try:
        interval = int(raw_value)
    except (TypeError, ValueError):
        return 60, 'Choose a valid refresh interval.'
    if interval not in ALLOWED_REFRESH_INTERVALS:
        return 60, 'Choose one of the available refresh intervals.'
    return interval, None


def validate_google_sheet_form(data: Any) -> Dict[str, Any]:
    form_data = {
        'sheet_url': (data.get('sheet_url', '') if data else '').strip(),
        'name': (data.get('name', '') if data else '').strip(),
        'tab': (data.get('tab', '') if data else '').strip(),
        'refresh_interval': str(data.get('refresh_interval', '60') if data else '60').strip() or '60',
    }
    errors: Dict[str, str] = {}

    if not form_data['sheet_url']:
        errors['sheet_url'] = 'Paste the full Google Sheets URL.'
    elif 'docs.google.com/spreadsheets/' not in form_data['sheet_url']:
        errors['sheet_url'] = 'Enter a valid Google Sheets URL.'

    if form_data['name'] and len(form_data['name']) > 200:
        errors['name'] = 'Connection name must be 200 characters or fewer.'

    if len(form_data['tab']) > 200:
        errors['tab'] = 'Sheet tab name must be 200 characters or fewer.'

    interval, interval_error = _clean_interval(form_data['refresh_interval'])
    if interval_error:
        errors['refresh_interval'] = interval_error

    cleaned = {
        'sheet_url': form_data['sheet_url'],
        'name': form_data['name'] or 'Google Sheet',
        'tab': form_data['tab'],
        'refresh_interval': interval,
    }
    return {'cleaned_data': cleaned, 'form_data': form_data, 'errors': errors}


def validate_excel_online_form(data: Any) -> Dict[str, Any]:
    form_data = {
        'file_url': (data.get('file_url', '') if data else '').strip(),
        'name': (data.get('name', '') if data else '').strip(),
        'tab': (data.get('tab', '') if data else '').strip(),
        'refresh_interval': str(data.get('refresh_interval', '60') if data else '60').strip() or '60',
    }
    errors: Dict[str, str] = {}

    if not form_data['file_url']:
        errors['file_url'] = 'Paste the Excel Online sharing URL.'
    elif not any(token in form_data['file_url'].lower() for token in ('onedrive', 'sharepoint', 'office.com')):
        errors['file_url'] = 'Enter a valid OneDrive, SharePoint, or Excel Online sharing URL.'

    if form_data['name'] and len(form_data['name']) > 200:
        errors['name'] = 'Connection name must be 200 characters or fewer.'

    if len(form_data['tab']) > 200:
        errors['tab'] = 'Sheet / tab name must be 200 characters or fewer.'

    interval, interval_error = _clean_interval(form_data['refresh_interval'])
    if interval_error:
        errors['refresh_interval'] = interval_error

    cleaned = {
        'file_url': form_data['file_url'],
        'name': form_data['name'] or 'Excel File',
        'tab': form_data['tab'],
        'refresh_interval': interval,
    }
    return {'cleaned_data': cleaned, 'form_data': form_data, 'errors': errors}


def connector_form_context(*, form_data: Dict[str, Any] | None = None, errors: Dict[str, str] | None = None, non_field_error: str = '') -> Dict[str, Any]:
    return {
        'form_data': form_data or {},
        'field_errors': errors or {},
        'error': non_field_error,
    }



def start_connector_sync_log(connector: DataConnector, *, trigger: str = 'manual') -> ConnectorSyncLog:
    return ConnectorSyncLog.objects.create(
        connector=connector,
        trigger=trigger if trigger in {'manual', 'auto', 'retry', 'initial'} else 'manual',
        status='syncing',
        message='Sync started',
    )


def finish_connector_sync_log(log: ConnectorSyncLog | None, connector: DataConnector, *, ok: bool, row_count: int = 0, message: str = '', error_message: str = '', schema_columns: list[dict[str, Any]] | None = None, schema_signature: str = '') -> None:
    if not log:
        return
    log.status = 'ok' if ok else 'error'
    log.row_count = row_count or 0
    log.message = (message or ('Sync complete' if ok else 'Sync failed'))[:255]
    log.error_message = (error_message or '')[:1000]
    log.schema_columns = schema_columns or []
    log.schema_signature = schema_signature or ''
    log.alerts = evaluate_connector_alerts(connector, ok=ok, row_count=row_count or 0, schema_columns=schema_columns or [])
    log.completed_at = timezone.now()
    log.save(update_fields=['status', 'row_count', 'message', 'error_message', 'schema_columns', 'schema_signature', 'alerts', 'completed_at'])


def connector_history_item_payload(log: ConnectorSyncLog) -> Dict[str, Any]:
    return {
        'id': log.id,
        'status': log.status,
        'trigger': log.trigger,
        'row_count': log.row_count or 0,
        'message': log.message or ('Sync complete' if log.status == 'ok' else 'Sync failed'),
        'error_message': log.error_message or '',
        'started_at': log.started_at.isoformat() if log.started_at else None,
        'completed_at': log.completed_at.isoformat() if log.completed_at else None,
        'started_human': timezone.localtime(log.started_at).strftime('%Y-%m-%d %H:%M') if log.started_at else '',
        'completed_human': timezone.localtime(log.completed_at).strftime('%Y-%m-%d %H:%M') if log.completed_at else '',
        'can_retry': log.status == 'error',
        'notes': log.notes or '',
        'schema_signature': log.schema_signature or '',
        'schema_columns': log.schema_columns or [],
        'alerts': log.alerts or [],
    }


def connector_history_payload(connector: DataConnector, *, limit: int = 8) -> Dict[str, Any]:
    logs = list(connector.sync_logs.all()[:limit])
    return {
        'connector_id': str(connector.id),
        'items': [connector_history_item_payload(log) for log in logs],
    }


def connector_detail_payload(connector: DataConnector) -> Dict[str, Any]:
    payload = connector_status_payload(connector)
    payload.update({
        'sheet_tab': connector.sheet_tab or '',
        'range_spec': connector.range_spec or '',
        'created_at': connector.created_at.isoformat() if connector.created_at else None,
        'created_human': timezone.localtime(connector.created_at).strftime('%Y-%m-%d %H:%M') if connector.created_at else '',
        'updated_human': timezone.localtime(connector.updated_at).strftime('%Y-%m-%d %H:%M') if connector.updated_at else '',
        'sheet_url': connector.sheet_url or '',
    })
    return payload


def connector_history_payload_filtered(connector: DataConnector, *, status: str = '', trigger: str = '', query: str = '', limit: int = 50) -> Dict[str, Any]:
    logs = connector.sync_logs.all()
    if status in {'ok', 'error', 'syncing'}:
        logs = logs.filter(status=status)
    if trigger in {'manual', 'auto', 'retry', 'initial'}:
        logs = logs.filter(trigger=trigger)
    if query:
        logs = logs.filter(Q(message__icontains=query) | Q(error_message__icontains=query) | Q(notes__icontains=query))
    logs = list(logs[:limit])
    return {
        'connector_id': str(connector.id),
        'filters': {'status': status, 'trigger': trigger, 'query': query},
        'items': [connector_history_item_payload(log) for log in logs],
    }


def validate_sync_note(note: Any) -> Tuple[str, Dict[str, str]]:
    cleaned = (str(note or '')).strip()
    errors: Dict[str, str] = {}
    if len(cleaned) > 2000:
        errors['notes'] = 'Notes must be 2000 characters or fewer.'
    return cleaned, errors


def alert_rule_payload(rule: ConnectorAlertRule) -> Dict[str, Any]:
    return {
        'id': str(rule.id),
        'rule_type': rule.rule_type,
        'rule_label': dict(ConnectorAlertRule.RULE_CHOICES).get(rule.rule_type, rule.rule_type),
        'threshold': rule.threshold,
        'action': rule.action or '',
        'action_label': dict(ConnectorAlertRule.ACTION_CHOICES).get(rule.action or '', 'No Action'),
        'is_active': bool(rule.is_active),
    }


def connector_alert_rules_payload(connector: DataConnector) -> Dict[str, Any]:
    rules = list(connector.alert_rules.all())
    return {
        'connector_id': str(connector.id),
        'items': [alert_rule_payload(rule) for rule in rules],
    }


def validate_alert_rule_form(data: Any) -> Dict[str, Any]:
    rule_type = str((data.get('rule_type') if data else '') or '').strip()
    action = str((data.get('action') if data else '') or '').strip()
    raw_threshold = str((data.get('threshold') if data else '') or '').strip()
    errors: Dict[str, str] = {}
    if rule_type not in {choice[0] for choice in ConnectorAlertRule.RULE_CHOICES}:
        errors['rule_type'] = 'Choose a valid alert rule.'
    if action not in {choice[0] for choice in ConnectorAlertRule.ACTION_CHOICES}:
        errors['action'] = 'Choose a valid alert action.'
    threshold = None
    if rule_type in {ConnectorAlertRule.RULE_ROW_DROP, ConnectorAlertRule.RULE_ROW_SPIKE, ConnectorAlertRule.RULE_STALE}:
        if not raw_threshold:
            errors['threshold'] = 'Enter a threshold for this rule.'
        else:
            try:
                threshold = float(raw_threshold)
            except (TypeError, ValueError):
                errors['threshold'] = 'Enter a valid numeric threshold.'
            else:
                if threshold < 0:
                    errors['threshold'] = 'Threshold must be zero or greater.'
    return {
        'errors': errors,
        'cleaned_data': {'rule_type': rule_type, 'action': action, 'threshold': threshold},
    }


def evaluate_connector_alerts(connector: DataConnector, *, ok: bool, row_count: int = 0, schema_columns: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    rules = list(connector.alert_rules.filter(is_active=True))
    if not rules:
        return []
    now = timezone.now()
    prev_success = connector.sync_logs.filter(status='ok').exclude(completed_at__isnull=True).order_by('-completed_at').first()
    prev_rows = int(getattr(prev_success, 'row_count', 0) or 0)
    drift = _schema_drift(schema_columns or [], getattr(prev_success, 'schema_columns', []) if prev_success else [])
    alerts = []
    for rule in rules:
        fired = False
        message = ''
        if rule.rule_type == ConnectorAlertRule.RULE_SYNC_FAILED and not ok:
            fired = True
            message = 'Sync failed'
        elif rule.rule_type == ConnectorAlertRule.RULE_ROW_DROP and ok and prev_success and prev_rows > 0 and row_count < prev_rows:
            pct = ((prev_rows - row_count) / prev_rows) * 100
            if pct >= float(rule.threshold or 0):
                fired = True
                message = f'Row count dropped {pct:.1f}%'
        elif rule.rule_type == ConnectorAlertRule.RULE_ROW_SPIKE and ok and prev_success and prev_rows > 0 and row_count > prev_rows:
            pct = ((row_count - prev_rows) / prev_rows) * 100
            if pct >= float(rule.threshold or 0):
                fired = True
                message = f'Row count increased {pct:.1f}%'
        elif rule.rule_type == ConnectorAlertRule.RULE_SCHEMA_CHANGE and ok and prev_success and drift['has_changes']:
            fired = True
            message = f"Schema drift detected: {drift['summary']}"
        elif rule.rule_type == ConnectorAlertRule.RULE_STALE and connector.last_synced_at:
            minutes = (now - connector.last_synced_at).total_seconds() / 60
            if minutes >= float(rule.threshold or 0):
                fired = True
                message = f'No successful sync for {int(minutes)} minutes'
        if fired:
            alerts.append({
                'rule_id': str(rule.id),
                'rule_type': rule.rule_type,
                'label': message,
                'action': rule.action or '',
            })
    return alerts
