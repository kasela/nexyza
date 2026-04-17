# Heroku / Railway / Render Procfile
web: gunicorn config.wsgi:application --workers 2 --threads 2 --timeout 120 --bind 0.0.0.0:$PORT
worker: python manage.py qcluster
