from pathlib import Path
from decouple import config, Csv

BASE_DIR = Path(__file__).resolve().parent.parent.parent

SECRET_KEY = config('SECRET_KEY', default='django-insecure-change-me-in-production')
DEBUG = config('DEBUG', default=True, cast=bool)
ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='*', cast=Csv())

INSTALLED_APPS = [
    'daphne',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'django_htmx',
    'apps.core',
    'apps.blog',
    'apps.accounts',
    'apps.billing',
    'apps.analyser',
    'apps.connectors',
    'apps.dashboard',
    'apps.reports',
    'apps.api',
    'apps.teams',
    'apps.nlq',
    'apps.pipeline',
    'apps.embed',
    'apps.whitelabel',
    'apps.search',
    'apps.widgets',
    'apps.forecasting',
    'apps.reportbuilder',
    'apps.webhooks',
    'apps.roles',
    'apps.catalog',
    'apps.collaboration',
    'channels',
    'apps.audit',
    'apps.joins',
    'apps.formulas',
    'apps.anomaly',
    'apps.versioning',
    'apps.exports',
    'apps.notifications',
    'apps.cleaner',
    'django_q',
    'corsheaders',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django_htmx.middleware.HtmxMiddleware',
    'apps.billing.middleware.SubscriptionMiddleware',
    'apps.whitelabel.middleware.WhiteLabelMiddleware',
    'apps.audit.middleware.AuditMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'apps.billing.context_processors.subscription_context',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Asia/Colombo'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

AUTH_USER_MODEL = 'accounts.User'
AUTHENTICATION_BACKENDS = [
    'django.contrib.auth.backends.ModelBackend',
    'allauth.account.auth_backends.AuthenticationBackend',
]
SITE_ID = 1
ACCOUNT_EMAIL_REQUIRED = True
ACCOUNT_USERNAME_REQUIRED = False
ACCOUNT_AUTHENTICATION_METHOD = 'email'
ACCOUNT_EMAIL_VERIFICATION = 'optional'
ACCOUNT_SIGNUP_PASSWORD_ENTER_TWICE = True
LOGIN_REDIRECT_URL = '/dashboard/'
LOGOUT_REDIRECT_URL = '/'

LEMONSQUEEZY_API_KEY = config('LEMONSQUEEZY_API_KEY', default='')
LEMONSQUEEZY_STORE_ID = config('LEMONSQUEEZY_STORE_ID', default='')
LEMONSQUEEZY_WEBHOOK_SECRET = config('LEMONSQUEEZY_WEBHOOK_SECRET', default='')
LEMONSQUEEZY_PLUS_MONTHLY_VARIANT_ID = config('LEMONSQUEEZY_PLUS_MONTHLY_VARIANT_ID', default='')
LEMONSQUEEZY_PLUS_YEARLY_VARIANT_ID  = config('LEMONSQUEEZY_PLUS_YEARLY_VARIANT_ID',  default='')
LEMONSQUEEZY_PRO_MONTHLY_VARIANT_ID  = config('LEMONSQUEEZY_PRO_MONTHLY_VARIANT_ID',  default='')
LEMONSQUEEZY_PRO_YEARLY_VARIANT_ID   = config('LEMONSQUEEZY_PRO_YEARLY_VARIANT_ID',   default='')
# Legacy aliases
LEMONSQUEEZY_MONTHLY_VARIANT_ID = LEMONSQUEEZY_PRO_MONTHLY_VARIANT_ID

# Set BILLING_ENABLED=True in .env once your LemonSqueezy store is approved.
# When False, pricing page shows "Coming Soon" and checkout is disabled.
BILLING_ENABLED = config('BILLING_ENABLED', default=False, cast=bool)
LEMONSQUEEZY_YEARLY_VARIANT_ID  = LEMONSQUEEZY_PRO_YEARLY_VARIANT_ID

ANTHROPIC_API_KEY = config('ANTHROPIC_API_KEY', default='')

FREE_UPLOAD_LIMIT = 5
FREE_FILE_SIZE_LIMIT = 1 * 1024 * 1024
PRO_FILE_SIZE_LIMIT = 10 * 1024 * 1024
ALLOWED_FILE_EXTENSIONS = ['.csv', '.xlsx', '.xls', '.json']

# Django-Q task queue
# ── Django-Q2 Scheduled Tasks ────────────────────────────────────────────────
Q_SCHEDULES = [
    {
        'func':    'apps.pipeline.tasks.check_due_pipelines',
        'minutes': 60,
        'name':    'pipeline-scheduler',
    },
    {
        'func':    'apps.connectors.tasks.sync_due_connectors',
        'minutes': 5,
        'name':    'sync-live-connectors',
    },
    {
        'func':    'apps.reportbuilder.tasks.send_scheduled_reports',
        'minutes': 15,
        'name':    'send-scheduled-reports',
    },
    {
        'func':    'apps.connectors.tasks.notify_low_token_budget',
        'minutes': 1440,   # daily
        'name':    'token-budget-warning',
    },
]

Q_CLUSTER = {
    'name': 'datalens',
    'workers': 2,
    'timeout': 120,
    'retry': 240,
    'queue_limit': 50,
    'bulk': 10,
    'orm': 'default',
}

# Email (override in prod.py)

# CORS
CORS_ALLOWED_ORIGINS = config('CORS_ALLOWED_ORIGINS', default='http://localhost:3000', cast=Csv())

# Share tokens expire after N days
SHARE_LINK_EXPIRY_DAYS = 30

# API
API_KEY_PREFIX = 'dl_'
API_RATE_LIMIT_PER_MIN = 60

# PWA
PWA_APP_NAME = 'Nexyza'
PWA_APP_DESCRIPTION = 'CSV, Excel & JSON Analyser'
PWA_APP_THEME_COLOR = '#7c3aed'
PWA_APP_BACKGROUND_COLOR = '#0d0b17'
PWA_APP_DISPLAY = 'standalone'
PWA_APP_ORIENTATION = 'any'
PWA_APP_START_URL = '/dashboard/'
PWA_APP_ICONS = [{'src': '/static/img/icon-192.png', 'sizes': '192x192'},
                 {'src': '/static/img/icon-512.png', 'sizes': '512x512'}]

# Pipeline
PIPELINE_MAX_SOURCES = 10
PIPELINE_CRON_ENABLED = True

# Embed
EMBED_ALLOWED_DOMAINS = []   # empty = all domains allowed
EMBED_CACHE_SECONDS = 300

# v5 settings
ANOMALY_Z_SCORE_THRESHOLD = 3.0   # flag values > N std devs from mean
VERSIONING_MAX_SNAPSHOTS  = 50    # max snapshots per upload
MARKETPLACE_PAGE_SIZE     = 20
EXPORT_PDF_ENABLED        = True
NOTIFICATION_CHECK_HOURS  = 1     # how often to check thresholds

# Safer rendering for local/dev environments behind aggressive web filters
ANALYSER_SAFE_MODE        = config('ANALYSER_SAFE_MODE', default=True, cast=bool)

# Custom error handlers
HANDLER_404 = 'config.views.handler_404'
HANDLER_500 = 'config.views.handler_500'

# Django Channels (WebSockets for real-time collaboration)
ASGI_APPLICATION = 'config.asgi.application'
# Auto-selects Redis channel layer if REDIS_URL is set, otherwise InMemory (dev only)
_REDIS_URL = config('REDIS_URL', default='')
if _REDIS_URL:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels_redis.core.RedisChannelLayer',
            'CONFIG':  {'hosts': [_REDIS_URL]},
        }
    }
