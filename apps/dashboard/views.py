from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone
from django.db.models import Count, Sum, Q
from datetime import timedelta
from apps.analyser.models import FileUpload, ChartConfig
from apps.accounts.models import OnboardingState
from django.conf import settings


@login_required
def index(request):
    user = request.user
    now  = timezone.now()
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    week_ago    = now - timedelta(days=7)

    uploads      = FileUpload.objects.filter(user=user)
    done_uploads = uploads.filter(status='done')
    recent       = uploads.order_by('-created_at')[:20]
    monthly_count = uploads.filter(created_at__gte=month_start).count()
    weekly_count  = uploads.filter(created_at__gte=week_ago).count()

    sub = getattr(request, 'subscription', None)
    is_pro = sub.is_active if sub else False
    upload_limit = settings.FREE_UPLOAD_LIMIT if not is_pro else None

    # File type breakdown
    type_counts = dict(
        uploads.values('file_type').annotate(n=Count('id')).values_list('file_type', 'n')
    )

    # Total rows analysed
    total_rows = done_uploads.aggregate(total=Sum('row_count'))['total'] or 0

    # Charts generated
    chart_count = ChartConfig.objects.filter(upload__user=user).count()

    # Pinned / recent done
    pinned  = done_uploads.filter(is_pinned=True)[:6]
    recent_done = done_uploads.order_by('-created_at')[:6]

    # Onboarding
    ob_state, _ = OnboardingState.objects.get_or_create(user=user)
    if not ob_state.welcomed:
        ob_state.welcomed = True
        ob_state.save(update_fields=['welcomed'])

    # Check if first upload done
    if not ob_state.first_upload and done_uploads.exists():
        ob_state.first_upload = True
        ob_state.save(update_fields=['first_upload'])

    onboarding_steps = [
        {
            'key': 'first_upload',
            'done': ob_state.first_upload,
            'title': 'Analyse your first file',
            'desc': 'Upload any CSV, Excel, or JSON file.',
            'url': '/workspace/',
            'icon': '📊',
        },
        {
            'key': 'viewed_charts',
            'done': ob_state.viewed_charts,
            'title': 'Explore auto-generated charts',
            'desc': 'AI picks the best charts for your data.',
            'url': '/workspace/',
            'icon': '📈',
        },
        {
            'key': 'asked_nlq',
            'done': ob_state.asked_nlq,
            'title': 'Ask a question in plain English',
            'desc': 'Use the "Ask AI" tab on any result page.',
            'url': '/workspace/',
            'icon': '💬',
        },
    ]

    show_onboarding = not ob_state.is_complete

    context = {
        'uploads': recent,
        'total_uploads': uploads.count(),
        'done_uploads':  done_uploads.count(),
        'monthly_count': monthly_count,
        'weekly_count':  weekly_count,
        'upload_limit':  upload_limit,
        'type_counts':   type_counts,
        'total_rows':    total_rows,
        'chart_count':   chart_count,
        'pinned':        pinned,
        'recent_done':   recent_done,
        'show_onboarding': show_onboarding,
        'onboarding_steps': onboarding_steps,
        'ob_progress':   ob_state.progress,
        'is_pro':        is_pro,
    }
    quick_actions = [
        {'icon': '📊', 'title': 'New Analysis',    'desc': 'Upload & analyse',          'url': '/workspace/'},
        {'icon': '🔗', 'title': 'Join Files',       'desc': 'Merge two datasets',         'url': '/join/'},
        {'icon': '🔌', 'title': 'Live Connectors',  'desc': 'Google Sheets auto-sync',   'url': '/connectors/'},
        {'icon': '📑', 'title': 'Reports',           'desc': 'Build & schedule reports',  'url': '/reports/builder/'},
        {'icon': '🧩', 'title': 'Widgets',           'desc': 'Pinned KPIs & charts',       'url': '/widgets/'},
        {'icon': '📚', 'title': 'Data Catalog',       'desc': 'Asset registry & lineage',  'url': '/catalog/'},
    ]
    context['quick_actions'] = quick_actions

    # AI token usage for this month
    try:
        from apps.billing.models import TokenUsage
        token_used   = TokenUsage.this_month(user)
        token_budget = getattr(getattr(user, 'subscription', None), 'ai_token_budget', 0) or 0
        token_pct    = round(token_used / token_budget * 100, 1) if token_budget else 0
        context['token_used']   = token_used
        context['token_budget'] = token_budget
        context['token_pct']    = token_pct
    except Exception:
        context['token_used'] = context['token_budget'] = context['token_pct'] = 0

    # Recent charts preview (last 6 non-KPI charts)
    recent_charts = list(
        ChartConfig.objects.filter(
            upload__user=user, upload__status='done'
        ).exclude(chart_type='kpi').select_related('upload')
        .order_by('-created_at')[:6]
    )
    context['recent_charts'] = recent_charts

    # Anomaly counts across all uploads
    try:
        from apps.anomaly.models import AnomalyReport
        anomaly_count = AnomalyReport.objects.filter(
            upload__user=user
        ).aggregate(total=__import__('django.db.models', fromlist=['Sum']).Sum(
            __import__('django.db.models', fromlist=['models']).models.Func('findings', function='jsonb_array_length')
        ))['total'] or 0
        context['anomaly_count'] = 0  # simplified — just show 0 if no scans
    except Exception:
        context['anomaly_count'] = 0

    return render(request, 'dashboard/index.html', context)
