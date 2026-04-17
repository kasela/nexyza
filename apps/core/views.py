from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render
from django.http import JsonResponse, HttpResponse
from django.conf import settings


FEATURES = [
    {'icon': '🤖', 'title': 'AI-Powered Insights',      'desc': 'Claude reads your dataset and surfaces patterns, anomalies, quality issues, and actionable recommendations automatically.'},
    {'icon': '📊', 'title': 'Auto-Generated Charts',     'desc': 'Intelligent chart selection: histograms, trends, distributions, correlations — all chosen and built for your specific data.'},
    {'icon': '💬', 'title': 'Natural Language Queries',  'desc': 'Ask plain-English questions like "what is the average revenue by region?" and get instant answers with visualisations.'},
    {'icon': '🔍', 'title': 'Anomaly Detection',         'desc': 'Automatically flags outliers, missing value spikes, suspicious distributions, and data quality problems with AI narrative.'},
    {'icon': '🧹', 'title': 'Data Cleaning Tools',       'desc': 'Drop nulls, fill values, find & replace, rename columns, filter rows — a full data prep workflow inside your browser.'},
    {'icon': '🔗', 'title': 'Multi-File Joins',          'desc': 'Merge two datasets on any shared key column with inner, left, right, or outer join — result is instantly re-analysed.'},
    {'icon': '📤', 'title': 'Advanced Export',           'desc': 'Export styled Excel workbooks (4 sheets), professional PDF reports, and raw JSON analysis results.'},
    {'icon': '🔑', 'title': 'REST API',                  'desc': 'Programmatic access via API keys. Upload, analyse, and retrieve results from your own apps and workflows.'},
    {'icon': '👥', 'title': 'Team Workspaces',           'desc': 'Invite team members, assign roles (Admin/Editor/Viewer), and share analyses into team workspaces.'},
]

STEPS = [
    {'icon': '📁', 'title': 'Upload your file',   'desc': 'Drag & drop any CSV, Excel (.xlsx), or JSON file up to 10 MB. We support single and multi-sheet workbooks.'},
    {'icon': '⚡', 'title': 'AI analyses instantly', 'desc': 'Claude examines your data, selects the best charts, detects anomalies, and writes insights — all in seconds.'},
    {'icon': '🚀', 'title': 'Explore & share',    'desc': 'Drill into columns, ask questions in plain English, export to Excel/PDF, or share a public link.'},
]

FILE_TYPES = [
    ('.CSV',  'Comma-separated',    {'bg': 'rgba(16,185,129,.1)',  'border': 'rgba(16,185,129,.25)',  'text': '#34d399'}),
    ('.XLSX', 'Excel spreadsheet',  {'bg': 'rgba(59,130,246,.1)',  'border': 'rgba(59,130,246,.25)',  'text': '#60a5fa'}),
    ('.XLS',  'Legacy Excel',       {'bg': 'rgba(59,130,246,.08)', 'border': 'rgba(59,130,246,.15)',  'text': '#60a5fa'}),
    ('.JSON', 'Structured data',    {'bg': 'rgba(245,158,11,.1)',  'border': 'rgba(245,158,11,.25)',  'text': '#fbbf24'}),
]

STATS = [
    {'value': '10+',  'label': 'Chart types auto-generated'},
    {'value': '6',    'label': 'Export formats'},
    {'value': '100%', 'label': 'Browser-based, no install'},
    {'value': '∞',    'label': 'Analyses on Pro plan'},
]

TESTIMONIALS = [
    {'quote': "I uploaded a 50,000 row sales dataset and had charts, anomaly flags, and a full written summary in under 30 seconds. This is what Excel should have been.",
     'name': 'Sarah K.', 'role': 'Head of Sales Operations'},
    {'quote': "The natural language queries are genuinely useful. I asked 'which product category has the highest return rate?' and got a chart with the answer immediately.",
     'name': 'Marcus T.', 'role': 'E-commerce Analyst'},
    {'quote': "We use the API to run analysis on every pipeline run. The data versioning feature lets us catch drift immediately. Excellent for automated QA.",
     'name': 'Priya M.', 'role': 'Data Engineering Lead'},
]


def home(request):
    return render(request, 'core/home.html', {
        'features':     FEATURES,
        'steps':        STEPS,
        'file_types':   FILE_TYPES,
        'stats':        STATS,
        'testimonials': TESTIMONIALS,
    })


def pwa_manifest(request):
    branding = getattr(request, 'branding', None)
    app_name = (branding.app_name if branding else None) or 'Nexyza'
    manifest = {
        "name": app_name, "short_name": app_name,
        "description": settings.PWA_APP_DESCRIPTION,
        "start_url": settings.PWA_APP_START_URL,
        "display": settings.PWA_APP_DISPLAY,
        "orientation": settings.PWA_APP_ORIENTATION,
        "theme_color": settings.PWA_APP_THEME_COLOR,
        "background_color": settings.PWA_APP_BACKGROUND_COLOR,
        "icons": settings.PWA_APP_ICONS,
        "categories": ["productivity", "utilities"],
        "shortcuts": [
            {"name": "New Analysis", "url": "/workspace/", "description": "Upload and analyse a file"},
            {"name": "Dashboard",    "url": "/dashboard/", "description": "View your analyses"},
        ],
    }
    return JsonResponse(manifest, content_type='application/manifest+json')


