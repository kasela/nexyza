"""
Management command to upload Nexyza Agent Skills to Anthropic.

Usage:
    python manage.py upload_skills                  # upload all
    python manage.py upload_skills --skill chart_analysis
    python manage.py upload_skills --force          # re-upload even if cached
    python manage.py upload_skills --list           # list uploaded skills
    python manage.py upload_skills --clear-cache    # clear cached IDs
"""
from django.core.management.base import BaseCommand
from django.conf import settings


class Command(BaseCommand):
    help = 'Upload Nexyza Agent Skills to Anthropic'

    def add_arguments(self, parser):
        parser.add_argument('--skill',       help='Specific skill key (chart_analysis or insights)')
        parser.add_argument('--force',       action='store_true', help='Re-upload even if cached')
        parser.add_argument('--list',        action='store_true', help='List uploaded skills')
        parser.add_argument('--clear-cache', action='store_true', dest='clear_cache',
                            help='Clear cached skill IDs')

    def handle(self, *args, **options):
        if not getattr(settings, 'ANTHROPIC_API_KEY', ''):
            self.stderr.write(self.style.ERROR('ANTHROPIC_API_KEY is not set'))
            return

        from apps.analyser.skills_manager import (
            upload_skill, upload_all_skills, list_skills,
            delete_cached_ids, SKILL_DIRS,
        )

        if options['clear_cache']:
            delete_cached_ids()
            self.stdout.write(self.style.SUCCESS('✓ Skill ID cache cleared'))
            return

        if options['list']:
            self.stdout.write('\nUploaded skills on your Anthropic account:\n')
            skills = list_skills()
            if not skills:
                self.stdout.write('  (none found)')
            for s in skills:
                self.stdout.write(f"  {s.get('id')} — {s.get('display_title','?')}")
            self.stdout.write('')
            return

        force = options.get('force', False)

        if options['skill']:
            key = options['skill']
            if key not in SKILL_DIRS:
                self.stderr.write(self.style.ERROR(
                    f"Unknown skill key '{key}'. Available: {', '.join(SKILL_DIRS.keys())}"
                ))
                return
            try:
                skill_id = upload_skill(key, force=force)
                self.stdout.write(self.style.SUCCESS(f'✓ {key}: {skill_id}'))
                self.stdout.write(f'\nAdd to your .env:\n  DATALENS_SKILL_{key.upper()} = {skill_id}')
            except Exception as e:
                self.stderr.write(self.style.ERROR(f'✗ {key}: {e}'))
        else:
            self.stdout.write('\nUploading all Nexyza skills...\n')
            results = upload_all_skills(force=force)
            env_lines = []
            for key, skill_id in results.items():
                if skill_id:
                    self.stdout.write(self.style.SUCCESS(f'  ✓ {key}: {skill_id}'))
                    env_lines.append(f'DATALENS_SKILL_{key.upper()} = {skill_id}')
                else:
                    self.stdout.write(self.style.ERROR(f'  ✗ {key}: failed'))

            if env_lines:
                self.stdout.write('\n' + self.style.WARNING(
                    'Add these to your .env file to activate Skills:\n'
                ) + '\n'.join(f'  {l}' for l in env_lines))
                self.stdout.write(self.style.WARNING(
                    '\n  USE_ANTHROPIC_SKILLS = True\n'
                ))
