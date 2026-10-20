#!/bin/sh
# Production start (Render): apply migrations, create the demo data if asked, then serve on $PORT.
# Docker Compose runs its own command instead (see docker-compose.yml).
set -e
python manage.py migrate --noinput
if [ "${SEED_DEMO:-false}" = "true" ]; then
  python manage.py seed_demo
fi
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers "${WEB_CONCURRENCY:-2}" \
  --timeout 90 --access-logfile -
