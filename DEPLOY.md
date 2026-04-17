# Nexyza — Production Deployment Guide

## Quick deploy checklist

### 1. Environment variables (.env)
Copy `.env.example` → `.env` and fill in every value:

```bash
SECRET_KEY=<generate: python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())">
DEBUG=False
ALLOWED_HOSTS=nexyza.com,www.nexyza.com
DJANGO_SETTINGS_MODULE=config.settings.prod

# Database (PostgreSQL required in production)
DB_NAME=nexyza
DB_USER=nexyza
DB_PASSWORD=<strong-password>
DB_HOST=localhost
DB_PORT=5432

# Email — Hostinger SMTP
EMAIL_HOST_PASSWORD=<your-hostinger-hello@nexyza.com-password>

# AI
ANTHROPIC_API_KEY=sk-ant-...

# Billing (LemonSqueezy — optional, skip to disable paid plans)
LEMONSQUEEZY_API_KEY=...
LEMONSQUEEZY_STORE_ID=...
LEMONSQUEEZY_WEBHOOK_SECRET=...
LEMONSQUEEZY_PLUS_MONTHLY_VARIANT_ID=...
LEMONSQUEEZY_PLUS_YEARLY_VARIANT_ID=...
LEMONSQUEEZY_PRO_MONTHLY_VARIANT_ID=...
LEMONSQUEEZY_PRO_YEARLY_VARIANT_ID=...

# Google Sheets connector (optional)
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...

# Redis (required for production WebSockets + task queue)
REDIS_URL=redis://localhost:6379/0
```

### 2. Install & migrate
```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
python manage.py createsuperuser
```

### 3. Run
```bash
# Without WebSockets (simpler, recommended to start)
gunicorn config.wsgi:application --workers 2 --timeout 120

# With WebSockets (real-time collaboration feature)
daphne -b 0.0.0.0 -p 8000 config.asgi:application

# Background tasks (scheduled reports, auto-sync connectors) — run separately
python manage.py qcluster
```

---

## Platform-specific guides

### VPS (Ubuntu 22.04) — Recommended
```bash
# Install system deps
sudo apt install python3.12 python3.12-venv postgresql redis-server nginx

# Setup app
git clone <your-repo> /var/www/nexyza
cd /var/www/nexyza
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Configure nginx as reverse proxy (see nginx.conf.example)
# Configure systemd for gunicorn + qcluster (see systemd/)
```

### Railway / Render / Fly.io
1. Set all env vars in the platform dashboard
2. Build command: `pip install -r requirements.txt && python manage.py migrate && python manage.py collectstatic --noinput`
3. Start command: `gunicorn config.wsgi:application --workers 2 --timeout 120`
4. Add a separate worker service with: `python manage.py qcluster`

### Heroku
```bash
heroku create nexyza
heroku addons:create heroku-postgresql:essential-0
heroku addons:create heroku-redis:mini
heroku config:set DJANGO_SETTINGS_MODULE=config.settings.prod SECRET_KEY=... DEBUG=False
git push heroku main
heroku run python manage.py migrate
```

---

## Production Redis (channels + Q2)

Update `config/settings/prod.py` to use Redis channel layer:

```python
# Replace InMemoryChannelLayer with Redis
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {"hosts": [config('REDIS_URL', default='redis://localhost:6379/0')]},
    }
}

# Also configure Django-Q2 to use Redis broker
Q_CLUSTER['redis'] = config('REDIS_URL', default='redis://localhost:6379/0')
```

---

## What works without extra setup
- ✅ All analysis, charts, AI insights, NLQ
- ✅ Email (contact form, password reset, scheduled reports) via Hostinger
- ✅ PDF, PPTX, Excel exports
- ✅ Teams, roles, report builder
- ✅ Marketplace, catalog, versioning, formulas, cleaner
- ✅ LemonSqueezy billing (when keys provided)

## What needs extra config
- **Google Sheets connector** → Google Cloud OAuth credentials
- **Real-time collaboration** → Redis (replace InMemoryChannelLayer)
- **File uploads >100MB** → S3/R2 object storage (django-storages)
- **Multiple workers** → Redis for Django-Q2 broker

---

## Security checklist
- [ ] SECRET_KEY is long random string (not the dev default)
- [ ] DEBUG=False
- [ ] ALLOWED_HOSTS set to your domain only
- [ ] HTTPS enabled (prod.py already sets SECURE_SSL_REDIRECT=True)
- [ ] Database password is strong
- [ ] EMAIL_HOST_PASSWORD set
- [ ] ANTHROPIC_API_KEY set (AI features need this)
