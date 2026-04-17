"""
Report Builder — drag-and-drop report construction with charts, AI insights,
stats tables, and PDF/PPTX export.
"""
import json
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.http import require_POST
from django.http import HttpResponse, JsonResponse
from django.urls import reverse
from django.contrib import messages
from django.utils import timezone
from apps.analyser.models import FileUpload, ChartConfig
from apps.analyser.charts import build_chart_data
from .models import Report, ReportSection, ScheduledReport, ReportExportJob
from .services import (
    validate_schedule_payload, queue_report_export_job, build_error,
    create_report_section, update_report_section, delete_report_section, reorder_report_sections,
)


@login_required
def report_list(request):
    reports = Report.objects.filter(user=request.user)
    uploads = FileUpload.objects.filter(user=request.user, status='done')
    return render(request, 'reportbuilder/list.html', {
        'reports': reports, 'uploads': uploads,
        'cover_colors': ['#7c3aed','#3b82f6','#10b981','#f59e0b','#ef4444','#06b6d4','#ec4899'],
    })


@login_required
@require_POST
def create_report(request):
    r = Report.objects.create(
        user=request.user,
        title=request.POST.get('title', 'Untitled Report'),
        description=request.POST.get('description', ''),
        cover_color=request.POST.get('cover_color', '#7c3aed'),
    )
    return redirect('reportbuilder:builder', pk=r.pk)


@login_required
def builder(request, pk):
    report  = get_object_or_404(Report, pk=pk, user=request.user)
    uploads = FileUpload.objects.filter(user=request.user, status='done')
    # Build section list with chart data resolved
    sections = []
    for sec in report.section_rows.all():
        s = {'id': sec.id, 'type': sec.section_type,
             'sort_order': sec.sort_order, 'content': sec.content}
        if sec.section_type == 'chart' and sec.content.get('chart_id'):
            try:
                chart = ChartConfig.objects.get(pk=sec.content['chart_id'])
                s['chart'] = chart
                s['chart_data'] = chart.cached_data or {}
            except ChartConfig.DoesNotExist:
                pass
        sections.append(s)

    # Charts available for this report's uploads
    all_charts = ChartConfig.objects.filter(
        upload__user=request.user, upload__status='done'
    ).select_related('upload').order_by('-upload__created_at', 'sort_order')

    return render(request, 'reportbuilder/builder.html', {
        'report': report,
        'sections': sections,
        'uploads': uploads,
        'all_charts': all_charts,
        'section_types': ReportSection.SECTION_TYPES,
        'active_schedule': report.schedules.filter(user=request.user, is_active=True).order_by('-created_at').first(),
    })


@login_required
@require_POST
def add_section(request, pk):
    report = get_object_or_404(Report, pk=pk, user=request.user)
    sec, error = create_report_section(report, request.user, request.POST)
    if error:
        if request.htmx or request.headers.get('x-requested-with') == 'XMLHttpRequest':
            return JsonResponse(error, status=error.get('status', 400))
        messages.error(request, error.get('error', 'Could not add section.'))
        return redirect('reportbuilder:builder', pk=pk)

    if request.htmx:
        from django.template.loader import render_to_string
        return HttpResponse(render_to_string(
            'reportbuilder/partials/section.html',
            {'sec': _resolve_section(sec), 'report': report},
            request=request,
        ))
    return redirect('reportbuilder:builder', pk=pk)


@login_required
@require_POST
def update_section(request, pk, section_id):
    report = get_object_or_404(Report, pk=pk, user=request.user)
    sec = get_object_or_404(ReportSection, pk=section_id, report=report)
    sec, error = update_report_section(sec, request.POST)
    if error:
        return JsonResponse(error, status=error.get('status', 400))
    return JsonResponse({'ok': True, 'content': sec.content})


@login_required
@require_POST
def delete_section(request, pk, section_id):
    report = get_object_or_404(Report, pk=pk, user=request.user)
    sec = get_object_or_404(ReportSection, pk=section_id, report=report)
    payload = delete_report_section(sec)
    if request.htmx:
        return HttpResponse('')
    return JsonResponse(payload)


@login_required
@require_POST
def reorder_sections(request, pk):
    report = get_object_or_404(Report, pk=pk, user=request.user)
    payload = reorder_report_sections(report, request.POST.get('order', '[]'))
    status = payload.pop('status', 200) if isinstance(payload, dict) else 200
    return JsonResponse(payload, status=status)


@login_required
@require_POST
def update_report_meta(request, pk):
    report = get_object_or_404(Report, pk=pk, user=request.user)
    report.title       = request.POST.get('title', report.title)
    report.description = request.POST.get('description', report.description)
    report.cover_color = request.POST.get('cover_color', report.cover_color)
    report.save(update_fields=['title', 'description', 'cover_color', 'updated_at'])
    return JsonResponse({'ok': True, 'title': report.title})