else:
    CHANNEL_LAYERS = {
        'default': {
            'BACKEND': 'channels.layers.InMemoryChannelLayer',
        }
    }
# Search
SEARCH_MIN_QUERY_LEN = 2
# Webhooks
WEBHOOK_TIMEOUT_SECONDS = 10
WEBHOOK_MAX_RETRIES = 3
# Forecasting
FORECAST_MAX_PERIODS = 52
FORECAST_MIN_DATAPOINTS = 5

# ── Anthropic Agent Skills ────────────────────────────────────────────────────
# Set to True to use Agent Skills for AI chart generation (requires API key)
# Set to False to use system prompt approach (works with any API key)
USE_ANTHROPIC_SKILLS = config('USE_ANTHROPIC_SKILLS', default=False, cast=bool)

# Skill IDs (auto-populated by skills_manager.upload_all_skills())
# You can also set these manually after uploading via the CLI
DATALENS_SKILL_CHART_ANALYSIS = config('DATALENS_SKILL_CHART_ANALYSIS', default='')
DATALENS_SKILL_INSIGHTS        = config('DATALENS_SKILL_INSIGHTS', default='')

# ── Google OAuth & Sheets ─────────────────────────────────────────────────────
GOOGLE_OAUTH_CLIENT_ID     = config('GOOGLE_OAUTH_CLIENT_ID',     default='')
GOOGLE_OAUTH_CLIENT_SECRET = config('GOOGLE_OAUTH_CLIENT_SECRET', default='')
GOOGLE_SHEETS_SCOPE = 'https://www.googleapis.com/auth/spreadsheets.readonly'

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'SCOPE': ['profile', 'email', 'https://www.googleapis.com/auth/spreadsheets.readonly'],
        'AUTH_PARAMS': {'access_type': 'offline', 'prompt': 'consent'},
        'APP': {
            'client_id':     GOOGLE_OAUTH_CLIENT_ID,
            'secret':        GOOGLE_OAUTH_CLIENT_SECRET,
            'key':           '',
        },
    }
}

