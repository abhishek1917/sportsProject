#!/usr/bin/env bash
set -o errexit

python manage.py migrate --noinput
python manage.py seed_sports
if [ -n "${DJANGO_SUPERUSER_USERNAME:-}" ] && [ -n "${DJANGO_SUPERUSER_PASSWORD:-}" ]; then
  python manage.py createsuperuser --noinput || true
fi
exec gunicorn stadium_booking.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --timeout 120