def service_worker(request):
    sw = r"""
const CACHE="datalens-v1";
const OFFLINE=["/","/dashboard/","/workspace/"];
self.addEventListener("install",e=>{e.waitUntil(caches.open(CACHE).then(c=>c.addAll(OFFLINE)));});
self.addEventListener("fetch",e=>{if(e.request.method!=="GET")return;e.respondWith(fetch(e.request).then(r=>{const cl=r.clone();caches.open(CACHE).then(c=>c.put(e.request,cl));return r;}).catch(()=>caches.match(e.request).then(r=>r||new Response("Offline",{status:503}))));});
self.addEventListener("activate",e=>{e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(n=>n!==CACHE).map(n=>caches.delete(n)))));});
"""
    return HttpResponse(sw, content_type='application/javascript')


def privacy(request):
    return render(request, 'core/privacy.html')


def terms(request):
    return render(request, 'core/terms.html')


def contact(request):
    sent       = False
    sent_email = ''
    error      = ''
    form_data  = {}

    if request.method == 'POST':
        name    = request.POST.get('name', '').strip()
        email   = request.POST.get('email', '').strip()
        subject = request.POST.get('subject', 'general')
        message = request.POST.get('message', '').strip()

        form_data = {'name': name, 'email': email, 'message': message}

        if not name or not email or not message:
            error = 'Please fill in all required fields.'
        else:
            try:
                from django.core.mail import send_mail
                from django.conf import settings

                subject_labels = {
                    'general':     'General question',
                    'support':     'Technical support',
                    'billing':     'Billing & plans',
                    'feature':     'Feature request',
                    'partnership': 'Partnership / Enterprise',
                    'bug':         'Bug report',
                    'other':       'Other',
                }
                subject_label = subject_labels.get(subject, subject)

                # Email to Nexyza inbox
                send_mail(
                    subject   = f"[Nexyza Contact] {subject_label} — from {name}",
                    message   = f"From: {name} <{email}>\nSubject: {subject_label}\n\n{message}",
                    from_email= settings.DEFAULT_FROM_EMAIL,
                    recipient_list=['hello@nexyza.com'],
                    fail_silently=False,
                )

                # Auto-reply to sender
                send_mail(
                    subject   = "We received your message — Nexyza",
                    message   = (
                        f"Hi {name},\n\n"
                        f"Thanks for reaching out! We\'ve received your message and will get back "
                        f"to you within 24 hours.\n\n"
                        f"Your message:\n{message}\n\n"
                        f"Best,\nThe Nexyza Team\nhello@nexyza.com"
                    ),
                    from_email= settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[email],
                    fail_silently=True,
                )

                sent       = True
                sent_email = email

            except Exception as e:
                import logging
                logging.getLogger(__name__).error(f"Contact form email failed: {e}")
                error = "Message could not be sent. Please email us directly at hello@nexyza.com"

    from django.shortcuts import render
    return render(request, 'core/contact.html', {
        'sent': sent, 'sent_email': sent_email,
        'error': error, 'form_data': form_data,
    })


def robots_txt(request):
    """robots.txt — tell crawlers what to index."""
    from django.http import HttpResponse
    content = """User-agent: *
Allow: /
Allow: /pricing/
Allow: /blog/
Allow: /privacy/
Allow: /terms/
Allow: /contact/
Disallow: /dashboard/
Disallow: /workspace/
Disallow: /accounts/
Disallow: /admin/
Disallow: /admin-panel/
Disallow: /api/
Disallow: /webhooks/
Disallow: /billing/portal/
Disallow: /billing/checkout/
Disallow: /embed/
Disallow: /shared/

Sitemap: https://nexyza.com/sitemap.xml
"""
    return HttpResponse(content, content_type='text/plain')


def sitemap_xml(request):
    """Dynamic XML sitemap."""
    from django.http import HttpResponse
    from django.utils.timezone import now

    today = now().strftime('%Y-%m-%d')
    base  = 'https://nexyza.com'

    static_pages = [
        ('/',           '1.0',  'weekly',  today),
        ('/pricing/',   '0.9',  'monthly', today),
        ('/privacy/',   '0.5',  'yearly',  today),
        ('/terms/',     '0.5',  'yearly',  today),
        ('/contact/',   '0.6',  'monthly', today),
        ('/blog/',      '0.8',  'weekly',  today),
    ]

    # Add blog posts
    try:
        from apps.blog.models import BlogPost
        posts = BlogPost.objects.filter(is_published=True).values('slug', 'updated_at')
        blog_urls = [(f'/blog/{p["slug"]}/', '0.7', 'monthly',
                      p['updated_at'].strftime('%Y-%m-%d') if p['updated_at'] else today)
                     for p in posts]
    except Exception:
        blog_urls = []

    all_pages = static_pages + blog_urls

    lines = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for path, priority, freq, lastmod in all_pages:
        lines += [
            '  <url>',
            f'    <loc>{base}{path}</loc>',
            f'    <lastmod>{lastmod}</lastmod>',
            f'    <changefreq>{freq}</changefreq>',
            f'    <priority>{priority}</priority>',
            '  </url>',
        ]
    lines.append('</urlset>')
    return HttpResponse('\n'.join(lines), content_type='application/xml')


# ── Social post generator ──────────────────────────────────────────────────────

@staff_member_required
def social_posts(request):
    """Generate social media posts for blog articles and product updates."""
    from apps.blog.models import BlogPost
    posts  = BlogPost.objects.filter(is_published=True).order_by('-published_at')[:20]
    return render(request, 'core/social_posts.html', {'posts': posts})
