"""
Nexyza backup command.

Usage:
    python manage.py backup                    # Full backup (DB + media)
    python manage.py backup --db-only          # Database only
    python manage.py backup --media-only       # Media/uploads only
    python manage.py backup --dest /path/      # Custom destination
    python manage.py backup --keep 14          # Keep last 14 backups (default 7)
    python manage.py backup --notify           # Email hello@nexyza.com on success/failure

Supports:
    - PostgreSQL: pg_dump → compressed .sql.gz
    - SQLite: file copy → .db.gz
    - Media: tar.gz archive of uploaded files
    - Optional S3/R2 upload after local backup
    - Email notification on completion or failure
"""
import gzip
import os
import shutil
import subprocess
import tarfile
import tempfile
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone


class Command(BaseCommand):
    help = 'Backup database and media files'

    def add_arguments(self, parser):
        parser.add_argument('--db-only',    action='store_true', help='Database backup only')
        parser.add_argument('--media-only', action='store_true', help='Media backup only')
        parser.add_argument('--dest',       type=str, default='', help='Backup destination directory')
        parser.add_argument('--keep',       type=int, default=7,  help='Number of backups to keep (default 7)')
        parser.add_argument('--notify',     action='store_true',  help='Email hello@nexyza.com on completion')
        parser.add_argument('--s3',         action='store_true',  help='Upload to S3/R2 after local backup')

    def handle(self, *args, **options):
        ts       = datetime.now().strftime('%Y%m%d_%H%M%S')
        dest_dir = Path(options['dest']) if options['dest'] else Path(settings.BASE_DIR) / 'backups'
        dest_dir.mkdir(parents=True, exist_ok=True)

        db_only    = options['db_only']
        media_only = options['media_only']
        keep       = options['keep']
        notify     = options['notify']
        upload_s3  = options['s3']

        backed_up = []
        errors    = []

        # ── Database backup ───────────────────────────────────────────────────
        if not media_only:
            try:
                db_file = self._backup_database(dest_dir, ts)
                backed_up.append(('database', db_file))
                self.stdout.write(self.style.SUCCESS(f'✅ DB backup: {db_file.name}  ({self._size(db_file)})'))
            except Exception as e:
                errors.append(f'Database backup failed: {e}')
                self.stdout.write(self.style.ERROR(f'❌ DB backup failed: {e}'))

        # ── Media backup ──────────────────────────────────────────────────────
        if not db_only:
            media_root = Path(settings.MEDIA_ROOT)
            if media_root.exists() and any(media_root.iterdir()):
                try:
                    media_file = self._backup_media(dest_dir, ts)
                    backed_up.append(('media', media_file))
                    self.stdout.write(self.style.SUCCESS(f'✅ Media backup: {media_file.name}  ({self._size(media_file)})'))
                except Exception as e:
                    errors.append(f'Media backup failed: {e}')
                    self.stdout.write(self.style.ERROR(f'❌ Media backup failed: {e}'))
            else:
                self.stdout.write('   Media dir empty — skipped')

        # ── S3/R2 upload ──────────────────────────────────────────────────────
        if upload_s3 and backed_up:
            for kind, filepath in backed_up:
                try:
                    self._upload_to_s3(filepath)
                    self.stdout.write(self.style.SUCCESS(f'☁  Uploaded {kind} to S3'))
                except Exception as e:
                    errors.append(f'S3 upload failed ({kind}): {e}')
                    self.stdout.write(self.style.ERROR(f'❌ S3 upload failed: {e}'))

        # ── Prune old backups ─────────────────────────────────────────────────
        self._prune_old(dest_dir, keep)

        # ── Email notification ────────────────────────────────────────────────
        if notify:
            self._send_notification(backed_up, errors, ts)

        if errors and not backed_up:
            raise Exception(f'Backup completely failed: {"; ".join(errors)}')

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _backup_database(self, dest_dir: Path, ts: str) -> Path:
        db_conf = settings.DATABASES['default']
        engine  = db_conf['ENGINE']

        if 'postgresql' in engine:
            out_path = dest_dir / f'db_{ts}.sql.gz'
            env = os.environ.copy()
            env['PGPASSWORD'] = db_conf.get('PASSWORD', '')
            cmd = [
                'pg_dump',
                '--no-password',
                '-h', db_conf.get('HOST', 'localhost'),
                '-p', str(db_conf.get('PORT', 5432)),
                '-U', db_conf.get('USER', 'postgres'),
                '-d', db_conf.get('NAME', 'nexyza'),
                '--format=custom',       # compressed + parallel-restore capable
                '--no-acl',
                '--no-owner',
            ]
            with gzip.open(out_path, 'wb') as gz_out:
                proc = subprocess.run(cmd, env=env, capture_output=True)
                if proc.returncode != 0:
                    raise RuntimeError(proc.stderr.decode()[:500])
                gz_out.write(proc.stdout)
            return out_path

        elif 'sqlite3' in engine:
            db_path  = Path(db_conf['NAME'])
            out_path = dest_dir / f'db_{ts}.sqlite3.gz'
            with open(db_path, 'rb') as f_in:
                with gzip.open(out_path, 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)
            return out_path

        else:
            raise NotImplementedError(f'Backup not supported for engine: {engine}')

    def _backup_media(self, dest_dir: Path, ts: str) -> Path:
        out_path   = dest_dir / f'media_{ts}.tar.gz'
        media_root = Path(settings.MEDIA_ROOT)
        with tarfile.open(out_path, 'w:gz') as tar:
            tar.add(media_root, arcname='media')
        return out_path

    def _prune_old(self, dest_dir: Path, keep: int):
        """Delete old backups, keeping only the most recent `keep` of each type."""
        for prefix in ('db_', 'media_'):
            files = sorted(dest_dir.glob(f'{prefix}*'), key=lambda p: p.stat().st_mtime, reverse=True)
            for old in files[keep:]:
                old.unlink()
                self.stdout.write(f'   🗑  Removed old backup: {old.name}')

    def _upload_to_s3(self, filepath: Path):
        """Upload backup file to S3/R2 bucket."""
        import boto3
        from django.conf import settings as s
        bucket = getattr(s, 'BACKUP_S3_BUCKET', '')
        prefix = getattr(s, 'BACKUP_S3_PREFIX', 'backups/')
        if not bucket:
            raise ValueError('BACKUP_S3_BUCKET not configured')
        s3 = boto3.client(
            's3',
            endpoint_url=getattr(s, 'BACKUP_S3_ENDPOINT', None),
            aws_access_key_id=getattr(s, 'BACKUP_S3_KEY', None),
            aws_secret_access_key=getattr(s, 'BACKUP_S3_SECRET', None),
        )
        s3.upload_file(str(filepath), bucket, f'{prefix}{filepath.name}')

    def _send_notification(self, backed_up, errors, ts):
        from django.core.mail import send_mail
        from django.conf import settings as s

        status  = '✅ SUCCESS' if backed_up and not errors else ('⚠️ PARTIAL' if backed_up else '❌ FAILED')
        summary = '\n'.join(f'  • {kind}: {f.name} ({self._size(f)})' for kind, f in backed_up)
        errs    = '\n'.join(f'  • {e}' for e in errors)
        body    = (
            f'Nexyza backup report — {ts}\n'
            f'Status: {status}\n\n'
            f'Files backed up:\n{summary or "  (none)"}\n\n'
            f'Errors:\n{errs or "  (none)"}\n'
        )
        send_mail(
            subject   =f'[Nexyza Backup] {status} — {ts}',
            message   = body,
            from_email= s.DEFAULT_FROM_EMAIL,
            recipient_list=['hello@nexyza.com'],
            fail_silently=True,
        )

    @staticmethod
    def _size(path: Path) -> str:
        b = path.stat().st_size
        if b >= 1024 ** 3: return f'{b / 1024**3:.1f} GB'
        if b >= 1024 ** 2: return f'{b / 1024**2:.1f} MB'
        if b >= 1024:      return f'{b / 1024:.1f} KB'
        return f'{b} B'
