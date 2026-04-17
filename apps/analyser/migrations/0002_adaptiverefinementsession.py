from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('analyser', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='AdaptiveRefinementSession',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('classification_json', models.JSONField(blank=True, default=dict)),
                ('question_schema', models.JSONField(blank=True, default=list)),
                ('answers_json', models.JSONField(blank=True, default=dict)),
                ('recommendations_json', models.JSONField(blank=True, default=dict)),
                ('current_step', models.PositiveIntegerField(default=0)),
                ('is_complete', models.BooleanField(default=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('profile', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='adaptive_sessions', to='analyser.uploadanalysisprofile')),
                ('upload', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='adaptive_refinement', to='analyser.fileupload')),
            ],
            options={'ordering': ['-updated_at']},
        ),
    ]
