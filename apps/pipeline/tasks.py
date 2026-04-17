"""Django-Q task: fetch URL source, re-analyse, update upload."""
import requests
import os, tempfile
from django.utils import timezone
from datetime import timedelta
from apps.analyser.models import FileUpload
from apps.analyser.engine import analyse
from apps.analyser.charts import auto_generate_charts
from .models import DataSource, PipelineRun


def _next_run(source):
    now = timezone.now()
    deltas = {'hourly': timedelta(hours=1), 'daily': timedelta(days=1),
              'weekly': timedelta(weeks=1), 'monthly': timedelta(days=30)}
    return now + deltas.get(source.frequency, timedelta(days=1))


def run_pipeline(source_id: int):
    try:
        source = DataSource.objects.select_related('user').get(id=source_id, is_active=True)
    except DataSource.DoesNotExist:
        return

    rows_before = source.last_upload.row_count if source.last_upload else 0

    try:
        if source.source_type == 'url':
            resp = requests.get(source.source_url, timeout=30)
            resp.raise_for_status()
            content = resp.content
            content_type = resp.headers.get('Content-Type', '')
            if 'json' in content_type:
                ext, file_type = '.json', 'json'
            elif 'excel' in content_type or 'spreadsheet' in content_type:
                ext, file_type = '.xlsx', 'excel'
            else:
                ext, file_type = '.csv', 'csv'

            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as f:
                f.write(content)
                tmp_path = f.name

            from django.core.files import File
            with open(tmp_path, 'rb') as f:
                upload = FileUpload.objects.create(
                    user=source.user,
                    file=File(f, name=f"{source.name}{ext}"),
                    original_name=f"{source.name}{ext}",
                    file_type=file_type,
                    file_size=len(content),
                    status='processing',
                )
            os.unlink(tmp_path)
        else:
            return  # re-upload type handled manually

        result = analyse(upload.file.path, file_type)
        upload.analysis_result = result
        upload.row_count = result['rows']
        upload.column_count = result['cols']
        upload.status = 'done'
        upload.save()
        auto_generate_charts(upload)

        PipelineRun.objects.create(
            source=source, status='ok', upload=upload,
            rows_before=rows_before, rows_after=upload.row_count,
        )
        source.last_upload = upload
        source.run_count += 1
        source.last_error = ''

    except Exception as e:
        PipelineRun.objects.create(source=source, status='error', error=str(e))
        source.last_error = str(e)

    source.last_run  = timezone.now()
    source.next_run  = _next_run(source)
    source.save(update_fields=['last_run', 'next_run', 'run_count', 'last_error', 'last_upload'])


def check_due_pipelines():
    """Called by Django-Q schedule hourly."""
    from django_q.tasks import async_task
    due = DataSource.objects.filter(is_active=True, next_run__lte=timezone.now())
    for s in due:
        async_task('apps.pipeline.tasks.run_pipeline', s.id)
