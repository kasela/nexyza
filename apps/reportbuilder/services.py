import json
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.urls import reverse
from apps.analyser.models import FileUpload, ChartConfig
from .models import ScheduledReport, ReportExportJob, ReportSection


def build_error(message, field_errors=None, status=400):
    return {
        "ok": False,
        "error": message,
        "field_errors": field_errors or {},
        "status": status,
    }


def validate_schedule_payload(data, fallback_email=""):
    frequency = (data.get("frequency") or "weekly").strip().lower()
    email = (data.get("email") or "").strip() or (fallback_email or "").strip()
    field_errors = {}

    allowed = {choice[0] for choice in ScheduledReport.FREQ_CHOICES}
    if frequency not in allowed:
        field_errors["frequency"] = "Choose daily, weekly, or monthly."

    if not email:
        field_errors["email"] = "Email is required."
    else:
        try:
            validate_email(email)
        except ValidationError:
            field_errors["email"] = "Enter a valid email address."

    if field_errors:
        return None, build_error("Please correct the highlighted schedule fields.", field_errors)

    return {"frequency": frequency, "email": email}, None


def validate_export_format(fmt):
    fmt = (fmt or "pdf").strip().lower()
    if fmt not in {"pdf"}:
        return None, build_error("Unsupported export format.", {"format": "Only PDF export is available right now."})
    return fmt, None


def queue_report_export_job(report, user, fmt):
    fmt, error = validate_export_format(fmt)
    if error:
        return None, error

    job = ReportExportJob.objects.create(
        report=report,
        user=user,
        fmt=fmt,
        status=ReportExportJob.STATUS_PENDING,
        status_message='Queued',
    )
    try:
        job.result_url = reverse('reportbuilder:export_download', args=[job.id])
        job.status = ReportExportJob.STATUS_DONE
        job.status_message = 'Ready to download'
        job.save(update_fields=['result_url', 'status', 'status_message', 'updated_at'])
        return job, None
    except Exception as exc:
        job.status = ReportExportJob.STATUS_ERROR
        job.error = str(exc)
        job.status_message = 'Export failed'
        job.save(update_fields=['status', 'error', 'status_message', 'updated_at'])
        return job, None


def _allowed_section_types():
    return {choice[0] for choice in ReportSection.SECTION_TYPES}


def validate_section_payload(report, user, data):
    stype = (data.get('section_type') or 'text').strip()
    field_errors = {}
    if stype not in _allowed_section_types():
        field_errors['section_type'] = 'Choose a valid section type.'
        return None, build_error('Please correct the section settings.', field_errors)

    content = {}
    if stype == 'heading':
        text = (data.get('text') or 'New Heading').strip()
        level_raw = data.get('level', 1)
        try:
            level = int(level_raw)
        except (TypeError, ValueError):
            level = 1
        if level not in {1, 2, 3}:
            field_errors['level'] = 'Heading level must be 1, 2, or 3.'
        if not text:
            field_errors['text'] = 'Heading text is required.'
        content = {'text': text, 'level': level}

    elif stype == 'text':
        text = (data.get('text') or 'Add your text here…').strip()
        if not text:
            field_errors['text'] = 'Text content is required.'
        content = {'text': text}

    elif stype == 'chart':
        chart_id = (data.get('chart_id') or '').strip()
        if not chart_id:
            field_errors['chart_id'] = 'Select a chart.'
        else:
            try:
                chart = ChartConfig.objects.select_related('upload').get(pk=chart_id, upload__user=user)
                content = {'chart_id': str(chart.id)}
            except ChartConfig.DoesNotExist:
                field_errors['chart_id'] = 'Selected chart was not found.'

    elif stype in {'stats', 'ai_insights', 'table'}:
        upload_id = (data.get('upload_id') or '').strip()
        if not upload_id:
            field_errors['upload_id'] = 'Select a dataset.'
        else:
            try:
                upload = FileUpload.objects.get(pk=upload_id, user=user)
                content = {'upload_id': str(upload.id)}
                if stype == 'table':
                    rows_raw = data.get('rows', 10)
                    try:
                        rows = int(rows_raw)
                    except (TypeError, ValueError):
                        rows = 10
                    if rows < 1 or rows > 100:
                        field_errors['rows'] = 'Table rows must be between 1 and 100.'
                    content['rows'] = max(1, min(rows, 100))
            except FileUpload.DoesNotExist:
                field_errors['upload_id'] = 'Selected dataset was not found.'

    elif stype == 'divider':
        content = {}

    elif stype == 'forecast':
        chart_id = (data.get('chart_id') or '').strip()
        if not chart_id:
            field_errors['chart_id'] = 'Select a chart to forecast.'
        else:
            try:
                chart = ChartConfig.objects.select_related('upload').get(pk=chart_id, upload__user=user)
                content = {'chart_id': str(chart.id)}
            except ChartConfig.DoesNotExist:
                field_errors['chart_id'] = 'Selected chart was not found.'

    if field_errors:
        return None, build_error('Please correct the section settings.', field_errors)
    return {'section_type': stype, 'content': content}, None


def create_report_section(report, user, data):
    payload, error = validate_section_payload(report, user, data)
    if error:
        return None, error
    sec = ReportSection.objects.create(
        report=report,
        section_type=payload['section_type'],
        sort_order=report.section_rows.count(),
        content=payload['content'],
    )
    return sec, None


def update_report_section(section, data):
    content = dict(section.content or {})
    field_errors = {}
    if section.section_type in {'heading', 'text'}:
        text = (data.get('text') or '').strip()
        if not text:
            field_errors['text'] = 'Text content is required.'
        content['text'] = text
        if section.section_type == 'heading':
            level_raw = data.get('level', content.get('level', 1))
            try:
                level = int(level_raw)
            except (TypeError, ValueError):
                level = content.get('level', 1)
            if level not in {1, 2, 3}:
                field_errors['level'] = 'Heading level must be 1, 2, or 3.'
            content['level'] = level
    else:
        field_errors['section'] = 'Only heading and text sections can be edited inline right now.'

    if field_errors:
        return None, build_error('Please correct the section content.', field_errors)

    section.content = content
    section.save(update_fields=['content'])
    return section, None


def delete_report_section(section):
    report = section.report
    removed_order = section.sort_order
    section.delete()
    for idx, sec in enumerate(report.section_rows.order_by('sort_order', 'created_at')):
        if sec.sort_order != idx:
            sec.sort_order = idx
            sec.save(update_fields=['sort_order'])
    return {'ok': True, 'removed_order': removed_order}


def reorder_report_sections(report, order):
    if isinstance(order, str):
        try:
            order = json.loads(order or '[]')
        except json.JSONDecodeError:
            return build_error('Invalid section order payload.', {'order': 'Could not parse section order.'})

    if not isinstance(order, list):
        return build_error('Invalid section order payload.', {'order': 'Order must be a list of section IDs.'})

    existing_ids = list(report.section_rows.values_list('id', flat=True))
    existing_str = {str(i) for i in existing_ids}
    order_str = [str(i) for i in order]
    if set(order_str) != existing_str:
        return build_error('Invalid section order payload.', {'order': 'Order must include every section exactly once.'})

    mapping = {str(sec.id): sec for sec in report.section_rows.all()}
    for idx, sid in enumerate(order_str):
        sec = mapping[sid]
        if sec.sort_order != idx:
            sec.sort_order = idx
            sec.save(update_fields=['sort_order'])
    return {'ok': True, 'count': len(order_str)}