@login_required
def export_report_pdf(request, pk):
    report = get_object_or_404(Report, pk=pk, user=request.user)
    try:
        data  = _build_report_pdf(report)
        fname = report.title.replace(' ', '_')[:40]
        resp  = HttpResponse(data, content_type='application/pdf')
        resp['Content-Disposition'] = f'attachment; filename="{fname}_report.pdf"'
        return resp
    except Exception as e:
        messages.error(request, f'PDF export failed: {e}')
        return redirect('reportbuilder:builder', pk=pk)


@login_required
def public_report(request, token):
    report = get_object_or_404(Report, share_token=token, is_public=True)
    sections = [_resolve_section(s) for s in report.section_rows.all()]
    return render(request, 'reportbuilder/public.html', {
        'report': report, 'sections': sections
    })


@login_required
@require_POST
def toggle_public(request, pk):
    report = get_object_or_404(Report, pk=pk, user=request.user)
    if not report.is_public:
        report.generate_share_token()
    report.is_public = not report.is_public
    report.save(update_fields=['is_public', 'share_token'])
    return JsonResponse({'ok': True, 'is_public': report.is_public,
                         'token': report.share_token})


@login_required
def delete_report(request, pk):
    report = get_object_or_404(Report, pk=pk, user=request.user)
    if request.method == 'POST':
        report.delete()
        messages.success(request, 'Report deleted.')
        return redirect('reportbuilder:list')
    return render(request, 'reportbuilder/list.html')




@login_required
@require_POST
def queue_report_export(request, pk, fmt):
    report = get_object_or_404(Report, pk=pk, user=request.user)
    job, error = queue_report_export_job(report, request.user, fmt)
    if error:
        return JsonResponse(error, status=error.get('status', 400))
    return JsonResponse({
        'ok': True,
        'job_id': str(job.id),
        'status': job.status,
        'message': job.status_message,
        'download_url': job.result_url,
    })


@login_required
def report_export_history(request, pk):
    report = get_object_or_404(Report, pk=pk, user=request.user)
    jobs = report.export_jobs.filter(user=request.user)[:10]
    return JsonResponse({'jobs': [
        {
            'id': str(job.id),
            'fmt': job.fmt,
            'status': job.status,
            'message': job.status_message or '',
            'error': job.error or '',
            'created_at': timezone.localtime(job.created_at).strftime('%Y-%m-%d %H:%M'),
            'download_url': job.result_url or '',
        } for job in jobs
    ]})


@login_required
@require_POST
def retry_report_export(request, job_id):
    prev = get_object_or_404(ReportExportJob.objects.select_related('report'), pk=job_id, user=request.user)
    job, error = queue_report_export_job(prev.report, request.user, prev.fmt)
    if error:
        return JsonResponse(error, status=error.get('status', 400))
    return JsonResponse({
        'ok': True,
        'job_id': str(job.id),
        'status': job.status,
        'message': job.status_message,
        'download_url': job.result_url,
    })


@login_required
def report_export_download(request, job_id):
    job = get_object_or_404(ReportExportJob.objects.select_related('report'), pk=job_id, user=request.user)
    if job.fmt != 'pdf':
        return HttpResponse('Unsupported format', status=400)
    data = _build_report_pdf(job.report)
    fname = job.report.title.replace(' ', '_')[:40]
    resp = HttpResponse(data, content_type='application/pdf')
    resp['Content-Disposition'] = f'attachment; filename="{fname}_report.pdf"'
    return resp

# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_section(sec):
    s = {'id': sec.id, 'type': sec.section_type,
         'sort_order': sec.sort_order, 'content': sec.content}
    if sec.section_type == 'chart' and sec.content.get('chart_id'):
        try:
            chart = ChartConfig.objects.get(pk=sec.content['chart_id'])
            s['chart'] = chart
            s['chart_data'] = chart.cached_data or {}
        except ChartConfig.DoesNotExist:
            pass
    if sec.section_type in ('stats', 'ai_insights', 'table') and sec.content.get('upload_id'):
        try:
            upload = FileUpload.objects.get(pk=sec.content['upload_id'])
            s['upload'] = upload
            s['analysis'] = upload.analysis_result or {}
        except FileUpload.DoesNotExist:
            pass
    return s


