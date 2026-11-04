"""Entry point for gunicorn / `flask run`: `gunicorn wsgi:app`."""

from lostlocker import create_app

app = create_app()
