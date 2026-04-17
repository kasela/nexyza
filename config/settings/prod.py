from .base import *

DEBUG = False

# ── Security ──────────────────────────────────────────────────────────────────
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
SECURE_REFERRER_POLICY = 'strict-origin-when-cross-origin'

# ALLOWED_HOSTS must be set via env var in production — never rely on '*'
# Example: ALLOWED_HOSTS=nexyza.com,www.nexyza.com
# Already inherited from base via config('ALLOWED_HOSTS', cast=Csv())
# Fail loudly if still set to wildcard in prod
_hosts = ALLOWED_HOSTS
if _hosts == ['*']:
    import warnings
    warnings.warn(
        "ALLOWED_HOSTS is set to '*' in production. "
        "Set ALLOWED_HOSTS env var to your actual domain(s).",
        RuntimeWarning,
        stacklevel=2,
    )

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
    }
}

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# ── Email — Hostinger SMTP ──────────────────────────────────────────────────
EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = config('EMAIL_HOST',          default='smtp.hostinger.com')
EMAIL_PORT          = config('EMAIL_PORT',          default=465, cast=int)
EMAIL_USE_SSL       = config('EMAIL_USE_SSL',       default=True,  cast=bool)
EMAIL_USE_TLS       = config('EMAIL_USE_TLS',       default=False, cast=bool)
EMAIL_HOST_USER     = config('EMAIL_HOST_USER',     default='hello@nexyza.com')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
DEFAULT_FROM_EMAIL  = config('DEFAULT_FROM_EMAIL',  default='Nexyza <hello@nexyza.com>')
SERVER_EMAIL        = config('SERVER_EMAIL',         default='hello@nexyza.com')

# ── Django-Q2 Redis broker ────────────────────────────────────────────────────
Q_CLUSTER.update({
    'redis': config('REDIS_URL', default='redis://localhost:6379/0'),
})

# ── Production logging — also write to file ───────────────────────────────────
LOGGING['handlers']['file']['level'] = 'WARNING'
LOGGING['root']['handlers'] = ['console_prod', 'file']
LOGGING['loggers']['django']['handlers'] = ['console_prod', 'file', 'mail_admins']
LOGGING['loggers']['apps']['handlers'] = ['console_prod', 'file']


# ── Database connection pooling (prod performance) ────────────────────────────
# PersistentDatabaseConnectionPool keeps connections alive across requests
DATABASES['default']['CONN_MAX_AGE'] = 60  # seconds — reuse DB connections

# ── Cache — use Redis if available, fallback to local memory ──────────────────
REDIS_URL = config('REDIS_URL', default='')
if REDIS_URL:
    CACHES = {
        'default': {
            'BACKEND': 'django.core.cache.backends.redis.RedisCache',
            'LOCATION': REDIS_URL,
            'OPTIONS': {'socket_connect_timeout': 5, 'socket_timeout': 5},
        }
    }

# ── Session engine — use cache-backed sessions in prod ───────────────────────
if REDIS_URL:
    SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
    SESSION_CACHE_ALIAS = 'default'

# ── Static files ─────────────────────────────────────────────────────────────
# Already set in base: STATICFILES_STORAGE = whitenoise CompressedManifest
# Ensure collectstatic runs before deployment.