def _build_report_pdf(report) -> bytes:
    import io
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.lib import colors
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                    Table, TableStyle, HRFlowable)
    from reportlab.lib.enums import TA_LEFT, TA_CENTER

    buf    = io.BytesIO()
    doc    = SimpleDocTemplate(buf, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm,
                               topMargin=2*cm, bottomMargin=2*cm)
    styles = getSampleStyleSheet()
    VIOLET = colors.HexColor('#7c3aed')
    SLATE  = colors.HexColor('#94a3b8')

    h1_s  = ParagraphStyle('H1', parent=styles['Heading1'], textColor=VIOLET, fontSize=22, spaceAfter=8)
    h2_s  = ParagraphStyle('H2', parent=styles['Heading2'], textColor=VIOLET, fontSize=16, spaceBefore=14, spaceAfter=6)
    body_s= ParagraphStyle('Body', parent=styles['Normal'], textColor=colors.HexColor('#1e293b'), fontSize=10, spaceAfter=5, leading=14)
    sub_s = ParagraphStyle('Sub',  parent=styles['Normal'], textColor=SLATE, fontSize=9, spaceAfter=10)

    story = [
        Paragraph(report.title, h1_s),
        Paragraph(report.description or '', sub_s),
        HRFlowable(color=VIOLET, thickness=1, spaceAfter=12),
    ]

    for sec in report.section_rows.all():
        s = _resolve_section(sec)
        if sec.section_type == 'heading':
            lvl  = sec.content.get('level', 1)
            size = {1: 18, 2: 14, 3: 12}.get(lvl, 12)
            style = ParagraphStyle(f'h{lvl}', parent=styles['Heading1'],
                                   textColor=VIOLET, fontSize=size, spaceBefore=10, spaceAfter=5)
            story.append(Paragraph(sec.content.get('text', ''), style))
        elif sec.section_type == 'text':
            story.append(Paragraph(sec.content.get('text', ''), body_s))
        elif sec.section_type == 'divider':
            story.append(HRFlowable(color=SLATE, thickness=0.5, spaceBefore=8, spaceAfter=8))
        elif sec.section_type == 'stats' and s.get('analysis'):
            story.append(Paragraph('Statistics', h2_s))
            cols_data = s['analysis'].get('columns', [])[:10]
            tdata = [['Column', 'Type', 'Nulls%', 'Unique', 'Min', 'Max', 'Mean']]
            for col in cols_data:
                tdata.append([
                    col['name'][:22], 'num' if col.get('is_numeric') else 'text',
                    f"{col.get('null_pct',0):.1f}%", str(col.get('unique_count','')),
                    str(col.get('min',''))[:10], str(col.get('max',''))[:10],
                    f"{col.get('mean',0):.2f}" if col.get('is_numeric') and col.get('mean') else '',
                ])
            tbl = Table(tdata, colWidths=[3.8*cm,1.4*cm,1.6*cm,1.6*cm,2.2*cm,2.2*cm,2.2*cm])
            tbl.setStyle(TableStyle([
                ('BACKGROUND',(0,0),(-1,0), VIOLET),
                ('TEXTCOLOR', (0,0),(-1,0), colors.white),
                ('FONTNAME',  (0,0),(-1,-1), 'Helvetica'),
                ('FONTSIZE',  (0,0),(-1,-1), 8),
                ('ROWBACKGROUNDS',(0,1),(-1,-1),[colors.HexColor('#f8fafc'), colors.white]),
                ('GRID',(0,0),(-1,-1),0.25, colors.HexColor('#e2e8f0')),
                ('TOPPADDING',(0,0),(-1,-1),4),('BOTTOMPADDING',(0,0),(-1,-1),4),
            ]))
            story.append(tbl)
            story.append(Spacer(1, 8))
        elif sec.section_type == 'ai_insights' and s.get('upload'):
            ins = s['upload'].ai_insights
            if ins:
                story.append(Paragraph('AI Insights', h2_s))
                for line in ins.split('\n'):
                    line = line.strip().lstrip('#*').strip()
                    if line:
                        story.append(Paragraph(line, body_s))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


@login_required
@require_POST
def schedule_report(request, pk):
    from django.utils import timezone
    from datetime import timedelta
    report = get_object_or_404(Report, pk=pk, user=request.user)
    cleaned, error = validate_schedule_payload(request.POST, fallback_email=request.user.email)
    if error:
        return JsonResponse(error, status=error.get('status', 400))
    freq = cleaned['frequency']
    email = cleaned['email']
    next_send = timezone.now() + timedelta(days={'daily':1,'weekly':7,'monthly':30}.get(freq,7))
    sched, created = ScheduledReport.objects.update_or_create(
        report=report, user=request.user,
        defaults={'frequency':freq,'email':email,'is_active':True,'next_send_at':next_send}
    )
    return JsonResponse({'ok': True, 'id': sched.id, 'frequency': freq, 'email': email, 'next_send_at': timezone.localtime(next_send).strftime('%Y-%m-%d %H:%M')})


@login_required
@require_POST
def unschedule_report(request, pk):
    from .models import ScheduledReport
    report = get_object_or_404(Report, pk=pk, user=request.user)
    ScheduledReport.objects.filter(report=report, user=request.user).update(is_active=False)
    return JsonResponse({'ok': True})