# Microsoft Graph (Excel Online)
MICROSOFT_OAUTH_CLIENT_ID     = config('MICROSOFT_OAUTH_CLIENT_ID',     default='')
MICROSOFT_OAUTH_CLIENT_SECRET = config('MICROSOFT_OAUTH_CLIENT_SECRET', default='')

# ── Email — Hostinger SMTP ────────────────────────────────────────────────────
EMAIL_BACKEND   = config('EMAIL_BACKEND', default='django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST      = config('EMAIL_HOST',     default='smtp.hostinger.com')
EMAIL_PORT      = config('EMAIL_PORT',     default=465, cast=int)
EMAIL_USE_SSL   = config('EMAIL_USE_SSL',  default=True,  cast=bool)
EMAIL_USE_TLS   = config('EMAIL_USE_TLS',  default=False, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER',     default='hello@nexyza.com')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL  = config('DEFAULT_FROM_EMAIL',  default='Nexyza <hello@nexyza.com>')
SERVER_EMAIL        = config('SERVER_EMAIL',         default='hello@nexyza.com')

# ── Logging ───────────────────────────────────────────────────────────────────
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {module}: {message}',
            'style': '{',
        },
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'filters': ['require_debug_true'],
            'class': 'logging.StreamHandler',
            'formatter': 'simple',
        },
        'console_prod': {
            'level': 'WARNING',
            'filters': ['require_debug_false'],
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'mail_admins': {
            'level': 'ERROR',
            'filters': ['require_debug_false'],
            'class': 'django.utils.log.AdminEmailHandler',
            'include_html': True,
        },
        'file': {
            'level': 'WARNING',
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'nexyza.log',
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'console_prod'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'console_prod', 'mail_admins'],
            'level': 'INFO',
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console_prod', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django.security': {
            'handlers': ['console_prod', 'mail_admins'],
            'level': 'ERROR',
            'propagate': False,
        },
        # App-specific loggers
        'apps': {
            'handlers': ['console', 'console_prod'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'apps.analyser': {
            'handlers': ['console', 'console_prod'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps.billing': {
            'handlers': ['console', 'console_prod', 'mail_admins'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
