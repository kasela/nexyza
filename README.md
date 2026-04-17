# Nexyza — CSV, Excel & JSON Analyser SaaS

A production-ready Django SaaS app for analysing data files with AI-powered insights.

## Tech Stack
- **Backend**: Django 5, Python 3.11+
- **Frontend**: Tailwind CSS (CDN), HTMX, Chart.js
- **AI**: Anthropic Claude Sonnet
- **Billing**: LemonSqueezy (monthly/yearly subscriptions)
- **Auth**: django-allauth (email-based)

## Quick Start

### 1. Clone & Install
```bash
git clone <repo>
cd datalens
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Environment Variables
```bash
cp .env.example .env
# Fill in your keys (see below)
```

### 3. Migrate & Run
```bash
python manage.py migrate
python manage.py createsuperuser
python manage.py runserver
```

Visit http://127.0.0.1:8000

---

## Environment Variables

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DEBUG` | `True` for dev, `False` for production |
| `ANTHROPIC_API_KEY` | From https://console.anthropic.com |
| `LEMONSQUEEZY_API_KEY` | From LemonSqueezy dashboard |
| `LEMONSQUEEZY_STORE_ID` | Your LS store ID |
| `LEMONSQUEEZY_WEBHOOK_SECRET` | LS webhook signing secret |
| `LEMONSQUEEZY_MONTHLY_VARIANT_ID` | Monthly plan variant ID |
| `LEMONSQUEEZY_YEARLY_VARIANT_ID` | Yearly plan variant ID |

---

## LemonSqueezy Setup

1. Create an account at [lemonsqueezy.com](https://lemonsqueezy.com)
2. Create a **Store** → note your Store ID
3. Create a **Product** → add two **Variants**: Monthly ($12) and Yearly ($96)
4. Copy the Variant IDs to `.env`
5. Go to **Webhooks** → create webhook pointing to `https://yourdomain.com/billing/webhook/`
6. Select events: `subscription_created`, `subscription_updated`, `subscription_cancelled`, `subscription_expired`, `subscription_resumed`
7. Copy the signing secret to `LEMONSQUEEZY_WEBHOOK_SECRET`

---

## Project Structure

```
datalens/
├── config/              # Django settings, urls, wsgi
│   └── settings/
│       ├── base.py
│       └── dev.py
├── apps/
│   ├── core/            # Landing page
│   ├── accounts/        # Custom User model (email auth)
│   ├── billing/         # LemonSqueezy integration
│   │   ├── models.py    # Subscription, WebhookEvent
│   │   ├── middleware.py # Attach subscription to request
│   │   ├── views.py     # Checkout, webhook, portal
│   │   └── urls.py
│   ├── analyser/        # Core analysis engine
│   │   ├── models.py    # FileUpload
│   │   ├── engine.py    # Pandas-based stats engine
│   │   ├── ai.py        # Claude AI insights
│   │   └── views.py     # Upload, result, export, delete
│   └── dashboard/       # User dashboard
├── templates/           # All HTML templates
│   ├── base.html
│   ├── core/
│   ├── billing/
│   ├── analyser/
│   └── dashboard/
└── media/               # Uploaded files (gitignored)
```

---

## Plans & Limits

| Feature | Free | Pro |
|---|---|---|
| Uploads/month | 5 | Unlimited |
| Max file size | 1 MB | 10 MB |
| File types | CSV, Excel, JSON | CSV, Excel, JSON |
| Summary stats | ✅ | ✅ |
| Charts | ✅ | ✅ |
| AI Insights (Claude) | ❌ | ✅ |
| Export CSV/JSON | ✅ | ✅ |
| Price | $0 | $12/mo or $8/mo yearly |

---

## Key Features

### Analysis Engine (`apps/analyser/engine.py`)
- Parses CSV, Excel (.xlsx/.xls), and JSON
- Per-column stats: min, max, mean, median, std, quartiles
- Null/missing value detection
- Histogram data for numeric columns
- Top value frequencies for categorical columns
- Correlation matrix for numeric pairs
- 50-row data preview

### AI Insights (`apps/analyser/ai.py`)
- Sends column statistics to Claude Sonnet
- Returns structured markdown: overview, key findings, data quality, recommendations, use cases
- Cached on the FileUpload model (generated once, stored forever)
- Pro plan gated via middleware

### Billing Flow
1. User clicks "Upgrade" → `/billing/checkout/monthly/`
2. Django creates a LemonSqueezy checkout session
3. User pays on LS hosted page
4. LS fires webhook → `/billing/webhook/`
5. Webhook updates `Subscription` model
6. `SubscriptionMiddleware` checks status on every request

---

## Deployment (Production)

1. Set `DEBUG=False`, proper `SECRET_KEY`, `ALLOWED_HOSTS`
2. Use PostgreSQL: update `DATABASES` in `settings/prod.py`
3. Set up media storage (AWS S3 via `django-storages`)
4. Run `python manage.py collectstatic`
5. Use gunicorn + nginx

```bash
gunicorn config.wsgi:application --workers 3 --bind 0.0.0.0:8000
```

---

## Admin
Visit `/admin/` with your superuser credentials to manage users, subscriptions, and webhook events.
