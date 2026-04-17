#!/bin/bash
set -e

echo "=== Nexyza Setup ==="

# Create virtualenv
python3 -m venv venv
source venv/bin/activate

# Install deps
pip install -r requirements.txt -q

# Copy env if not exists
if [ ! -f .env ]; then
  cp .env.example .env
  echo "⚠  .env created from .env.example — fill in your API keys before running!"
fi

# Migrate
python manage.py migrate

# Create superuser
echo "Creating superuser (optional — press Ctrl+C to skip):"
python manage.py createsuperuser --noinput --email admin@nexyza.com || true

# Collect static (for production)
# python manage.py collectstatic --noinput

echo ""
echo "✅ Setup complete!"
echo ""
echo "Run the dev server:"
echo "  source venv/bin/activate"
echo "  python manage.py runserver"
echo ""
echo "Then visit: http://127.0.0.1:8000"
