#!/bin/sh
# Single-container start for free hosting tiers (e.g. Render free web service), which have no
# pre-deploy command and no free background worker. Runs migrations, then Celery (with Beat
# embedded) in the background and gunicorn in the foreground.
#
# Beat must run in exactly one place: do not scale a service using this script above one
# instance, and do not also run a separate Beat process against the same broker.
set -e

python manage.py migrate --noinput

celery -A config worker -B \
    --concurrency="${CELERY_CONCURRENCY:-1}" \
    --loglevel="${LOG_LEVEL:-INFO}" \
    --schedule /tmp/celerybeat-schedule &

exec gunicorn config.wsgi:application \
    --bind "0.0.0.0:${PORT:-8000}" \
    --workers "${GUNICORN_WORKERS:-2}" \
    --timeout 120
