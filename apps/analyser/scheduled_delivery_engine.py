from __future__ import annotations

from datetime import timedelta
from typing import Any, Dict, List

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone

from .connector_models import ScheduledAnalyticsRun, AnalysisSnapshot
from .models import FileUpload
from .executive_summary import build_executive_summary
from .decision_intelligence_engine import build_decision_dashboard

CADENCE_DELTAS = {"daily": timedelta(days=1), "weekly": timedelta(days=7), "monthly": timedelta(days=30)}


def schedule_next_run(schedule: ScheduledAnalyticsRun):
    schedule.next_run_at = timezone.now() + CADENCE_DELTAS.get(schedule.cadence, timedelta(days=7))
    return schedule.next_run_at


def normalize_recipients(raw: str | List[str]) -> List[str]:
    if isinstance(raw, list):
        vals = raw
    else:
        vals = [v.strip() for v in (raw or '').replace(';', ',').split(',')]
    clean=[]
    for v in vals:
        if v and v not in clean:
            clean.append(v)
    return clean


def schedule_payload(upload: FileUpload, analysis: Dict[str, Any]) -> Dict[str, Any]:
    summary = build_executive_summary(analysis, chart_count=upload.chart_configs.count())
    charts = list(upload.chart_configs.all().order_by('sort_order', 'created_at')[:8])
    dashboard = build_decision_dashboard(analysis, charts, mode='executive')
    return {
        'headline': summary.headline,
        'opportunity': summary.opportunity,
        'risk': summary.risk,
        'action': summary.action,
        'sections': [
            {'title': s.get('title', ''), 'chart_titles': [getattr(c, 'title', '') for c in (s.get('charts') or [])[:5]]}
            for s in (dashboard.get('sections') or [])[:5]
        ],
        'decision_cards': dashboard.get('decision_cards') or [],
        'benchmark_summary': analysis.get('benchmark_summary') or {},
        'time_intelligence': analysis.get('time_intelligence') or {},
        'scenario_context': analysis.get('scenario_context') or {},
        'generated_at': timezone.now().isoformat(),
    }


def snapshot_schedule(schedule: ScheduledAnalyticsRun) -> AnalysisSnapshot:
    upload = schedule.upload
    analysis = upload.analysis_result or {}
    summary_json = schedule_payload(upload, analysis)
    chart_payloads = []
    for chart in upload.chart_configs.all().order_by('sort_order', 'created_at')[:12]:
        chart_payloads.append({'title': chart.title, 'chart_type': chart.chart_type, 'x_axis': chart.x_axis, 'y_axis': chart.y_axis, 'size': chart.size})
    alerts = []
    for card in (summary_json.get('decision_cards') or [])[:5]:
        alerts.append({'title': card.get('title', ''), 'message': card.get('message', ''), 'severity': card.get('severity', '')})
    return AnalysisSnapshot.objects.create(upload=upload, summary_json=summary_json, chart_payloads_json=chart_payloads, alerts_json=alerts)


def deliver_schedule(schedule: ScheduledAnalyticsRun) -> Dict[str, Any]:
    snapshot = snapshot_schedule(schedule)
    recipients = schedule.recipients or []
    if schedule.delivery_mode == 'email' and recipients:
        site = getattr(settings, 'SITE_URL', 'http://localhost:8000')
        subject = f"[Nexyza] {schedule.title} — {timezone.now().strftime('%b %d, %Y')}"
        ctx = {'schedule': schedule, 'upload': schedule.upload, 'snapshot': snapshot, 'site_url': site, 'workspace_url': f"{site}/workspace/{schedule.upload.id}/charts/"}
        text_body = render_to_string('analyser/email/scheduled_delivery.txt', ctx)
        html_body = render_to_string('analyser/email/scheduled_delivery.html', ctx)
        msg = EmailMultiAlternatives(subject=subject, body=text_body, from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'hello@nexyza.com'), to=recipients)
        msg.attach_alternative(html_body, 'text/html')
        msg.send(fail_silently=False)
    schedule.status = 'ok'
    schedule.last_error = ''
    schedule.last_run_at = timezone.now()
    schedule_next_run(schedule)
    schedule.save(update_fields=['status', 'last_error', 'last_run_at', 'next_run_at', 'updated_at'])
    return {'snapshot_id': str(snapshot.id), 'recipients': recipients, 'delivery_mode': schedule.delivery_mode}
