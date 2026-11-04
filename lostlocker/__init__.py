"""Lost Locker: a lost-and-found site for students."""

from __future__ import annotations

import logging
import secrets

import click
from flask import Flask, render_template
from flask_wtf.csrf import CSRFError, CSRFProtect

from . import api, auth, db, items
from .config import load_config

csrf = CSRFProtect()

# No inline scripts or styles and no third-party hosts, so a strict policy is possible.
CONTENT_SECURITY_POLICY = (
    "default-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; "
    "form-action 'self'; frame-ancestors 'none'"
)


def create_app(test_config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.from_mapping(load_config())
    if test_config:
        app.config.from_mapping(test_config)

    if not app.config["SECRET_KEY"]:
        if app.debug or app.testing:
            app.config["SECRET_KEY"] = secrets.token_hex(32)
        else:
            raise RuntimeError(
                "SECRET_KEY is not set. Generate one with "
                '`python -c "import secrets; print(secrets.token_hex(32))"` and put it in .env.'
            )

    logging.basicConfig(level=logging.INFO)
    csrf.init_app(app)
    db.init_app(app)
    app.register_blueprint(auth.bp)
    app.register_blueprint(items.bp)
    app.register_blueprint(api.bp)
    _register_error_handlers(app)
    _register_cli(app)

    @app.after_request
    def security_headers(response):
        response.headers.setdefault("Content-Security-Policy", CONTENT_SECURITY_POLICY)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "same-origin")
        return response

    return app


def _register_error_handlers(app: Flask) -> None:
    def show(code: int, title: str, message: str):
        return render_template("error.html", code=code, title=title, message=message), code

    @app.errorhandler(400)
    def bad_request(_e):
        return show(400, "Bad request", "That request wasn't valid. Please go back and try again.")

    @app.errorhandler(CSRFError)
    def csrf_error(_e):
        return show(400, "Session expired", "Your form expired. Please go back and try again.")

    @app.errorhandler(403)
    def forbidden(_e):
        return show(403, "Not allowed", "You don't have permission to do that.")

    @app.errorhandler(404)
    def not_found(_e):
        return show(404, "Not found", "We couldn't find that page.")

    @app.errorhandler(413)
    def too_large(_e):
        return show(413, "File too large", "That upload is too large. Photos can be up to 8 MB.")

    @app.errorhandler(500)
    def server_error(_e):
        return show(500, "Something went wrong", "Sorry, something went wrong on our end.")


def _register_cli(app: Flask) -> None:
    @app.cli.command("migrate")
    def migrate_command() -> None:
        """Create/upgrade the database schema."""
        applied = db.run_migrations(app.config["DATABASE_URL"])
        click.echo("Applied: " + ", ".join(applied) if applied else "Database is up to date.")

    @app.cli.command("make-admin")
    @click.argument("email")
    def make_admin_command(email: str) -> None:
        """Give an existing account admin rights."""
        conn = db.psycopg2.connect(app.config["DATABASE_URL"])
        try:
            with conn, conn.cursor() as cur:
                cur.execute(
                    "UPDATE users SET is_admin = true WHERE email = %s", (email.strip().lower(),)
                )
                if cur.rowcount == 0:
                    raise click.ClickException(f"No account with email {email}. Register first.")
        finally:
            conn.close()
        click.echo(f"{email} is now an admin.")
