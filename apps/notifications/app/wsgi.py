"""Entry point for gunicorn (`gunicorn app.wsgi:app`) and `flask --app app.wsgi run`."""
from . import create_app

app = create_app()
