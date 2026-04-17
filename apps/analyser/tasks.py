"""
Background tasks for heavy analysis operations.
Run with: python manage.py qcluster
"""
import logging
import os
import time

logger = logging.getLogger(__name__)


def analyse_upload_async(upload_id: int):
    """
    Analyse a FileUpload in the background.
    Used for large files (>5 MB) that would timeout a web request.
    """
    from apps.analyser.models import FileUpload
    from apps.analyser.engine import analyse
    from apps.analyser.views import _sanitise_result

    try:
        upload = FileUpload.objects.get(pk=upload_id)
        upload.status = 'processing'
        upload.save(update_fields=['status'])

        result = analyse(
            upload.file.path,
            upload.file_type,
            sheet_name=upload.active_sheet or None,
        )
        result = _sanitise_result(result)

        upload.analysis_result = result
        upload.row_count       = result['rows']
        upload.column_count    = result['cols']
        upload.status          = FileUpload.STATUS_DONE
        upload.save(update_fields=['analysis_result', 'row_count', 'column_count', 'status'])

        # Auto-generate rule-based charts
        from apps.analyser.charts import _rule_based
        _rule_based(upload)

        logger.info(f"Background analysis complete: upload {upload_id}")
        return {'ok': True, 'rows': result['rows'], 'cols': result['cols']}

    except FileUpload.DoesNotExist:
        logger.error(f"Upload {upload_id} not found")
        return {'ok': False, 'error': 'Upload not found'}
    except Exception as e:
        logger.exception(f"Background analysis failed for upload {upload_id}: {e}")
        try:
            upload = FileUpload.objects.get(pk=upload_id)
            upload.status = 'error'
            upload.save(update_fields=['status'])
        except Exception:
            pass
        return {'ok': False, 'error': str(e)}


def generate_ai_charts_async(upload_id: int):
    """Generate AI charts in background — avoids timeout on large datasets."""
    from apps.analyser.models import FileUpload
    from apps.analyser.ai_charts import ai_recommend_charts, apply_ai_recommendations

    try:
        upload = FileUpload.objects.get(pk=upload_id)
        configs = ai_recommend_charts(upload.analysis_result, upload.original_name)
        created = apply_ai_recommendations(upload, configs)
        logger.info(f"Background AI charts: {len(created)} charts for upload {upload_id}")
        return {'ok': True, 'charts': len(created)}
    except Exception as e:
        logger.error(f"Background AI charts failed for upload {upload_id}: {e}")
        return {'ok': False, 'error': str(e)}


def export_pdf_async(upload_id: int, user_id: int) -> str:
    """Generate PDF in background and store path."""
    from apps.analyser.models import FileUpload
    from apps.exports.views import _generate_pdf_bytes
    from django.conf import settings

    try:
        upload = FileUpload.objects.get(pk=upload_id)
        data   = _generate_pdf_bytes(upload)
        fname  = f"exports/pdf_{upload_id}_{user_id}.pdf"
        fpath  = os.path.join(settings.MEDIA_ROOT, fname)
        os.makedirs(os.path.dirname(fpath), exist_ok=True)
        with open(fpath, 'wb') as f:
            f.write(data)
        return fname
    except Exception as e:
        logger.error(f"Background PDF failed for upload {upload_id}: {e}")
        return ''
