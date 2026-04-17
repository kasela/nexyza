"""Multi-file join engine using Pandas."""
import pandas as pd
import tempfile, os
from apps.analyser.engine import load_dataframe, analyse


def execute_join(left_upload, right_upload, left_key: str, right_key: str, join_type: str) -> dict:
    """
    Merge two FileUploads on their respective key columns.
    Returns dict with 'df', 'rows', 'cols', 'path'.
    """
    df_l = load_dataframe(left_upload.file.path,  left_upload.file_type,
                          sheet_name=left_upload.active_sheet or None)
    df_r = load_dataframe(right_upload.file.path, right_upload.file_type,
                          sheet_name=right_upload.active_sheet or None)

    if left_key not in df_l.columns:
        raise ValueError(f"Column '{left_key}' not found in {left_upload.original_name}")
    if right_key not in df_r.columns:
        raise ValueError(f"Column '{right_key}' not found in {right_upload.original_name}")

    # Suffix duplicate columns
    merged = df_l.merge(
        df_r,
        left_on=left_key,
        right_on=right_key,
        how=join_type,
        suffixes=('_left', '_right'),
    )

    # Save as temp CSV
    tmp = tempfile.NamedTemporaryFile(suffix='.csv', delete=False,
                                      dir='/tmp', mode='w', encoding='utf-8')
    merged.to_csv(tmp.name, index=False)
    tmp.close()

    return {'df': merged, 'rows': len(merged), 'cols': len(merged.columns), 'tmp_path': tmp.name}


def save_join_result(join_cfg, tmp_path: str, name: str, user):
    """Persist the joined CSV as a new FileUpload and run analysis."""
    from apps.analyser.models import FileUpload
    from apps.analyser.charts import auto_generate_charts
    from django.core.files import File

    with open(tmp_path, 'rb') as f:
        upload = FileUpload.objects.create(
            user=user,
            original_name=f"{name}.csv",
            file_type='csv',
            status='processing',
        )
        upload.file.save(f"{name}.csv", File(f), save=True)

    try:
        result = analyse(upload.file.path, 'csv')
        upload.analysis_result = result
        upload.row_count = result['rows']
        upload.column_count = result['cols']
        upload.status = 'done'
        upload.file_size = os.path.getsize(upload.file.path)
        upload.save()
        auto_generate_charts(upload)
    except Exception as e:
        upload.status = 'error'
        upload.error_message = str(e)
        upload.save()
    finally:
        os.unlink(tmp_path)

    return upload
